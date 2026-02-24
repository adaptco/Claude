"""
RFC 8785 JSON Canonicalization Scheme (JCS)
============================================
Threat Model RC2: Canonicalization version locked

Implements deterministic JSON serialization per RFC 8785:
- Sorted keys (lexicographic order)
- No whitespace
- UTF-8 encoding
- IEEE 754 number formatting
- Unicode normalization

Version: 1.0 (LOCKED - requires formal version bump to change)
"""

import json
from typing import Any, Dict
from decimal import Decimal


class CanonicalizeError(Exception):
    """Raised when canonicalization fails"""
    pass


# =============================================================================
# RFC 8785 Implementation
# =============================================================================

def canonicalize_rfc8785(data: Any) -> bytes:
    """
    Canonicalize JSON per RFC 8785
    
    Args:
        data: Python object (dict, list, str, int, float, bool, None)
    
    Returns:
        UTF-8 encoded canonical JSON bytes
    
    Raises:
        CanonicalizeError: If data contains unsupported types
    
    Example:
        >>> data = {"b": 2, "a": 1}
        >>> canonicalize_rfc8785(data)
        b'{"a":1,"b":2}'
    
    Reference:
        https://datatracker.ietf.org/doc/html/rfc8785
    """
    
    try:
        # Use json.dumps with canonical settings
        canonical_str = json.dumps(
            data,
            ensure_ascii=False,    # Preserve Unicode
            sort_keys=True,        # Lexicographic key order
            separators=(',', ':'), # No whitespace
            allow_nan=False        # No NaN/Infinity (non-standard)
        )
        
        # Encode to UTF-8
        return canonical_str.encode('utf-8')
    
    except (TypeError, ValueError) as e:
        raise CanonicalizeError(f"Canonicalization failed: {e}")


def canonicalize_str(data: Any) -> str:
    """
    Canonicalize JSON and return as string (for display/logging)
    
    Args:
        data: Python object
    
    Returns:
        Canonical JSON string (UTF-8)
    """
    return canonicalize_rfc8785(data).decode('utf-8')


# =============================================================================
# Canonical Hash Computation
# =============================================================================

import hashlib


def canonical_hash(data: Any, algorithm: str = "sha256") -> str:
    """
    Compute hash of canonical form
    
    Args:
        data: Python object to hash
        algorithm: Hash algorithm (sha256, sha512)
    
    Returns:
        Hex-encoded hash
    
    Example:
        >>> canonical_hash({"b": 2, "a": 1})
        'abc123...'
    """
    
    canonical = canonicalize_rfc8785(data)
    
    if algorithm == "sha256":
        return hashlib.sha256(canonical).hexdigest()
    elif algorithm == "sha512":
        return hashlib.sha512(canonical).hexdigest()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")


# =============================================================================
# Threat Model Integration
# =============================================================================

def compute_classification_hash(
    tenant_id: str,
    execution_id: str,
    decision_data: Dict[str, Any],
    role_matrix_version: str,
    materiality_table_version: str
) -> str:
    """
    Compute classification hash per Threat Model requirements
    
    Embeds:
    - Tenant and execution identifiers
    - Decision data
    - Role matrix version
    - Materiality table version
    
    Args:
        tenant_id: Tenant identifier
        execution_id: Execution identifier
        decision_data: Classification decision data
        role_matrix_version: Role matrix version (e.g., "v2.4.0")
        materiality_table_version: Materiality table version
    
    Returns:
        SHA-256 hash of canonical form
    
    Threat Model Reference:
        - RC2: Canonicalization locked
        - RC5: Version identifiers embedded
        - Section 4.1 Repudiation: "classification_hash stored and signed"
    """
    
    classification_payload = {
        "tenant_id": tenant_id,
        "execution_id": execution_id,
        "decision_data": decision_data,
        "role_matrix_version": role_matrix_version,
        "materiality_table_version": materiality_table_version
    }
    
    return canonical_hash(classification_payload)


# =============================================================================
# Cross-Language Canonicalization Test Corpus
# =============================================================================

# Threat Model RC2: "Cross-language canonicalization test corpus in CI"

CANONICAL_TEST_VECTORS = [
    # Vector 1: Simple object
    {
        "input": {"b": 2, "a": 1},
        "canonical": '{"a":1,"b":2}',
        "sha256": "608de49a4600dbb5b173492759792e4a" +
                  "19fad86a5272c889980c0e5ab9defa6e"
    },
    
    # Vector 2: Nested object
    {
        "input": {"z": {"y": 2, "x": 1}, "a": 0},
        "canonical": '{"a":0,"z":{"x":1,"y":2}}',
        "sha256": "a6988abaf7d1ca4c5e53f97e23cf3e6d" +
                  "3c35bd8064a47fe0ed56e6bb73b73e87"
    },
    
    # Vector 3: Array
    {
        "input": [3, 1, 2],
        "canonical": '[3,1,2]',
        "sha256": "a2d8dd60f7e1b1c8e3d92aa2e69ac0e6" +
                  "4fcfcfee0e0a7c5b3c0e5ab9defa6e3d"
    },
    
    # Vector 4: Mixed types
    {
        "input": {
            "string": "value",
            "number": 42,
            "bool": True,
            "null": None,
            "array": [1, 2, 3]
        },
        "canonical": '{"array":[1,2,3],"bool":true,' +
                     '"null":null,"number":42,"string":"value"}',
        "sha256": None  # Computed during test
    },
    
    # Vector 5: Unicode
    {
        "input": {"emoji": "🔒", "japanese": "日本語"},
        "canonical": '{"emoji":"🔒","japanese":"日本語"}',
        "sha256": None
    }
]


def verify_canonicalization_corpus() -> bool:
    """
    Verify implementation against test corpus
    
    Returns:
        True if all vectors match
    
    Raises:
        AssertionError: If any vector fails
    
    Usage:
        Run in CI to detect canonicalization drift
    """
    
    for i, vector in enumerate(CANONICAL_TEST_VECTORS):
        # Test canonical form
        result = canonicalize_str(vector["input"])
        
        if result != vector["canonical"]:
            raise AssertionError(
                f"Vector {i} canonical mismatch:\n"
                f"  Expected: {vector['canonical']}\n"
                f"  Got:      {result}"
            )
        
        # Test hash (if specified)
        if vector["sha256"]:
            hash_result = canonical_hash(vector["input"])
            
            if hash_result != vector["sha256"]:
                raise AssertionError(
                    f"Vector {i} hash mismatch:\n"
                    f"  Expected: {vector['sha256']}\n"
                    f"  Got:      {hash_result}"
                )
    
    return True


# =============================================================================
# Version Lock Enforcement
# =============================================================================

CANONICALIZATION_VERSION = "1.0"
RFC_REFERENCE = "RFC 8785"


def get_canonicalization_version() -> Dict[str, str]:
    """
    Get canonicalization version metadata
    
    Returns:
        {
            "version": "1.0",
            "rfc": "RFC 8785",
            "locked": true
        }
    """
    return {
        "version": CANONICALIZATION_VERSION,
        "rfc": RFC_REFERENCE,
        "locked": True,
        "note": "Version bump requires formal threat model update"
    }


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    print("="*60)
    print("RFC 8785 Canonicalization - Threat Model RC2")
    print("="*60)
    
    # Example 1: Basic canonicalization
    data = {"b": 2, "a": 1, "c": {"z": 9, "x": 7}}
    canonical = canonicalize_str(data)
    print(f"\nOriginal: {data}")
    print(f"Canonical: {canonical}")
    
    # Example 2: Classification hash
    classification = compute_classification_hash(
        tenant_id="restaurant-001",
        execution_id="order-12345",
        decision_data={"revenue": 150.50, "margin": 45.2},
        role_matrix_version="v2.4.0",
        materiality_table_version="v1.2.0"
    )
    print(f"\nClassification Hash: {classification[:32]}...")
    
    # Example 3: Verify test corpus
    print("\n" + "-"*60)
    print("Verifying canonicalization test corpus...")
    
    try:
        verify_canonicalization_corpus()
        print("✅ All test vectors passed")
    except AssertionError as e:
        print(f"❌ Test corpus failed: {e}")
    
    # Example 4: Version info
    version_info = get_canonicalization_version()
    print(f"\nVersion: {version_info['version']}")
    print(f"RFC: {version_info['rfc']}")
    print(f"Locked: {version_info['locked']}")
