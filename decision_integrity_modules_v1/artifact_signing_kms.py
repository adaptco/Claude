"""
Artifact Signing — RSASSA-PSS-SHA-256 (HSM/KMS-capable)
======================================================

Threat Model:
- RC3: RSASSA-PSS-SHA-256 signing via HSM/KMS only (production path)
- RC4: No re-sign policy enforced at application layer

This module provides a small, deterministic signing/verification surface:
- Canonicalizes payload via RFC 8785 JCS
- Hashes canonical payload (SHA-256)
- Signs the hash using RSASSA-PSS-SHA-256
- Binds signature scope to environment + key_version + payload_hash
- Enforces \"no re-sign\" by consulting a registry (caller's storage)

Design note:
The runtime kernel should only call signing after state == FINALIZED and after
the FINAL event is committed. This module exposes guard rails but does not
own transactions.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Protocol, Sequence

from canonicalization_rfc8785 import canonicalize_rfc8785, canonical_hash

# Optional deps: cloud KMS client
try:
    from google.cloud.kms_v1 import KeyManagementServiceClient  # type: ignore
    from google.cloud.kms_v1.types import AsymmetricSignRequest  # type: ignore
except Exception:  # pragma: no cover
    KeyManagementServiceClient = None  # type: ignore
    AsymmetricSignRequest = None  # type: ignore

# Local signing (tests/dev)
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed


# =============================================================================
# Types
# =============================================================================

class SignatureRegistry(Protocol):
    """
    Registry for enforcing no re-sign policy.

    Must be implemented by caller (DB table, KV store, etc).
    """

    def has_signature(self, artifact_id: str) -> bool: ...
    def record_signature(self, artifact_id: str, signature_record: Dict[str, Any]) -> None: ...


class Signer(Protocol):
    def sign_prehashed_sha256(self, digest: bytes) -> bytes: ...
    def key_version(self) -> str: ...


@dataclass(frozen=True)
class SignatureEnvelope:
    artifact_id: str
    environment: str
    key_version: str
    payload_hash_sha256: str
    signed_at: str  # RFC3339
    algorithm: str  # "RSASSA_PSS_SHA_256"
    signature_b64: str

    # Optional: extra bindings for audit-grade defensibility
    scope: Optional[Dict[str, Any]] = None


# =============================================================================
# Production signer: Google Cloud KMS (asymmetric signing key)
# =============================================================================

class GcpKmsPssSigner:
    """
    Production path. Requires:
    - An asymmetric signing key in Cloud KMS (preferably HSM-backed)
    - IAM allowing only sign() for runtime identity
    """

    def __init__(self, *, kms_key_version_resource: str, client: Optional[Any] = None):
        if KeyManagementServiceClient is None:
            raise RuntimeError("google-cloud-kms is not installed; cannot use GcpKmsPssSigner")
        self._client = client or KeyManagementServiceClient()
        self._key_version = kms_key_version_resource

    def key_version(self) -> str:
        return self._key_version

    def sign_prehashed_sha256(self, digest: bytes) -> bytes:
        if AsymmetricSignRequest is None:
            raise RuntimeError("google-cloud-kms is not installed; cannot sign")
        req = AsymmetricSignRequest(
            name=self._key_version,
            digest={"sha256": digest},
        )
        resp = self._client.asymmetric_sign(request=req)
        return bytes(resp.signature)


# =============================================================================
# Dev/test signer: local RSA key (NOT for production)
# =============================================================================

class LocalRsaPssSigner:
    def __init__(self, private_key: rsa.RSAPrivateKey, *, key_version: str = "local-dev"):
        self._priv = private_key
        self._ver = key_version

    @staticmethod
    def generate(bits: int = 3072, *, key_version: str = "local-dev") -> "LocalRsaPssSigner":
        priv = rsa.generate_private_key(public_exponent=65537, key_size=bits)
        return LocalRsaPssSigner(priv, key_version=key_version)

    def key_version(self) -> str:
        return self._ver

    def sign_prehashed_sha256(self, digest: bytes) -> bytes:
        return self._priv.sign(
            digest,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
            Prehashed(hashes.SHA256()),
        )

    def public_key(self):
        return self._priv.public_key()


def verify_rsassa_pss_sha256(public_key, digest: bytes, signature: bytes) -> bool:
    try:
        public_key.verify(
            signature,
            digest,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
            Prehashed(hashes.SHA256()),
        )
        return True
    except Exception:
        return False


# =============================================================================
# Orchestrated signing API
# =============================================================================

def sign_artifact(
    *,
    artifact_id: str,
    payload: Any,
    environment: str,
    signer: Signer,
    registry: SignatureRegistry,
    scope: Optional[Dict[str, Any]] = None,
    require_unsigned: bool = True,
) -> SignatureEnvelope:
    """
    Canonicalize + hash + sign an artifact, enforcing no re-sign.

    - require_unsigned=True: fail if already signed (RC4)
    """
    if require_unsigned and registry.has_signature(artifact_id):
        raise ValueError(f"No re-sign policy: artifact {artifact_id} already signed")

    canonical = canonicalize_rfc8785(payload)
    payload_hash = canonical_hash(payload, "sha256")
    digest = bytes.fromhex(payload_hash)

    signature = signer.sign_prehashed_sha256(digest)
    env = SignatureEnvelope(
        artifact_id=artifact_id,
        environment=environment,
        key_version=signer.key_version(),
        payload_hash_sha256=payload_hash,
        signed_at=datetime.now(timezone.utc).isoformat(),
        algorithm="RSASSA_PSS_SHA_256",
        signature_b64=base64.b64encode(signature).decode("ascii"),
        scope=scope,
    )

    # record immutably
    registry.record_signature(artifact_id, {
        "artifact_id": env.artifact_id,
        "environment": env.environment,
        "key_version": env.key_version,
        "payload_hash_sha256": env.payload_hash_sha256,
        "signed_at": env.signed_at,
        "algorithm": env.algorithm,
        "signature_b64": env.signature_b64,
        "scope": env.scope,
    })
    return env


def verify_envelope(
    *,
    envelope: SignatureEnvelope,
    payload: Any,
    public_key,
    expected_environment: Optional[str] = None,
) -> bool:
    """
    Verify payload matches envelope hash and signature verifies.

    expected_environment: if set, require envelope.environment matches (anti-replay across env).
    """
    if expected_environment and envelope.environment != expected_environment:
        return False

    payload_hash = canonical_hash(payload, "sha256")
    if payload_hash != envelope.payload_hash_sha256:
        return False

    digest = bytes.fromhex(payload_hash)
    sig = base64.b64decode(envelope.signature_b64.encode("ascii"))
    return verify_rsassa_pss_sha256(public_key, digest, sig)
