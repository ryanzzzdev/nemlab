"""Ports of Java ``SimulationComparisonTest`` cases."""

import math
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from nemlab_core import comparison, threshold
from nemlab_core.accounting import calculate
from nemlab_core.comparison import SimulationComparison, ThresholdResult
from nemlab_core.dispatch import Dispatch, Interval
from nemlab_core.hindsight import Limits, Outcome, Status
from nemlab_core.prices import INTERVALS, NEM_OFFSET, PriceDay, Region
from nemlab_core.prices import Interval as PriceInterval
from nemlab_core.request import (
    Costs,
    EfficiencyInput,
    Normalised,
    SimulationRequest,
    Site,
    ThresholdInput,
    Windows,
)
from nemlab_core.threshold import THRESHOLD_VERSION, Thresholds

# SimulationRequestTest.CLOCK: fixed 2026-09-20T00:00:00Z -> today 2026-09-20.
TODAY = date(2026, 9, 20)
LIMITS = Limits.standard()


def request() -> SimulationRequest:
    return SimulationRequest(
        Region.NSW1,
        date(2023, 9, 11),
        Site(*[Decimal(x) for x in ("2", "0", "2", "0", "1", "1", "1", "1")]),
        EfficiencyInput(None, None, Decimal("0.9")),
        Costs(*[Decimal(x) for x in ("2", "2", "10")]),
        Windows(600, 840, 1020, 1260),
    )


def parameters() -> Normalised:
    return request().normalise(today=TODAY)


def prices(p: Normalised) -> PriceDay:
    day = p.values.day
    assert day is not None
    start = datetime(day.year, day.month, day.day, tzinfo=NEM_OFFSET)
    values = tuple(
        PriceInterval.from_end(
            Region.NSW1,
            start + timedelta(seconds=(i + 1) * 300),
            Decimal(-30 if p.windows.can_charge(i) else 200),
        )
        for i in range(INTERVALS)
    )
    return PriceDay(Region.NSW1, day, values)


def test_validates_both_strategies_and_rejects_tampered_physical_outputs():
    p = parameters()
    day = prices(p)
    result = comparison.run(p, day, LIMITS)
    assert result.hindsight.status is Status.OPTIMAL
    comparison.validate(result, p, day, LIMITS)
    steps = list(result.hindsight.dispatch.intervals)
    steps[0] = Interval(1, 1, 0)
    h = result.hindsight
    broken = Outcome(
        h.status,
        h.solver_state,
        h.certificate_state,
        Dispatch(tuple(steps), h.dispatch.limiting_reason),
        h.accounting,
        h.solver_objective,
        h.upper_bound,
        h.absolute_gap,
        h.elapsed_nanos,
        h.limits,
        h.diagnostic,
    )
    with pytest.raises(ValueError):
        comparison.validate(
            SimulationComparison(
                result.fixed_dispatch, result.fixed_accounting, broken, None
            ),
            p,
            day,
            LIMITS,
        )


def test_rejects_unproven_expired_and_nonfinite_optimality_claims():
    p = parameters()
    day = prices(p)
    result = comparison.run(p, day, LIMITS)
    h = result.hindsight
    invalid = (
        Outcome(
            h.status,
            "FEASIBLE",
            h.certificate_state,
            h.dispatch,
            h.accounting,
            h.solver_objective,
            h.upper_bound,
            h.absolute_gap,
            h.elapsed_nanos,
            h.limits,
            None,
        ),
        Outcome(
            h.status,
            h.solver_state,
            h.certificate_state,
            h.dispatch,
            h.accounting,
            h.solver_objective,
            h.upper_bound,
            0.02,
            h.elapsed_nanos,
            h.limits,
            None,
        ),
        Outcome(
            h.status,
            h.solver_state,
            h.certificate_state,
            h.dispatch,
            h.accounting,
            h.solver_objective,
            h.upper_bound,
            h.absolute_gap,
            5_000_000_000,
            h.limits,
            None,
        ),
        Outcome(
            h.status,
            h.solver_state,
            h.certificate_state,
            h.dispatch,
            h.accounting,
            math.inf,
            h.upper_bound,
            h.absolute_gap,
            h.elapsed_nanos,
            h.limits,
            None,
        ),
    )
    for outcome in invalid:
        with pytest.raises(ValueError):
            comparison.validate(
                SimulationComparison(
                    result.fixed_dispatch, result.fixed_accounting, outcome, None
                ),
                p,
                day,
                LIMITS,
            )


def test_runs_and_validates_the_threshold_experiment_when_requested():
    r = request()
    with_t = SimulationRequest(
        r.region,
        r.day,
        r.site,
        r.efficiency,
        r.costs,
        r.windows,
        ThresholdInput(Decimal("30"), Decimal("150")),
    )
    p = with_t.normalise(today=TODAY)
    day = prices(p)
    result = comparison.run(p, day, LIMITS)
    assert result.threshold is not None
    assert result.threshold.version == THRESHOLD_VERSION
    assert result.threshold.thresholds == p.thresholds
    assert len(result.threshold.dispatch.intervals) == INTERVALS
    comparison.validate(result, p, day, LIMITS)
    t = result.threshold
    steps = list(t.dispatch.intervals)
    steps[0] = Interval(0, 0, steps[0].ending_energy_mwh + 1)
    tampered = ThresholdResult(
        t.version,
        t.thresholds,
        Dispatch(tuple(steps), t.dispatch.limiting_reason),
        t.accounting,
    )
    with pytest.raises(ValueError):
        comparison.validate(
            SimulationComparison(
                result.fixed_dispatch,
                result.fixed_accounting,
                result.hindsight,
                tampered,
            ),
            p,
            day,
            LIMITS,
        )
    with pytest.raises(ValueError):
        comparison.validate(
            SimulationComparison(
                result.fixed_dispatch, result.fixed_accounting, result.hindsight, None
            ),
            p,
            day,
            LIMITS,
        )


def test_rejects_unexpected_threshold_results_and_version_mismatch():
    p = parameters()
    day = prices(p)
    result = comparison.run(p, day, LIMITS)
    thresholds = Thresholds(Decimal("30"), Decimal("150"))
    dispatch = threshold.plan(p.battery, thresholds, day)
    unexpected = ThresholdResult(
        THRESHOLD_VERSION,
        thresholds,
        dispatch,
        calculate(p.battery, p.costs, day, dispatch),
    )
    with pytest.raises(ValueError):
        comparison.validate(
            SimulationComparison(
                result.fixed_dispatch,
                result.fixed_accounting,
                result.hindsight,
                unexpected,
            ),
            p,
            day,
            LIMITS,
        )
    r = request()
    p2 = SimulationRequest(
        r.region,
        r.day,
        r.site,
        r.efficiency,
        r.costs,
        r.windows,
        ThresholdInput(Decimal("30"), Decimal("150")),
    ).normalise(today=TODAY)
    with_result = comparison.run(p2, day, LIMITS)
    t = with_result.threshold
    assert t is not None
    wrong_version = ThresholdResult(
        "price-threshold-v0", t.thresholds, t.dispatch, t.accounting
    )
    with pytest.raises(ValueError):
        comparison.validate(
            SimulationComparison(
                with_result.fixed_dispatch,
                with_result.fixed_accounting,
                with_result.hindsight,
                wrong_version,
            ),
            p2,
            day,
            LIMITS,
        )


def test_preserves_failed_solver_diagnostics_without_dispatch():
    p = parameters()
    day = prices(p)
    result = comparison.run(p, day, LIMITS)
    failed = Outcome(
        Status.NO_SOLUTION,
        "NOT_RUN",
        "NOT_RUN",
        None,
        None,
        None,
        None,
        None,
        0,
        LIMITS,
        "No feasible point",
    )
    comparison.validate(
        SimulationComparison(
            result.fixed_dispatch, result.fixed_accounting, failed, None
        ),
        p,
        day,
        LIMITS,
    )
    false_failure = Outcome(
        Status.ERROR,
        "ERROR",
        "NOT_RUN",
        result.hindsight.dispatch,
        result.hindsight.accounting,
        None,
        None,
        None,
        0,
        LIMITS,
        None,
    )
    with pytest.raises(ValueError):
        comparison.validate(
            SimulationComparison(
                result.fixed_dispatch, result.fixed_accounting, false_failure, None
            ),
            p,
            day,
            LIMITS,
        )
