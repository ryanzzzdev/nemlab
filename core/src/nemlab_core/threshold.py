"""Visitor thresholds and the all-day price rule — ports Java ``Thresholds``
and ``PriceThreshold``."""

from dataclasses import dataclass
from decimal import Decimal

from nemlab_core import dispatch as dispatch_module
from nemlab_core import numbers
from nemlab_core.battery import Battery
from nemlab_core.dispatch import Dispatch, Interval, Limit
from nemlab_core.prices import INTERVALS, PriceDay

THRESHOLD_VERSION = "price-threshold-v1"


@dataclass(frozen=True)
class Thresholds:
    """Fixed visitor thresholds in AUD/MWh; charge must be below discharge."""

    charge_below: Decimal
    discharge_above: Decimal

    def __post_init__(self) -> None:
        numbers.finite("charge threshold", float(self.charge_below))
        numbers.finite("discharge threshold", float(self.discharge_above))
        if self.charge_below >= self.discharge_above:
            raise ValueError("charge threshold must be below discharge threshold")


def plan(battery: Battery, thresholds: Thresholds, prices: PriceDay) -> Dispatch:
    """Idealised same-interval price rule: charge below the charge threshold,
    discharge above the discharge threshold, otherwise hold. Runs the whole
    day; never forces a terminal trade."""
    eta_c = battery.efficiency.charge
    eta_d = battery.efficiency.discharge
    charge_limit = battery.effective_charge_mw() / 12
    discharge_limit = battery.effective_discharge_mw() / 12
    energy = battery.initial_mwh
    intervals: list[Interval] = []
    for i in range(INTERVALS):
        price = prices.intervals[i].price
        charge = 0.0
        discharge = 0.0
        if price < thresholds.charge_below:
            charge = min(charge_limit, max(0, (battery.maximum_mwh - energy) / eta_c))
        elif price > thresholds.discharge_above:
            discharge = min(
                discharge_limit, max(0, (energy - battery.minimum_mwh) * eta_d)
            )
        energy += eta_c * charge - discharge / eta_d
        intervals.append(Interval(charge, discharge, energy))
    result = Dispatch(tuple(intervals), Limit.NOT_EVALUATED)
    dispatch_module.validate_unrestricted(battery, result)
    return result
