"""
RFC 8785 JSON Canonicalization Scheme (JCS)
===========================================

Threat Model RC2: Canonicalization version locked

This module provides a deterministic JSON canonicalization compatible with RFC 8785
(JCS). It is intended for cryptographic hashing/signing and cross-language replay.

Normative guarantees:
- UTF-8 output
- Object member names are sorted lexicographically by Unicode code points
- Array order is preserved
- No insignificant whitespace
- Strings are encoded per JSON escaping rules (UTF-8, no ASCII-forcing)
- Numbers are serialized using a stable, JCS-aligned representation

IMPORTANT:
Python's built-in json.dumps is NOT fully RFC 8785-compliant for numbers (e.g.,
it may emit trailing `.0` or exponent zero-padding). This implementation avoids
those pitfalls.

Version: 1.1 (LOCKED)
Changing output format requires a formal version bump and cross-language corpus update.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from decimal import Decimal
from typing import Any, Iterable, Mapping, Sequence


class CanonicalizeError(Exception):
    """Raised when canonicalization fails."""


# =============================================================================
# Public API
# =============================================================================

JCS_VERSION = "JCS_1.1"


def canonicalize_rfc8785(value: Any) -> bytes:
    """
    Canonicalize a JSON-serializable value per RFC 8785 (JCS) and return UTF-8 bytes.
    """
    s = _canon_value(value)
    return s.encode("utf-8")


def canonicalize_str(value: Any) -> str:
    """Canonicalize and return a UTF-8 string."""
    return canonicalize_rfc8785(value).decode("utf-8")


def canonical_hash(value: Any, algorithm: str = "sha256") -> str:
    """Hash the canonicalized value and return hex digest."""
    h = hashlib.new(algorithm)
    h.update(canonicalize_rfc8785(value))
    return h.hexdigest()


def compute_classification_hash(
    *,
    role_matrix_version: str,
    materiality_table_version: str,
    request_role: str,
    materiality: str,
    direction: str,
    duration_cap_applied: int,
    required_approvals: Sequence[str],
    policy_id: str,
    tenant_id: str,
) -> str:
    """
    Compute a provably pure classification hash for defensibility.

    This MUST be a pure function: same inputs => same output.
    """
    payload = {
        "jcs_version": JCS_VERSION,
        "role_matrix_version": role_matrix_version,
        "materiality_table_version": materiality_table_version,
        "request_role": request_role,
        "materiality": materiality,
        "direction": direction,
        "duration_cap_applied": int(duration_cap_applied),
        "required_approvals": list(required_approvals),
        "policy_id": policy_id,
        "tenant_id": tenant_id,
    }
    return canonical_hash(payload, "sha256")


# =============================================================================
# Canonicalization internals
# =============================================================================

# Regex to normalize exponent formatting, e.g. "1e-06" -> "1e-6"
_EXP_RE = re.compile(r"e([+-])0+(\d+)$")


def _canon_value(v: Any) -> str:
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, str):
        # Use json.dumps for correct JSON string escaping, but force no spaces and UTF-8.
        return json.dumps(v, ensure_ascii=False, separators=(",", ":"))
    if isinstance(v, int):
        return str(v)
    if isinstance(v, Decimal):
        return _format_decimal(v)
    if isinstance(v, float):
        return _format_float(v)
    if isinstance(v, Mapping):
        return _canon_object(v)
    if isinstance(v, (list, tuple)):
        return _canon_array(v)

    raise CanonicalizeError(f"Unsupported type for canonicalization: {type(v).__name__}")


def _canon_object(obj: Mapping[str, Any]) -> str:
    # Keys must be strings per JSON
    for k in obj.keys():
        if not isinstance(k, str):
            raise CanonicalizeError("Object keys must be strings")

    items = []
    for k in sorted(obj.keys()):
        items.append(_canon_value(k) + ":" + _canon_value(obj[k]))
    return "{" + ",".join(items) + "}"


def _canon_array(arr: Sequence[Any]) -> str:
    return "[" + ",".join(_canon_value(x) for x in arr) + "]"


def _normalize_exponent(s: str) -> str:
    # Ensure lower-case 'e' and no leading zeros in exponent.
    if "E" in s:
        s = s.replace("E", "e")
    m = _EXP_RE.search(s)
    if m:
        s = _EXP_RE.sub(r"e\1\2", s)
    return s


def _strip_trailing_decimal_zeros(s: str) -> str:
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def _format_decimal(d: Decimal) -> str:
    # Disallow NaN/Infinity for JCS
    if not d.is_finite():
        raise CanonicalizeError("Non-finite Decimal is not allowed in canonical JSON")

    # Normalize -0 to 0
    if d == 0:
        return "0"

    # Use plain decimal if it can be expressed without exponent within JS fixed range,
    # otherwise use scientific.
    sign = "-" if d.is_signed() else ""
    ad = -d if d.is_signed() else d

    # Thresholds aligned with ECMAScript toString behavior:
    # - Use fixed for 1e-6 <= abs < 1e21, else scientific.
    if Decimal("1e-6") <= ad < Decimal("1e21"):
        s = format(ad, "f")
        s = _strip_trailing_decimal_zeros(s)
        return sign + s

    # Scientific: one digit before dot, trim trailing zeros
    s = format(ad.normalize(), "e")  # like 1.230000e+03
    # Trim mantissa zeros
    mant, exp = s.split("e")
    mant = _strip_trailing_decimal_zeros(mant)
    s = mant + "e" + exp
    s = _normalize_exponent(s)
    return sign + s


def _format_float(x: float) -> str:
    if not math.isfinite(x):
        raise CanonicalizeError("NaN/Infinity are not allowed in canonical JSON")

    # Normalize -0.0 to 0
    if x == 0.0:
        return "0"

    sign = "-" if math.copysign(1.0, x) < 0 else ""
    ax = abs(x)

    # ECMAScript-ish threshold:
    # fixed for 1e-6 <= abs < 1e21 else scientific
    if 1e-6 <= ax < 1e21:
        # Use a shortest-roundtrip representation, then force fixed form if it used exponent.
        # repr(x) is shortest roundtrip in Python; convert through Decimal for stable formatting.
        d = Decimal(repr(ax))
        s = format(d, "f")
        s = _strip_trailing_decimal_zeros(s)
        return sign + s

    # Scientific
    d = Decimal(repr(ax))
    s = format(d.normalize(), "e")
    mant, exp = s.split("e")
    mant = _strip_trailing_decimal_zeros(mant)
    s = mant + "e" + exp
    s = _normalize_exponent(s)
    return sign + s
