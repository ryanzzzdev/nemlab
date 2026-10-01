"""Unrounded totals recomputed from dispatch — ports Java ``Accounting``.

Summation replicates JDK ``DoubleStream.sum()`` compensated summation (the
Kahan-style ``sumWithCompensation`` loop) so totals match the Java figures to
their last bit rather than merely to the reconciliation tolerance.
"""

import math
from collections.abc import Iterable
from dataclasses import dataclass

from nemlab_core import numbers
from nemlab_core.battery import Battery, TradingCosts
from nemlab_core.dispatch import Dispatch
from nemlab_core.prices import INTERVALS, PriceDay


@dataclass(frozen=True)
class Accounting:
    imported_mwh: float
    exported_mwh: float
    charging_cost: float
    revenue: float
    fees: float
    degradation: float
    margin: float
    losses_mwh: float

    def __post_init__(self) -> None:
        for value in (
            self.imported_mwh,
            self.exported_mwh,
            self.charging_cost,
            self.revenue,
            self.fees,
            self.degradation,
            self.margin,
            self.losses_mwh,
        ):
            numbers.finite("accounting total", value)


def _compensated_sum(values: Iterable[float]) -> float:
    total = 0.0
    compensation = 0.0
    for value in values:
        tmp = value - compensation
        velvel = total + tmp
        compensation = (velvel - total) - tmp
        total = velvel
    return total + compensation


def calculate(
    battery: Battery, costs: TradingCosts, day: PriceDay, dispatch: Dispatch
) -> Accounting:
    if len(dispatch.intervals) != INTERVALS:
        raise ValueError("dispatch and price day lengths differ")
    purchases: list[float] = []
    sales: list[float] = []
    for i in range(INTERVALS):
        price = float(day.intervals[i].price)
        step = dispatch.intervals[i]
        purchases.append(
            numbers.finite("interval charging cost", price * step.imported_mwh)
        )
        sales.append(numbers.finite("interval revenue", price * step.exported_mwh))
    imported = _compensated_sum(step.imported_mwh for step in dispatch.intervals)
    exported = _compensated_sum(step.exported_mwh for step in dispatch.intervals)
    charging_cost = _compensated_sum(purchases)
    revenue = _compensated_sum(sales)
    fees = costs.import_fee * imported + costs.export_fee * exported
    degradation = costs.degradation_per_exported_mwh * exported
    losses = (1 - battery.efficiency.charge) * imported + (
        1 / battery.efficiency.discharge - 1
    ) * exported
    return Accounting(
        imported,
        exported,
        charging_cost,
        revenue,
        fees,
        degradation,
        revenue - charging_cost - fees - degradation,
        losses,
    )


def reconciles(expected: float, actual: float) -> bool:
    return (
        math.isfinite(expected)
        and math.isfinite(actual)
        and abs(expected - actual) <= 1e-6 + 1e-9 * max(abs(expected), abs(actual))
    )
