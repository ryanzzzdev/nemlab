"""``PriceBatch`` — a normalised day keeping missing observations and
explicit source nulls distinct (Java ``PriceBatch``)."""

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum

from nemlab_core import decimal_text
from nemlab_core.prices import (
    INTERVAL_SECONDS,
    INTERVALS,
    NEM_OFFSET,
    Interval,
    PriceDay,
    Region,
)


class Kind(Enum):
    VALUE = "VALUE"
    MISSING = "MISSING"
    SOURCE_NULL = "SOURCE_NULL"


@dataclass(frozen=True)
class Slot:
    kind: Kind
    price: Decimal | None

    def __post_init__(self) -> None:
        if (self.kind is Kind.VALUE) != (self.price is not None):
            raise ValueError("invalid slot state")
        if self.price is not None:
            if not self.price.is_finite() or not decimal_text.within_decimal_limits(
                self.price
            ):
                raise ValueError("nonfinite price")
            object.__setattr__(
                self, "price", decimal_text.strip_trailing_zeros(self.price)
            )


@dataclass(frozen=True)
class PriceBatch:
    region: Region
    day: date
    slots: tuple[Slot, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "slots", tuple(self.slots))
        if len(self.slots) != INTERVALS:
            raise ValueError("expected 288 normalised slots")

    def count(self, kind: Kind) -> int:
        return sum(1 for slot in self.slots if slot.kind is kind)

    def complete(self) -> bool:
        return self.count(Kind.VALUE) == INTERVALS

    def to_price_day(self) -> PriceDay:
        if not self.complete():
            raise ValueError("incomplete day cannot be simulated")
        start = datetime(self.day.year, self.day.month, self.day.day, tzinfo=NEM_OFFSET)
        intervals = tuple(
            Interval.from_end(
                self.region,
                start + timedelta(seconds=(i + 1) * INTERVAL_SECONDS),
                slot.price,  # type: ignore[arg-type]
            )
            for i, slot in enumerate(self.slots)
        )
        return PriceDay(self.region, self.day, intervals)

    def content_hash(self) -> str:
        canonical = (
            f"oe-price-v1|AUD/MWh|5m|interval-end|+10:00|{self.region.name}|{self.day}"
        )
        for slot in self.slots:
            price = (
                "" if slot.price is None else decimal_text.to_plain_string(slot.price)
            )
            canonical += f"|{slot.kind.name}:{price}"
        return hash(canonical)


def hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
