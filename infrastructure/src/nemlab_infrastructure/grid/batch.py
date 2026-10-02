"""``GridBatch`` — one normalised series-day on the provider source-label grid.

288 five-minute positions ``[00:00, 24:00)`` per NEM market day. ``VALUE``,
``MISSING`` (no row returned) and ``SOURCE_NULL`` (explicit null) stay
distinct — zeros are real observations, never substitutes for gaps.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum

from nemlab_core import decimal_text
from nemlab_core.prices import INTERVALS, Region
from nemlab_infrastructure.prices.batch import Kind, hash


class Metric(Enum):
    DEMAND = "demand"
    FLOW_IMPORTS = "flow_imports"
    FLOW_EXPORTS = "flow_exports"
    POWER = "power"

    @property
    def unit(self) -> str:
        return "MW"


@dataclass(frozen=True)
class Slot:
    kind: Kind
    value: Decimal | None

    def __post_init__(self) -> None:
        if (self.kind is Kind.VALUE) != (self.value is not None):
            raise ValueError("invalid slot state")
        if self.value is not None:
            if not self.value.is_finite() or not decimal_text.within_decimal_limits(
                self.value
            ):
                raise ValueError("nonfinite value")
            object.__setattr__(
                self, "value", decimal_text.strip_trailing_zeros(self.value)
            )


@dataclass(frozen=True)
class GridBatch:
    """One (region, metric, series, market_day) series — ``series`` is the
    empty string for single-series metrics and the fueltech for ``power``."""

    region: Region
    metric: Metric
    series: str
    day: date
    slots: tuple[Slot, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "slots", tuple(self.slots))
        if len(self.slots) != INTERVALS:
            raise ValueError("expected 288 normalised slots")
        if not isinstance(self.series, str) or len(self.series) > 80:
            raise ValueError("invalid series key")

    def count(self, kind: Kind) -> int:
        return sum(1 for slot in self.slots if slot.kind is kind)

    def complete(self) -> bool:
        return self.count(Kind.VALUE) == INTERVALS

    def content_hash(self) -> str:
        canonical = (
            f"oe-grid-v1|{self.metric.value}|{self.series}|MW|5m|source-label"
            f"|+10:00|{self.region.name}|{self.day}"
        )
        for slot in self.slots:
            value = (
                "" if slot.value is None else decimal_text.to_plain_string(slot.value)
            )
            canonical += f"|{slot.kind.name}:{value}"
        return hash(canonical)
