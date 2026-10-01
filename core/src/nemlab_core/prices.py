"""Complete-day price boundary — ports the Java ``PriceDay`` record.

Exact source decimals survive normalisation: prices stay ``Decimal`` here;
only the strategies convert to float at the arithmetic boundary.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum

from nemlab_core import numbers

NEM_OFFSET = timezone(timedelta(hours=10))
INTERVALS = 288
INTERVAL_SECONDS = 300


class Region(Enum):
    NSW1 = "NSW1"
    QLD1 = "QLD1"
    SA1 = "SA1"
    TAS1 = "TAS1"
    VIC1 = "VIC1"


@dataclass(frozen=True)
class Interval:
    region: Region
    start: datetime
    end: datetime
    price: Decimal

    def __post_init__(self) -> None:
        numbers.finite("price", float(self.price))

    @classmethod
    def from_end(cls, region: Region, end: datetime, price: Decimal) -> "Interval":
        return cls(region, end - timedelta(seconds=INTERVAL_SECONDS), end, price)


@dataclass(frozen=True)
class PriceDay:
    region: Region
    date: date
    intervals: tuple[Interval, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "intervals", tuple(self.intervals))
        if len(self.intervals) != INTERVALS:
            raise ValueError("require exactly 288 prices")
        start = datetime(
            self.date.year, self.date.month, self.date.day, tzinfo=NEM_OFFSET
        )
        for i, interval in enumerate(self.intervals):
            expected_start = start + timedelta(seconds=i * INTERVAL_SECONDS)
            expected_end = start + timedelta(seconds=(i + 1) * INTERVAL_SECONDS)
            if (
                interval.region is not self.region
                or interval.start != expected_start
                or interval.end != expected_end
            ):
                raise ValueError(f"wrong region or noncontiguous interval at index {i}")
