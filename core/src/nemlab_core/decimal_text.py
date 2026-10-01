"""Exact ``BigDecimal`` behaviour for request decimal strings.

Java's ``new BigDecimal(String)`` rejects inputs Python's ``Decimal`` accepts
(NaN, Infinity, surrounding whitespace), so parsing goes through the
BigDecimal grammar first. ``strip_trailing_zeros`` and ``to_plain_string``
replicate ``stripTrailingZeros().toPlainString()`` without context rounding —
Python's ``Decimal.normalize`` would round at 28 digits, which corrupts the
38-digit values the contract deliberately accepts.
"""

import re
from decimal import Decimal
from typing import cast

# BigDecimal grammar: optional sign, digits with optional fraction or leading
# fraction, optional exponent. No whitespace, NaN/Infinity, grouping or hex.
_GRAMMAR = re.compile(r"[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")

MAX_PRECISION = 38
MAX_SCALE = 18


def parse(value: str) -> Decimal:
    """Parse like ``new BigDecimal(value)``; reject what it rejects."""
    if not _GRAMMAR.fullmatch(value):
        raise ValueError(f"invalid decimal: {value!r}")
    return Decimal(value)


def precision(value: Decimal) -> int:
    """Java ``precision()``: digits of the unscaled value; zero counts as 1."""
    if value.is_zero():
        return 1
    return len(value.as_tuple().digits)


def scale(value: Decimal) -> int:
    """Java ``scale()``: decimal digits right of the point (negative for 1E+n)."""
    return -value.as_tuple().exponent  # type: ignore[operator]


def strip_trailing_zeros(value: Decimal) -> Decimal:
    """Java ``stripTrailingZeros()`` without ``Decimal.normalize`` rounding."""
    if value.is_zero():
        # Java drops the sign on zero: new BigDecimal("-0.00") is unsigned.
        return Decimal(0)
    t = value.as_tuple()
    digits = list(t.digits)
    stripped = 0
    while digits and digits[-1] == 0:
        digits.pop()
        stripped += 1
    return Decimal((t.sign, tuple(digits), cast("int", t.exponent) + stripped))


def to_plain_string(value: Decimal) -> str:
    """Java ``toPlainString()``: no exponent, and zero never carries a sign."""
    if value.is_zero():
        value = value.copy_abs()
    return format(value, "f")


def canonical_decimal(value: Decimal) -> str:
    return to_plain_string(strip_trailing_zeros(value))


def within_decimal_limits(value: Decimal) -> bool:
    """The shared ``precision <= 38 && |scale| <= 18`` field bound."""
    return precision(value) <= MAX_PRECISION and abs(scale(value)) <= MAX_SCALE
