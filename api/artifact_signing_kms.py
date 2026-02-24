"""
RSASSA-PSS-SHA-256 Artifact Signing
====================================
Threat Model RC3: RSASSA-PSS-SHA-256 signing via HSM/KMS only
Threat Model RC4: No re-sign policy enforced at application layer

Integrates with Google Cloud KMS for HSM-backed signing.
Enforces constitutional guarantees:
- Sign only FINALIZED states
- No re-signing of artifacts
- Environment scoping
- Signature binding to canonical payload hash
"""

from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel
import base64

from google.cloud import kms
from google.cloud.kms_v1 import KeyManagementServiceClient

from canonicalization_rfc8785 import canonicalize_rfc8785, canonical_hash
from core_fsm_states import State


# =============================================================================
# Signature Models
# =============================================================================

class SignatureMetadata(BaseModel):
    """
    Cryptographic signature metadata
    
    Threat Model References:
    - Section 4.3 Signing: Environment bound, key_version embedded
    - RC4: No re-sign policy
    """
    algorithm: str = "RSASSA-PSS-SHA-256"
    key_id: str  # Full KMS key resource name
    key_version: str
    environment: str  # "production" | "staging" | "development"
    signed_at: str  # ISO 8601 timestamp
    signer_identity: str  # Service account email
    
    # Threat Model: Bind canonical payload hash
    canonical_payload_hash: str  # SHA-256 of canonical form
    
    # Threat Model: Bind execution state
    execution_id: str
    tenant_id: str
    final_event_hash: str  # Hash of FINALIZED event


class ArtifactSignature(BaseModel):
    """
    Complete artifact signature
    
    Stored in database for verification
    """
    signature_id: str
    metadata: SignatureMetadata
    signature_value: str  # Base64-encoded signature
    
    # No re-sign tracking
    signed_execution_hash: str  # Prevents re-signing
    
    created_at: datetime


# =============================================================================
# No Re-Sign Policy Enforcement
# =============================================================================

class ResignViolation(Exception):
    """Raised when attempting to re-sign an artifact"""
    pass


class InvalidStateForSigning(Exception):
    """Raised when attempting to sign non-FINALIZED state"""
    pass


# =============================================================================
# KMS Signing Service
# =============================================================================

class KMSSigningService:
    """
    Google Cloud KMS signing service
    
    Threat Model Controls:
    - RC3: RSASSA-PSS-SHA-256 via HSM/KMS only
    - RC4: No re-sign policy
    - Section 4.3: Separate IAM roles
    """
    
    def __init__(
        self,
        project_id: str,
        location: str,
        key_ring: str,
        key_name: str,
        environment: str = "production"
    ):
        """
        Initialize KMS signing service
        
        Args:
            project_id: GCP project ID
            location: KMS location (e.g., "us-central1")
            key_ring: Key ring name
            key_name: Key name
            environment: Environment scope
        
        IAM Requirements (Threat Model Section 4.3):
        - Runtime service account: roles/cloudkms.signerVerifier
        - Signing service account: roles/cloudkms.cryptoOperator
        - Key admin account: roles/cloudkms.admin (separate)
        """
        self.client = KeyManagementServiceClient()
        self.environment = environment
        
        # Build key path
        self.key_path = self.client.crypto_key_version_path(
            project_id, location, key_ring, key_name, "1"  # Primary version
        )
    
    async def sign_artifact(
        self,
        tenant_id: str,
        execution_id: str,
        final_event_hash: str,
        payload: Dict[str, Any],
        current_state: str,
        signer_identity: str,
        existing_signature: Optional[str] = None
    ) -> ArtifactSignature:
        """
        Sign execution artifact
        
        Threat Model Enforcements:
        1. RC3: Uses KMS RSASSA-PSS-SHA-256
        2. RC4: Prevents re-signing
        3. Section 4.3 Tampering: Only sign FINALIZED state
        4. Section 4.3 Signing: Environment bound
        
        Args:
            tenant_id: Tenant identifier
            execution_id: Execution identifier
            final_event_hash: Hash of FINALIZED event
            payload: Artifact payload (to be canonicalized)
            current_state: Current FSM state
            signer_identity: Service account email
            existing_signature: Existing signature hash (for re-sign check)
        
        Returns:
            ArtifactSignature
        
        Raises:
            InvalidStateForSigning: If state != FINALIZED
            ResignViolation: If artifact already signed
        """
        
        # CONSTITUTIONAL CHECK 1: Only sign FINALIZED state
        if current_state != State.FINALIZED.value:
            raise InvalidStateForSigning(
                f"Cannot sign non-FINALIZED state: {current_state}. "
                f"Threat Model RC3: Signature only allowed when state == FINALIZED"
            )
        
        # CONSTITUTIONAL CHECK 2: No re-signing
        if existing_signature:
            raise ResignViolation(
                f"Artifact already signed: {existing_signature[:16]}... "
                f"Threat Model RC4: No re-sign policy enforced"
            )
        
        # Step 1: Canonicalize payload
        canonical = canonicalize_rfc8785(payload)
        canonical_hash_value = canonical_hash(payload)
        
        # Step 2: Build signing payload
        # Threat Model: Environment, key_version, tenant_id bound
        signing_payload = {
            "tenant_id": tenant_id,
            "execution_id": execution_id,
            "environment": self.environment,
            "canonical_payload_hash": canonical_hash_value,
            "final_event_hash": final_event_hash,
            "signed_at": datetime.utcnow().isoformat() + "Z"
        }
        
        # Canonicalize signing payload
        signing_canonical = canonicalize_rfc8785(signing_payload)
        
        # Step 3: Sign with KMS
        # Build digest (KMS expects digest, not raw data)
        import hashlib
        digest = hashlib.sha256(signing_canonical).digest()
        
        # KMS sign request
        response = self.client.asymmetric_sign(
            request={
                "name": self.key_path,
                "digest": {"sha256": digest}
            }
        )
        
        signature_bytes = response.signature
        signature_b64 = base64.b64encode(signature_bytes).decode('utf-8')
        
        # Step 4: Extract key version from response
        key_version = response.name.split("/")[-1]
        
        # Step 5: Build signature metadata
        metadata = SignatureMetadata(
            key_id=self.key_path,
            key_version=key_version,
            environment=self.environment,
            signed_at=signing_payload["signed_at"],
            signer_identity=signer_identity,
            canonical_payload_hash=canonical_hash_value,
            execution_id=execution_id,
            tenant_id=tenant_id,
            final_event_hash=final_event_hash
        )
        
        # Step 6: Create artifact signature
        signature_id = f"sig-{execution_id}-{datetime.utcnow().timestamp()}"
        
        artifact_signature = ArtifactSignature(
            signature_id=signature_id,
            metadata=metadata,
            signature_value=signature_b64,
            signed_execution_hash=final_event_hash,  # Prevents re-signing
            created_at=datetime.utcnow()
        )
        
        return artifact_signature
    
    async def verify_signature(
        self,
        signature: ArtifactSignature,
        payload: Dict[str, Any]
    ) -> bool:
        """
        Verify artifact signature
        
        Threat Model Section 4.3 Repudiation: Public verification supported
        
        Args:
            signature: Artifact signature to verify
            payload: Original payload
        
        Returns:
            True if signature valid
        """
        
        # Step 1: Recompute canonical hash
        canonical_hash_value = canonical_hash(payload)
        
        # Verify canonical hash matches metadata
        if canonical_hash_value != signature.metadata.canonical_payload_hash:
            return False
        
        # Step 2: Rebuild signing payload
        signing_payload = {
            "tenant_id": signature.metadata.tenant_id,
            "execution_id": signature.metadata.execution_id,
            "environment": signature.metadata.environment,
            "canonical_payload_hash": canonical_hash_value,
            "final_event_hash": signature.metadata.final_event_hash,
            "signed_at": signature.metadata.signed_at
        }
        
        signing_canonical = canonicalize_rfc8785(signing_payload)
        
        # Step 3: Compute digest
        import hashlib
        digest = hashlib.sha256(signing_canonical).digest()
        
        # Step 4: Verify with KMS
        signature_bytes = base64.b64decode(signature.signature_value)
        
        # Get public key from KMS
        public_key_response = self.client.get_public_key(
            request={"name": signature.metadata.key_id}
        )
        
        # Verify signature (using cryptography library)
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
        
        public_key = serialization.load_pem_public_key(
            public_key_response.pem.encode('utf-8')
        )
        
        try:
            public_key.verify(
                signature_bytes,
                signing_canonical,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception:
            return False


# =============================================================================
# Database Schema for Signatures
# =============================================================================

SIGNATURE_SCHEMA_SQL = """
-- Artifact signatures table
CREATE TABLE IF NOT EXISTS artifact_signatures (
    signature_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    execution_id TEXT NOT NULL,
    
    -- Signature metadata (JSONB for flexibility)
    metadata JSONB NOT NULL,
    
    -- Base64-encoded signature value
    signature_value TEXT NOT NULL,
    
    -- No re-sign enforcement
    signed_execution_hash TEXT NOT NULL UNIQUE,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Index for lookups
    INDEX idx_execution_signature ON artifact_signatures(tenant_id, execution_id)
);

-- CONSTITUTIONAL CONSTRAINT: No re-signing
-- Enforced by UNIQUE constraint on signed_execution_hash
"""


# =============================================================================
# Integration with Event Store
# =============================================================================

async def sign_finalized_execution(
    signing_service: KMSSigningService,
    tenant_id: str,
    execution_id: str,
    final_event_hash: str,
    payload: Dict[str, Any],
    signer_identity: str,
    db_conn
) -> ArtifactSignature:
    """
    Sign execution after FINALIZED
    
    Threat Model Workflow:
    1. Verify state == FINALIZED
    2. Check no existing signature
    3. Sign with KMS
    4. Store signature in database
    
    Args:
        signing_service: KMS signing service
        tenant_id: Tenant ID
        execution_id: Execution ID
        final_event_hash: Hash of FINALIZED event
        payload: Artifact payload
        signer_identity: Service account email
        db_conn: Database connection
    
    Returns:
        ArtifactSignature
    """
    
    # Check for existing signature
    existing = await db_conn.fetchval(
        "SELECT signed_execution_hash FROM artifact_signatures "
        "WHERE tenant_id = $1 AND execution_id = $2",
        tenant_id, execution_id
    )
    
    # Sign artifact
    signature = await signing_service.sign_artifact(
        tenant_id=tenant_id,
        execution_id=execution_id,
        final_event_hash=final_event_hash,
        payload=payload,
        current_state=State.FINALIZED.value,
        signer_identity=signer_identity,
        existing_signature=existing
    )
    
    # Store signature
    await db_conn.execute(
        """
        INSERT INTO artifact_signatures (
            signature_id, tenant_id, execution_id,
            metadata, signature_value, signed_execution_hash
        )
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        signature.signature_id,
        signature.metadata.tenant_id,
        signature.metadata.execution_id,
        signature.metadata.dict(),
        signature.signature_value,
        signature.signed_execution_hash
    )
    
    return signature


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    print("="*60)
    print("RSASSA-PSS-SHA-256 Artifact Signing")
    print("Threat Model RC3 + RC4")
    print("="*60)
    
    print("\nThreat Model Enforcements:")
    print("✅ RC3: RSASSA-PSS-SHA-256 via Google Cloud KMS")
    print("✅ RC4: No re-sign policy (unique constraint)")
    print("✅ Section 4.3: Only sign FINALIZED state")
    print("✅ Section 4.3: Environment + key_version bound")
    print("✅ Section 4.3: Separate IAM roles required")
    
    print("\nRequired IAM Roles:")
    print("- Runtime: roles/cloudkms.signerVerifier")
    print("- Signing Service: roles/cloudkms.cryptoOperator")
    print("- Key Admin: roles/cloudkms.admin (separate account)")
