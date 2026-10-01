"""Ports of Java ``HindsightTest`` cases plus HiGHS budget/version probes."""

import math
import random
import time
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from nemlab_core import fixed, hindsight
from nemlab_core.battery import Battery, Efficiency, TradingCosts
from nemlab_core.hindsight import Limits, Status
from nemlab_core.prices import INTERVALS, NEM_OFFSET, PriceDay, Region
from nemlab_core.prices import Interval as PriceInterval
from nemlab_core.windows import ScheduleWindows

WINDOWS = ScheduleWindows(0, 1, 1, 2)
FREE = TradingCosts(0, 0, 0)


def battery(capacity, initial, charge, discharge, efficiency):
    return Battery(
        capacity, 0, capacity, initial, charge, discharge, charge, discharge, efficiency
    )


def ideal():
    return battery(1, 0, 12, 12, Efficiency(1, 1))


def prices(buy: float, sell: float) -> PriceDay:
    day = date(2026, 9, 11)
    start = datetime(day.year, day.month, day.day, tzinfo=NEM_OFFSET)
    values = tuple(
        PriceInterval.from_end(
            Region.NSW1,
            start + timedelta(seconds=(i + 1) * 300),
            Decimal(str(buy if i == 0 else sell if i == 1 else 0)),
        )
        for i in range(INTERVALS)
    )
    return PriceDay(Region.NSW1, day, values)


def solve(b: Battery, w: ScheduleWindows, c: TradingCosts, p: PriceDay):
    return hindsight.solve(b, w, c, p, Limits.standard())


def proven(outcome: hindsight.Outcome, expected: float) -> None:
    assert outcome.status is Status.OPTIMAL, outcome
    assert outcome.accounting is not None
    assert outcome.accounting.margin == pytest.approx(expected, abs=1e-6)
    assert outcome.upper_bound is not None
    assert outcome.upper_bound >= expected - 1e-7
    assert outcome.absolute_gap is not None
    assert 0 <= outcome.absolute_gap <= hindsight.GAP_TOLERANCE


@pytest.mark.parametrize(
    ("buy", "sell", "expected"),
    [(-30, 200, 230), (100, 10, 0), (0, 0, 0), (-30, -10, 20)],
)
def test_manual_price_optima(buy, sell, expected):
    r = solve(ideal(), WINDOWS, FREE, prices(buy, sell))
    proven(r, expected)
    baseline = fixed.run(ideal(), WINDOWS, FREE, prices(buy, sell))
    assert r.accounting.margin + 1e-6 >= baseline.accounting.margin


def test_fees_losses_and_connection_limit():
    proven(
        solve(
            battery(1, 0, 12, 12, Efficiency(1, 0.9)),
            WINDOWS,
            TradingCosts(2, 2, 10),
            prices(-30, 200),
        ),
        197.2,
    )
    proven(
        solve(
            Battery(1, 0, 1, 0, 12, 12, 12, 6, Efficiency(1, 1)),
            WINDOWS,
            FREE,
            prices(0, 100),
        ),
        50,
    )


def test_initial_inventory_and_zero_power_cannot_create_profit():
    proven(
        solve(battery(1, 1, 12, 12, Efficiency(1, 1)), WINDOWS, FREE, prices(0, 100)), 0
    )
    proven(
        solve(battery(1, 0, 0, 12, Efficiency(1, 1)), WINDOWS, FREE, prices(-30, 200)),
        0,
    )
    proven(
        solve(battery(1, 0, 12, 0, Efficiency(1, 1)), WINDOWS, FREE, prices(-30, 200)),
        0,
    )


def test_negative_prices_cannot_reward_simultaneous_energy_dissipation():
    r = solve(
        battery(1, 0, 12, 12, Efficiency.round_trip(0.81)),
        WINDOWS,
        FREE,
        prices(-100, -100),
    )
    # Only legitimate inter-interval cycling; no same-interval import/export.
    proven(r, 19)
    assert r.dispatch is not None
    for interval in r.dispatch.intervals:
        assert interval.imported_mwh == 0 or interval.exported_mwh == 0
    assert r.dispatch.intervals[-1].ending_energy_mwh == pytest.approx(0, abs=1e-7)


def test_tiny_exact_enumeration_across_every_feasible_binary_dispatch():
    rng = random.Random(10210)
    windows = ScheduleWindows(0, 2, 2, 4)
    for _ in range(40):
        original = prices(0, 0)
        entries = list(original.intervals)
        price = [0] * 4
        for i in range(4):
            price[i] = rng.randrange(81) - 40
            old = entries[i]
            entries[i] = PriceInterval.from_end(old.region, old.end, Decimal(price[i]))
        day = PriceDay(original.region, original.date, tuple(entries))
        best = 0
        for mask in range(16):
            c0, c1 = mask & 1, (mask >> 1) & 1
            d0, d1 = (mask >> 2) & 1, (mask >> 3) & 1
            if c0 + c1 > 1 or c0 + c1 != d0 + d1:
                continue
            best = max(
                best, -price[0] * c0 - price[1] * c1 + price[2] * d0 + price[3] * d1
            )
        # Unit capacities and energy balance form an integral flow polytope:
        # this enumeration is an exact oracle.
        result = solve(ideal(), windows, FREE, day)
        proven(result, best)
        baseline = fixed.run(ideal(), windows, FREE, day)
        assert result.accounting.margin + 1e-6 >= baseline.accounting.margin


def test_omitted_proof_is_never_reported_as_optimal():
    for limit in (Limits(0, 100), Limits(100, 0)):
        r = hindsight.solve(ideal(), WINDOWS, FREE, prices(-30, 200), limit)
        assert r.status is Status.NO_SOLUTION
        assert r.dispatch is None
        assert r.upper_bound is None
        assert r.absolute_gap is None


def test_feasible_timeout_missing_proof_or_large_gap_cannot_become_optimal():
    assert hindsight.can_claim_optimal(True, 0.001, False)
    assert not hindsight.can_claim_optimal(False, 0.001, False)
    assert not hindsight.can_claim_optimal(True, 0.001, True)
    assert not hindsight.can_claim_optimal(True, None, False)
    assert not hindsight.can_claim_optimal(True, 0.02, False)
    assert not hindsight.can_claim_optimal(True, math.nan, False)
    assert not hindsight.can_claim_optimal(True, -0.001, False)


def test_fractional_reference_cases_with_efficiency_and_fees():
    rng = random.Random(105)
    for _ in range(20):
        eta = 0.5 + rng.random() * 0.5
        purchase = rng.random() * 100 - 50
        sale = rng.random() * 200 - 50
        b = battery(2, 0.25, 12, 12, Efficiency(eta, eta))
        result = solve(b, WINDOWS, TradingCosts(2, 3, 4), prices(purchase, sale))
        # Import is limited to 1 MWh; a cycle exports eta squared, or the
        # optimum idles.
        optimum = max(0, (sale - 7) * eta * eta - purchase - 2)
        proven(result, optimum)


def test_large_numerical_allowance_is_feasible_but_not_optimal():
    result = solve(
        battery(1_000_000, 0, 12_000_000, 12_000_000, Efficiency(1, 1)),
        WINDOWS,
        FREE,
        prices(-30, 200),
    )
    assert result.status is Status.FEASIBLE_NOT_PROVEN, result
    assert result.dispatch is not None
    assert result.accounting is not None
    assert result.accounting.margin == pytest.approx(230_000_000, abs=1e-5)
    assert result.absolute_gap is not None and result.absolute_gap > 0.01


def test_numerical_failure_has_no_publishable_dispatch():
    # Double.MIN_VALUE is the smallest denormal (4.9e-324), not
    # sys.float_info.min; 12/12 divided by it overflows to infinity.
    r = solve(
        battery(1, 0, 12, 12, Efficiency(1, math.nextafter(0.0, 1.0))),
        WINDOWS,
        FREE,
        prices(0, 100),
    )
    assert r.status is Status.FAILED_VALIDATION
    assert r.dispatch is None


def test_dual_expression_is_an_upper_bound_even_with_nonoptimal_multipliers():
    buy = [0.0] * INTERVALS
    sell = [0.0] * INTERVALS
    buy[0] = -30
    sell[1] = 200
    # mu=0, lambda=0 gives the loose but valid upper bound 230.
    assert hindsight.dual_upper_bound(WINDOWS, buy, sell, 1, 1, 1, 0, 0) >= 230
    # Very poor multipliers still bound the optimum.
    assert hindsight.dual_upper_bound(WINDOWS, buy, sell, 1, 1, 1, 50, 30) >= 230


def test_iteration_budget_abort_never_publishes_unproven():
    # A single simplex iteration cannot certify a 192-variable LP; whatever
    # the solver returns, the outcome must not claim optimality without a gap.
    r = hindsight.solve(ideal(), WINDOWS, FREE, prices(-30, 200), Limits(5_000, 1))
    if r.status is Status.OPTIMAL:
        assert r.absolute_gap is not None and r.absolute_gap <= hindsight.GAP_TOLERANCE
        assert r.certificate_state == "OPTIMAL"
    else:
        assert r.status in (Status.NO_SOLUTION, Status.FEASIBLE_NOT_PROVEN)
        if r.status is Status.NO_SOLUTION:
            assert r.dispatch is None


def test_warm_solve_is_well_inside_the_cooperative_budget():
    # 288-interval LP + certificate must run far under the 5 s cooperative
    # budget (and the 15 s parent deadline); cold start is covered by the
    # first call in the suite.
    elapsed = []
    for _ in range(10):
        start = time.monotonic_ns()
        r = solve(ideal(), WINDOWS, FREE, prices(-30, 200))
        elapsed.append(time.monotonic_ns() - start)
        assert r.status is Status.OPTIMAL
    assert max(elapsed) < 1_000_000_000  # 1 s warm ceiling, 5 s is the contract


def test_limits_validation():
    for bad in ((-1, 1), (60_001, 1), (1, -1)):
        with pytest.raises(ValueError):
            Limits(*bad)
