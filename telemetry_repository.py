"""Exact persistence codecs; connection and repository operations follow later.

Canonical rational TEXT is opaque to SQLite numeric operations. Decode to
Fraction before mathematical comparison or arithmetic.
"""

import re
from fractions import Fraction


_CANONICAL_PROBABILITY = re.compile(r"(0|[1-9][0-9]*)/([1-9][0-9]*)")


def encode_probability(value: Fraction | None) -> str | None:
    """Encode an exact probability as reduced ``n/d`` TEXT, or SQL NULL.

    Decimal conversion respects the runtime's integer-string safety limit.
    """
    if value is None:
        return None
    if not isinstance(value, Fraction):
        raise TypeError("Probability must be a Fraction or None.")
    if not 0 <= value <= 1:
        raise ValueError("Probability must be in [0, 1].")
    return f"{value.numerator}/{value.denominator}"


def decode_probability(value: str | None) -> Fraction | None:
    """Decode only canonical ASCII ``n/d`` TEXT representing a value in [0, 1]."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("Stored probability must be a string or None.")
    match = _CANONICAL_PROBABILITY.fullmatch(value)
    if match is None:
        raise ValueError("Stored probability must use canonical ASCII n/d syntax.")
    probability = Fraction(int(match[1]), int(match[2]))
    if encode_probability(probability) != value:
        raise ValueError("Stored probability must be reduced canonical n/d TEXT.")
    return probability
