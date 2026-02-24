# Threat Model → Implementation Mapping (RC1–RC7)

This document maps each **Required Normative Control (RC1–RC7)** from *Threat Model v1.0* to concrete implementation artifacts.

> Goal: **forensic-grade reproducibility** ("what rules were in force when this was approved?") while preserving **runtime determinism**.

---

## RC1 — Append-only event store enforced at DB level

**Status:** Provided by existing `event_store_postgres.py` (caller-owned).

**Non-negotiables (must exist):**
- Append-only writes (no UPDATE/DELETE for event rows)
- `hash_prev` / `hash_current` chain
- Tenant-scoped access controls (RLS or application-enforced)

---

## RC2 — RFC 8785 canonicalization version locked

**Implementation:** `canonicalization_rfc8785.py`

**What it guarantees:**
- Deterministic, cross-language stable JSON canonicalization
- JCS version string embedded via `JCS_VERSION`
- "Provably pure" classification hashing via `compute_classification_hash(...)`

**Operational control:**
- Pin a cross-language canonicalization corpus in CI (Python/Go/TS)
- Any canonicalization change requires a version bump and corpus update

---

## RC3 — RSASSA-PSS-SHA-256 signing via HSM/KMS only

**Implementation:** `artifact_signing_kms.py`

**Notes:**
- Production signer: `GcpKmsPssSigner` (requires Cloud KMS asymmetric key)
- Dev/test signer: `LocalRsaPssSigner` (explicitly **NOT** for production)

**Signature binding includes:**
- `environment`
- `key_version`
- `payload_hash_sha256`
- Optional `scope` (e.g., FINAL event hash, execution_id, tenant_id)

---

## RC4 — No re-sign policy enforced at application layer

**Implementation:** `artifact_signing_kms.py`

**Mechanism:**
- `sign_artifact(..., registry=SignatureRegistry, require_unsigned=True)`
- Registry is caller-owned storage that rejects a second signature for same `artifact_id`

**Hard rule:**
- Re-signing is not allowed. Any change must produce a new artifact with a new id.

---

## RC5 — Role matrix + materiality table versioning and hash embedding

**Implementation:** `revenue_policy_validator.py` + `canonicalization_rfc8785.py`

**Required fields in OverrideCreated (normative):**
- `role_matrix_version`
- `materiality_table_version`
- `classification_hash`
- `authorization_snapshot` (frozen)

**Purity requirement:**
- `classification_hash` MUST be computed using only stable inputs (no wall clock, no DB order)

---

## RC6 — Anchor window deterministic and recorded

**Implementation:** `merkle_anchoring.py`

**Key mechanics:**
- Deterministic `(window_start, window_end)`
- Snapshot boundary: `snapshot_max_created_at` captured before leaf fetch
- Deterministic leaf ordering: `ORDER BY id ASC`
- Post-anchor retro insert prevention: reject inserts with `created_at <= last_window_end`

**DDL helper:** `anchor_records_ddl()`

---

## RC7 — Replay verification validates chain + signature + classification hash

**Status:** Provided by existing `verification.py` (caller-owned).

**Must verify:**
1. Event chain integrity (genesis → head)
2. Canonical hash matches signed payload
3. Signature verifies (key_version + environment scope)
4. Embedded `classification_hash` recomputes correctly
5. Override resolution replays deterministically

---

## Recommended CI Gates (minimal)

1. **JCS corpus tests** across languages (pass/fail)
2. **Signature verification roundtrip** (dev keys) + contract tests for KMS
3. **Anchor determinism** (same window inputs → same root)
4. **No re-sign** invariants (attempted second signature must fail)

---

End.
