"""Numeric guards mirroring the Java ``Numbers`` helper."""

import math


def finite(field: str, value: float) -> float:
    if not math.isfinite(value):
        raise ValueError(f"{field} must be finite")
    return value


def nonnegative(field: str, value: float) -> float:
    finite(field, value)
    if value < 0:
        raise ValueError(f"{field} must be nonnegative")
    return value


def efficiency(field: str, value: float) -> float:
    finite(field, value)
    if value <= 0 or value > 1:
        raise ValueError(f"{field} must be in (0,1]")
    return value
