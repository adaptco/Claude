# Cryptographic Parameter Policy v1.0

**Version:** 1.0  
**Status:** Normative  
**Effective Date:** 2026-02-15  
**Review Interval:** Annual (or upon algorithm deprecation)  
**Authority:** Security Architecture Board

---

## 1. Executive Summary

This policy defines mandatory cryptographic parameters for the Override & Decision Integrity Substrate. All implementations MUST comply with NIST SP 800-57, FIPS 140-2/3, and current IETF standards.

**Security Posture:**
- Minimum 128-bit security strength
- FIPS 140-2 Level 2+ for key operations
- NIST-approved algorithms only
- Quantum-resistance awareness (future migration path)

---

## 2. Cryptographic Algorithms

### 2.1 Digital Signatures (RC3)

**Primary Algorithm:** RSASSA-PSS with SHA-256

```yaml
Algorithm: RSASSA-PSS (Probabilistic Signature Scheme)
Hash Function: SHA-256
Modulus Size: 3072 bits (minimum)
Recommended: 4096 bits
Public Exponent: 65537 (F4)
Salt Length: 32 bytes (matches hash output)
MGF: MGF1 with SHA-256
```

**NIST References:**
- FIPS 186-5: Digital Signature Standard
- NIST SP 800-57 Part 1: Key strength 128-bit through 2030
- NIST SP 800-131A: Approved for federal use

**Rationale:**
- RSA-PSS provides provable security vs RSA-PKCS#1 v1.5
- 3072-bit RSA ≈ 128-bit symmetric strength (approved through 2030)
- 4096-bit RSA ≈ 152-bit symmetric strength (future-proof)
- Deterministic padding eliminates signature malleability

**Approved Key Sizes:**

| Modulus (bits) | Security Strength | Valid Through | Status |
|----------------|-------------------|---------------|--------|
| 2048 | 112-bit | 2030 (deprecated) | ❌ Not Approved |
| 3072 | 128-bit | 2030+ | ✅ Minimum |
| 4096 | 152-bit | 2050+ | ✅ Recommended |

**MUST NOT USE:**
- ❌ RSA-PKCS#1 v1.5 (vulnerable to padding oracle)
- ❌ DSA (deprecated per NIST SP 800-131A)
- ❌ ECDSA without deterministic nonce (RFC 6979)

---

### 2.2 Hash Functions

**Primary Hash:** SHA-256

```yaml
Algorithm: SHA-256
Output Size: 256 bits (32 bytes)
Block Size: 512 bits
Security Strength: 128-bit collision resistance
```

**NIST References:**
- FIPS 180-4: Secure Hash Standard
- NIST SP 800-107: Approved through 2030+

**Hash Function Hierarchy:**

| Algorithm | Output (bits) | Security | Status |
|-----------|--------------|----------|--------|
| SHA-1 | 160 | Broken | ❌ Forbidden |
| SHA-256 | 256 | 128-bit | ✅ Approved |
| SHA-384 | 384 | 192-bit | ✅ Approved |
| SHA-512 | 512 | 256-bit | ✅ Approved |
| SHA3-256 | 256 | 128-bit | ✅ Approved (alternative) |

**Usage Contexts:**
- **Event Hash Chain:** SHA-256 (Threat Model RC1)
- **Canonical Payload Hash:** SHA-256 (Threat Model RC2)
- **Merkle Tree:** SHA-256 (Threat Model RC6)
- **Classification Hash:** SHA-256 (Threat Model RC5)

**MUST NOT USE:**
- ❌ MD5 (broken, NIST deprecated)
- ❌ SHA-1 (collision attacks demonstrated)

---

### 2.3 JSON Canonicalization (RC2)

**Standard:** RFC 8785 (JSON Canonicalization Scheme)

```yaml
Specification: RFC 8785
Encoding: UTF-8
Number Format: IEEE 754 double precision
String Escaping: Minimal (per RFC 8785 Section 3.2.2.2)
Key Sorting: Lexicographic (code point order)
Whitespace: Removed
```

**Version Lock:** 1.0 (LOCKED - requires formal security review to change)

**Implementation Requirements:**
- MUST use IETF-approved JCS library
- MUST validate with cross-language test corpus
- MUST pin library version in build
- MUST NOT accept non-canonical JSON for signature verification

**Test Vectors:** Defined in `canonicalization_rfc8785.py`

---

## 3. Key Management

### 3.1 Key Generation

**Entropy Source:**

```yaml
Source: FIPS 140-2 validated DRBG (Deterministic Random Bit Generator)
Algorithm: CTR_DRBG (AES-256)
Reseeding: Every 2^20 requests or 1 hour
Seed Entropy: 256 bits minimum
```

**NIST References:**
- NIST SP 800-90A: Recommendation for Random Number Generation
- FIPS 140-2: Security Requirements for Cryptographic Modules

**RSA Key Pair Generation:**

```yaml
Method: Probabilistic prime generation
Prime Size: 1536 bits (for 3072-bit modulus)
Prime Generation: FIPS 186-5 Appendix B.3.3
Primality Testing: Miller-Rabin (FIPS 186-5)
```

---

### 3.2 Key Storage (RC3: HSM/KMS)

**Hardware Security Module (HSM) Requirements:**

```yaml
Certification: FIPS 140-2 Level 2 minimum (Level 3 recommended)
Key Extraction: NOT PERMITTED
Key Operations: Performed inside HSM boundary
Audit Logging: Required for all key operations
Tamper Detection: Physical and logical
```

**Google Cloud KMS Compliance:**

| Requirement | GCP KMS Implementation | Status |
|-------------|----------------------|--------|
| FIPS 140-2 Level 3 | Cloud HSM (hardware-backed keys) | ✅ |
| Key extraction prevention | Keys never leave HSM | ✅ |
| Audit logging | Cloud Audit Logs | ✅ |
| Access control | IAM with service accounts | ✅ |
| Key versioning | Automatic versioning | ✅ |

**IAM Role Separation (Threat Model Section 4.3):**

```yaml
Runtime Service Account:
  Role: roles/cloudkms.signerVerifier
  Permissions: Sign, verify (no key management)

Signing Service Account:
  Role: roles/cloudkms.cryptoOperator
  Permissions: Sign operations only

Key Admin Account:
  Role: roles/cloudkms.admin
  Permissions: Key creation, rotation, deletion
  Requirement: Separate from runtime accounts
```

**MUST NOT:**
- ❌ Store private keys in application memory
- ❌ Export private keys from HSM
- ❌ Use software-backed keys for production signing

---

### 3.3 Key Rotation

**Rotation Policy:**

```yaml
RSA Signing Keys:
  Rotation Interval: 365 days (annual)
  Emergency Rotation: Within 24 hours (compromise suspected)
  Grace Period: 30 days (dual-signature verification)
  Trigger Events:
    - Calendar-based (annual)
    - Personnel change (key admin departure)
    - Suspected compromise
    - Algorithm deprecation

Symmetric Keys (if used):
  Rotation Interval: 90 days
  Key Derivation: HKDF-SHA256
```

**Rotation Procedure:**

1. Generate new key in HSM (version N+1)
2. Activate new key for signing
3. Maintain old key (version N) for verification (30 days)
4. Log rotation as signed governance event
5. Update key version in signature metadata
6. Retire old key after grace period

**NIST References:**
- NIST SP 800-57 Part 1 Rev. 5: Section 5.3.6 (Key Rotation)

---

### 3.4 Key Destruction

**Secure Key Deletion:**

```yaml
Method: NIST SP 800-88 Media Sanitization
HSM Deletion: Cryptographic erase (immediate)
Backup Deletion: Physical destruction or cryptographic wipe
Verification: Deletion logged and audited
Retention: 7 years for governance/compliance
```

**Destruction Triggers:**
- Key compromise confirmed
- End of cryptographic period
- Algorithm deprecation
- Regulatory requirement

---

## 4. Merkle Tree Parameters (RC6)

**Merkle Tree Construction:**

```yaml
Hash Function: SHA-256
Leaf Node: H(event.hash_current)
Internal Node: H(left_hash || right_hash)
Odd Leaves: Duplicate last leaf
Root Hash: 256 bits (32 bytes)
```

**Anchor Frequency:**

```yaml
Window Duration: 24 hours (deterministic)
Maximum Events: 1,000,000 per window
Minimum Events: 1 (at least one event required)
Anchor Target: Polygon (EVM-compatible)
Confirmation Blocks: 12 blocks (finality)
```

**NIST References:**
- NIST FIPS 180-4: SHA-256 for Merkle trees

---

## 5. TLS/Transport Security

**TLS Version:**

```yaml
Minimum Version: TLS 1.3
Approved Versions: TLS 1.3 only
Deprecated: TLS 1.2, 1.1, 1.0, SSL 3.0, SSL 2.0
```

**Approved Cipher Suites (TLS 1.3):**

```yaml
TLS_AES_256_GCM_SHA384         # Recommended
TLS_AES_128_GCM_SHA256         # Approved
TLS_CHACHA20_POLY1305_SHA256   # Approved (mobile)
```

**MUST NOT USE:**
- ❌ CBC mode ciphers (padding oracle vulnerabilities)
- ❌ RC4 (broken)
- ❌ 3DES (deprecated)
- ❌ Export ciphers
- ❌ Anonymous ciphers (no authentication)

**Certificate Requirements:**

```yaml
Key Type: RSA or ECDSA
RSA Modulus: 3072 bits minimum
ECDSA Curve: P-256 (secp256r1) or P-384
Signature: RSA-PSS-SHA256 or ECDSA-SHA256
Validity: 398 days maximum (per CA/Browser Forum)
```

---

## 6. Database Encryption

**Encryption at Rest:**

```yaml
Algorithm: AES-256-GCM
Key Management: Google Cloud KMS
Key Rotation: Automatic (90 days)
Scope: All event store data
```

**PostgreSQL TDE (Transparent Data Encryption):**

```yaml
Extension: pgcrypto (built-in)
Column Encryption: AES-256-GCM for sensitive fields
Backup Encryption: AES-256-GCM
Key Hierarchy:
  - Master Key: Google Cloud KMS (HSM-backed)
  - Data Encryption Keys: Derived via HKDF-SHA256
```

---

## 7. Random Number Generation

**Production Requirements:**

```yaml
Source: /dev/urandom (Linux)
Fallback: FIPS 140-2 validated DRBG
Algorithm: CTR_DRBG (AES-256)
Seed: 256 bits minimum
Reseeding: Per NIST SP 800-90A
```

**MUST NOT USE:**
- ❌ /dev/random (blocking, DoS risk)
- ❌ Mersenne Twister (not cryptographic)
- ❌ Linear congruential generators
- ❌ JavaScript Math.random()

**Nonce Generation:**

```yaml
Context: Override IDs, Execution IDs
Length: 128 bits minimum
Uniqueness: Cryptographically random (collision probability < 2^-64)
Format: UUID v4 (RFC 4122)
```

---

## 8. Quantum Resistance Posture

**Current Status:** Classical cryptography (pre-quantum)

**Migration Path:**

```yaml
Timeline: Post-2030 (NIST PQC standardization complete)
Candidates:
  - CRYSTALS-Dilithium (signatures)
  - CRYSTALS-Kyber (key encapsulation)
  - SPHINCS+ (stateless hash-based signatures)

Hybrid Approach (Transition):
  - Dual signatures: RSA-PSS + Dilithium
  - Graceful degradation
  - Backward compatibility
```

**Monitoring:**
- Track NIST PQC standardization (FIPS 203, 204, 205)
- Assess quantum computing advances
- Plan migration by 2028

---

## 9. Compliance Matrix

### 9.1 FIPS 140-2 Compliance

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| Approved algorithms | RSA-PSS, SHA-256, AES-256 | ✅ |
| HSM Level 2+ | Google Cloud HSM | ✅ |
| Key extraction prevention | Keys in HSM only | ✅ |
| Self-tests | KMS automatic | ✅ |
| Audit logging | Cloud Audit Logs | ✅ |

### 9.2 PCI-DSS Compliance

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| 3.5: Protect keys | HSM storage | ✅ |
| 3.6: Key management | Documented procedures | ✅ |
| 4.1: Strong crypto | TLS 1.3, AES-256 | ✅ |
| 8.3: Multi-factor | IAM with 2FA | ✅ |

### 9.3 SOC2 Type II

| Control | Implementation | Status |
|---------|----------------|--------|
| CC6.1: Logical access | IAM role separation | ✅ |
| CC6.6: Encryption | AES-256, TLS 1.3 | ✅ |
| CC6.7: Key management | HSM, rotation policy | ✅ |
| CC7.2: Monitoring | Audit logs, alerts | ✅ |

---

## 10. Algorithm Deprecation Timeline

**Current (2026):**

| Algorithm | Status | Sunset Date |
|-----------|--------|-------------|
| SHA-256 | ✅ Approved | 2030+ |
| RSA-3072 | ✅ Approved | 2030 |
| RSA-4096 | ✅ Approved | 2050+ |
| AES-256 | ✅ Approved | 2030+ |
| TLS 1.3 | ✅ Approved | 2030+ |

**Deprecated:**

| Algorithm | Status | Reason |
|-----------|--------|--------|
| SHA-1 | ❌ Forbidden | Collision attacks (2017) |
| MD5 | ❌ Forbidden | Broken (2004) |
| RSA-2048 | ⚠️ Transitional | Below 128-bit strength (2030) |
| TLS 1.2 | ⚠️ Transitional | Migrate to TLS 1.3 |
| DSA | ❌ Forbidden | NIST deprecated |

---

## 11. Security Strength Levels

**NIST SP 800-57 Security Strength:**

| Strength | Symmetric | RSA Modulus | ECC Curve | Hash | Status |
|----------|-----------|-------------|-----------|------|--------|
| 112-bit | 3DES | 2048 | P-224 | SHA-224 | ⚠️ Deprecated |
| 128-bit | AES-128 | 3072 | P-256 | SHA-256 | ✅ Minimum |
| 192-bit | AES-192 | 7680 | P-384 | SHA-384 | ✅ Approved |
| 256-bit | AES-256 | 15360 | P-521 | SHA-512 | ✅ Approved |

**Recommendation:** Use 128-bit security strength minimum (valid through 2030+)

---

## 12. Operational Procedures

### 12.1 Key Ceremony

**Initial Key Generation:**

1. Dual-person control (2 authorized personnel)
2. HSM initialization in secure facility
3. Key generation witnessed and logged
4. Key backup to offline secure storage
5. Verification of key integrity
6. Documentation signed by witnesses

### 12.2 Incident Response

**Key Compromise Suspected:**

1. Immediately disable affected key (< 1 hour)
2. Generate new key in HSM
3. Issue emergency rotation notification
4. Audit all signatures with compromised key
5. Document incident in security log
6. Review IAM permissions

### 12.3 Audit Requirements

**Quarterly Reviews:**
- Key usage statistics
- Rotation compliance
- Algorithm deprecation status
- Failed signature attempts
- IAM permission changes

**Annual Reviews:**
- Full cryptographic policy review
- NIST/IETF standard updates
- HSM certification status
- Quantum resistance assessment

---

## 13. References

**NIST Publications:**
- FIPS 140-2: Security Requirements for Cryptographic Modules
- FIPS 180-4: Secure Hash Standard (SHA)
- FIPS 186-5: Digital Signature Standard (DSS)
- SP 800-57 Part 1: Key Management (Recommendation)
- SP 800-90A: Random Number Generation
- SP 800-131A: Transitions for Crypto Algorithms

**IETF Standards:**
- RFC 8017: PKCS #1 v2.2 (RSA-PSS)
- RFC 8785: JSON Canonicalization Scheme
- RFC 8446: TLS 1.3
- RFC 4122: UUID Generation

**Industry Standards:**
- PCI-DSS 4.0: Payment Card Industry Data Security Standard
- SOC 2: Service Organization Control

---

## 14. Change Management

**Version History:**

| Version | Date | Changes | Approved By |
|---------|------|---------|-------------|
| 1.0 | 2026-02-15 | Initial policy | Security Architecture Board |

**Change Procedure:**

1. Security impact assessment
2. Threat model update
3. Implementation plan
4. Backward compatibility analysis
5. Approval by Security Architecture Board
6. Version increment
7. Communication to stakeholders

**Emergency Changes:**

- Algorithm compromise: Immediate deprecation
- NIST advisory: 7-day response
- Zero-day: 24-hour mitigation plan

---

## 15. Enforcement

**Mandatory Compliance:**

All implementations of the Override & Decision Integrity Substrate MUST comply with this policy. Non-compliance is a security incident requiring immediate remediation.

**Validation:**
- Automated compliance checks in CI/CD
- Quarterly security audits
- Penetration testing (annual)
- Code review for crypto changes

**Penalties:**
- Development freeze until remediation
- Escalation to Security Architecture Board
- Incident report required

---

**END OF CRYPTOGRAPHIC PARAMETER POLICY v1.0**
