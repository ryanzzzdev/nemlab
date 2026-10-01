"""Both strategies plus diagnostics — ports Java ``SimulationComparison``.

Only an OPTIMAL hindsight outcome is a publishable comparison; ``validate``
re-checks every strategy dispatch and the optimality metadata independently.
"""

import math
from dataclasses import dataclass

from nemlab_core import fixed, hindsight, threshold
from nemlab_core.accounting import Accounting, calculate, reconciles
from nemlab_core.dispatch import Dispatch, validate_unrestricted
from nemlab_core.dispatch import validate as validate_dispatch
from nemlab_core.prices import PriceDay
from nemlab_core.request import Normalised
from nemlab_core.threshold import THRESHOLD_VERSION, Thresholds
from nemlab_core.windows import ScheduleWindows


@dataclass(frozen=True)
class ThresholdResult:
    """Optional all-day price-rule experiment; absent for requests without
    thresholds."""

    version: str
    thresholds: Thresholds
    dispatch: Dispatch
    accounting: Accounting


@dataclass(frozen=True)
class SimulationComparison:
    fixed_dispatch: Dispatch
    fixed_accounting: Accounting
    hindsight: hindsight.Outcome
    threshold: ThresholdResult | None


def run(
    p: Normalised, prices: PriceDay, limits: hindsight.Limits
) -> SimulationComparison:
    fixed_result = fixed.run(p.battery, p.windows, p.costs, prices)
    hindsight_outcome = hindsight.solve(p.battery, p.windows, p.costs, prices, limits)
    threshold_result = None
    if p.thresholds is not None:
        dispatch = threshold.plan(p.battery, p.thresholds, prices)
        threshold_result = ThresholdResult(
            THRESHOLD_VERSION,
            p.thresholds,
            dispatch,
            calculate(p.battery, p.costs, prices, dispatch),
        )
    return SimulationComparison(
        fixed_result.dispatch,
        fixed_result.accounting,
        hindsight_outcome,
        threshold_result,
    )


def validate(
    comparison: SimulationComparison,
    p: Normalised,
    prices: PriceDay,
    limits: hindsight.Limits,
) -> None:
    h = comparison.hindsight
    if h is None or h.status is None:
        raise ValueError("missing hindsight outcome")
    if fixed.plan(p.battery, p.windows) != comparison.fixed_dispatch:
        raise ValueError("fixed policy mismatch")
    _validate_strategy(
        p, prices, comparison.fixed_dispatch, comparison.fixed_accounting, p.windows
    )
    t = comparison.threshold
    if t is None:
        if p.thresholds is not None:
            raise ValueError("missing threshold experiment")
    else:
        if (
            p.thresholds is None
            or t.version != THRESHOLD_VERSION
            or t.thresholds is None
            or p.thresholds.charge_below != t.thresholds.charge_below
            or p.thresholds.discharge_above != t.thresholds.discharge_above
        ):
            raise ValueError("threshold experiment mismatch")
        if threshold.plan(p.battery, p.thresholds, prices) != t.dispatch:
            raise ValueError("threshold dispatch mismatch")
        _validate_strategy(p, prices, t.dispatch, t.accounting, None)
    for value in (h.solver_objective, h.upper_bound, h.absolute_gap):
        if value is not None and not math.isfinite(value):
            raise ValueError("nonfinite solver metadata")
    if h.limits != limits or h.elapsed_nanos < 0:
        raise ValueError("solver execution metadata mismatch")
    has_dispatch = h.status in (
        hindsight.Status.OPTIMAL,
        hindsight.Status.FEASIBLE_NOT_PROVEN,
    )
    if has_dispatch:
        assert h.dispatch is not None and h.accounting is not None
        _validate_strategy(p, prices, h.dispatch, h.accounting, p.windows)
    elif h.dispatch is not None or h.accounting is not None:
        raise ValueError("failed solver cannot publish dispatch")
    if h.status is hindsight.Status.OPTIMAL:
        gap, bound = h.absolute_gap, h.upper_bound
        assert h.accounting is not None
        if (
            h.solver_state != "OPTIMAL"
            or bound is None
            or not math.isfinite(bound)
            or gap is None
            or not math.isfinite(gap)
            or gap < 0
            or gap > hindsight.GAP_TOLERANCE
            or h.elapsed_nanos >= limits.milliseconds * 1_000_000
            or not reconciles(bound - h.accounting.margin, gap)
            or (
                h.accounting.margin + 0.01 < comparison.fixed_accounting.margin
                and not reconciles(
                    h.accounting.margin, comparison.fixed_accounting.margin
                )
            )
        ):
            raise ValueError("invalid optimality metadata")


def _validate_strategy(
    p: Normalised,
    prices: PriceDay,
    dispatch: Dispatch,
    actual: Accounting,
    windows: ScheduleWindows | None,
) -> None:
    if windows is None:
        validate_unrestricted(p.battery, dispatch)
    else:
        validate_dispatch(p.battery, windows, dispatch)
    expected = calculate(p.battery, p.costs, prices, dispatch)
    for e, a in zip(_values(expected), _values(actual), strict=True):
        if not reconciles(e, a):
            raise ValueError("accounting mismatch")


def _values(a: Accounting) -> tuple[float, ...]:
    return (
        a.imported_mwh,
        a.exported_mwh,
        a.charging_cost,
        a.revenue,
        a.fees,
        a.degradation,
        a.margin,
        a.losses_mwh,
    )
