"""Physical site values — ports the Java ``Battery``, ``Efficiency`` and
``TradingCosts`` records. Aggregate MW/MWh; connection limits apply after
aggregation."""

import math
from dataclasses import dataclass

from nemlab_core import numbers


@dataclass(frozen=True)
class Efficiency:
    charge: float
    discharge: float

    def __post_init__(self) -> None:
        numbers.efficiency("charge efficiency", self.charge)
        numbers.efficiency("discharge efficiency", self.discharge)

    @classmethod
    def round_trip(cls, value: float) -> "Efficiency":
        leg = math.sqrt(numbers.efficiency("round-trip efficiency", value))
        return cls(leg, leg)


@dataclass(frozen=True)
class Battery:
    capacity_mwh: float
    minimum_mwh: float
    maximum_mwh: float
    initial_mwh: float
    charge_mw: float
    discharge_mw: float
    import_limit_mw: float
    export_limit_mw: float
    efficiency: Efficiency

    def __post_init__(self) -> None:
        numbers.nonnegative("capacity", self.capacity_mwh)
        numbers.nonnegative("minimum energy", self.minimum_mwh)
        numbers.nonnegative("maximum energy", self.maximum_mwh)
        numbers.nonnegative("initial energy", self.initial_mwh)
        if (
            self.capacity_mwh == 0
            or self.minimum_mwh > self.initial_mwh
            or self.initial_mwh > self.maximum_mwh
            or self.maximum_mwh > self.capacity_mwh
        ):
            raise ValueError("invalid energy bounds")
        numbers.nonnegative("charge power", self.charge_mw)
        numbers.nonnegative("discharge power", self.discharge_mw)
        numbers.nonnegative("import limit", self.import_limit_mw)
        numbers.nonnegative("export limit", self.export_limit_mw)

    def effective_charge_mw(self) -> float:
        return min(self.charge_mw, self.import_limit_mw)

    def effective_discharge_mw(self) -> float:
        return min(self.discharge_mw, self.export_limit_mw)


@dataclass(frozen=True)
class TradingCosts:
    """AUD per grid-side imported/exported MWh."""

    import_fee: float
    export_fee: float
    degradation_per_exported_mwh: float

    def __post_init__(self) -> None:
        numbers.nonnegative("import fee", self.import_fee)
        numbers.nonnegative("export fee", self.export_fee)
        numbers.nonnegative("degradation", self.degradation_per_exported_mwh)
