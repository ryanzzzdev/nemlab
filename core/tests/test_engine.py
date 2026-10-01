"""Ports of Java ``BatteryEngineTest`` cases plus seeded invariants."""

import random
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from nemlab_core import dispatch as dispatch_module
from nemlab_core import fixed
from nemlab_core.accounting import reconciles
from nemlab_core.battery import Battery, Efficiency, TradingCosts
from nemlab_core.dispatch import Dispatch, Interval, Limit
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


def run(b: Battery, buy: float, sell: float) -> fixed.SimulationResult:
    return fixed.run(b, WINDOWS, FREE, prices(buy, sell))


@pytest.mark.parametrize(
    "buy,sell,margin", [(-30, 200, 230), (100, 10, -90), (0, 0, 0), (-30, -10, 20)]
)
def test_reference_prices(buy, sell, margin):
    result = run(ideal(), buy, sell)
    assert result.accounting.imported_mwh == pytest.approx(1, abs=1e-9)
    assert result.accounting.exported_mwh == pytest.approx(1, abs=1e-9)
    assert result.accounting.margin == pytest.approx(margin, abs=1e-9)
    assert result.dispatch.intervals[0].ending_energy_mwh == pytest.approx(1, abs=1e-9)
    assert result.dispatch.intervals[287].ending_energy_mwh == pytest.approx(
        0, abs=1e-9
    )


def test_loss_and_fee_reference():
    result = fixed.run(
        battery(1, 0, 12, 12, Efficiency(1, 0.9)),
        WINDOWS,
        TradingCosts(2, 2, 10),
        prices(-30, 200),
    )
    a = result.accounting
    assert a.imported_mwh == pytest.approx(1, abs=1e-9)
    assert a.exported_mwh == pytest.approx(0.9, abs=1e-9)
    assert a.losses_mwh == pytest.approx(0.1, abs=1e-9)
    assert a.charging_cost == pytest.approx(-30, abs=1e-9)
    assert a.revenue == pytest.approx(180, abs=1e-9)
    assert a.fees == pytest.approx(3.8, abs=1e-9)
    assert a.degradation == pytest.approx(9, abs=1e-9)
    assert a.margin == pytest.approx(197.2, abs=1e-9)


def test_connection_limit_caps_the_whole_cycle():
    b = Battery(1, 0, 1, 0, 12, 12, 12, 6, Efficiency(1, 1))
    r = run(b, 0, 100)
    assert r.accounting.imported_mwh == pytest.approx(0.5, abs=1e-9)
    assert r.accounting.exported_mwh == pytest.approx(0.5, abs=1e-9)
    assert r.accounting.margin == pytest.approx(50, abs=1e-9)
    assert r.dispatch.limiting_reason is Limit.DISCHARGE_WINDOW


def test_idle_has_an_explanation():
    full = run(battery(1, 1, 12, 12, Efficiency(1, 1)), 0, 100)
    assert full.accounting.imported_mwh == pytest.approx(0, abs=1e-9)
    assert full.dispatch.intervals[-1].ending_energy_mwh == pytest.approx(1, abs=1e-9)
    assert full.dispatch.limiting_reason is Limit.ENERGY_HEADROOM
    disabled = run(battery(1, 0, 0, 12, Efficiency(1, 1)), -30, 200)
    assert disabled.accounting.margin == pytest.approx(0, abs=1e-9)
    assert disabled.dispatch.limiting_reason is Limit.CHARGE_WINDOW
    assert run(
        battery(1, 0, 12, 0, Efficiency(1, 1)), -30, 200
    ).accounting.imported_mwh == pytest.approx(0, abs=1e-9)


def test_partial_allocation_and_nonzero_initial_inventory():
    b = Battery(3, 0.5, 2.5, 1, 12, 12, 12, 12, Efficiency(1, 1))
    w = ScheduleWindows(0, 3, 5, 8)
    d = fixed.plan(b, w)
    assert d.intervals[0].imported_mwh == pytest.approx(1, abs=1e-9)
    assert d.intervals[1].imported_mwh == pytest.approx(0.5, abs=1e-9)
    assert d.intervals[2].imported_mwh == pytest.approx(0, abs=1e-9)
    assert d.intervals[4].exported_mwh == pytest.approx(0, abs=1e-9)
    assert d.intervals[5].exported_mwh == pytest.approx(1, abs=1e-9)
    assert d.intervals[6].exported_mwh == pytest.approx(0.5, abs=1e-9)
    assert d.intervals[-1].ending_energy_mwh == pytest.approx(1, abs=1e-9)


def test_split_efficiency_is_applied_once_per_leg():
    r = run(battery(2, 0.3, 12, 12, Efficiency.round_trip(0.81)), -30, 200)
    assert r.accounting.imported_mwh == pytest.approx(1, abs=1e-9)
    assert r.accounting.exported_mwh == pytest.approx(0.81, abs=1e-9)
    assert r.accounting.losses_mwh == pytest.approx(0.19, abs=1e-9)
    assert r.dispatch.intervals[-1].ending_energy_mwh == pytest.approx(0.3, abs=1e-9)


def test_price_permutation_and_costs_cannot_change_dispatch():
    first = run(ideal(), -30, 200)
    second = fixed.run(ideal(), WINDOWS, TradingCosts(500, 500, 500), prices(200, -30))
    assert first.dispatch == second.dispatch
    assert first.accounting.margin != second.accounting.margin


def test_seeded_randomised_physical_and_financial_checks():
    rng = random.Random(9341)
    for _ in range(200):
        capacity = 0.01 + rng.random() * 1000
        b = battery(
            capacity,
            capacity * rng.random(),
            rng.random() * 100,
            rng.random() * 100,
            Efficiency.round_trip(0.5 + rng.random() * 0.5),
        )
        w = ScheduleWindows(60, 170, 200, 280)
        template = prices(0, 0)
        observations = tuple(
            PriceInterval.from_end(
                Region.NSW1, iv.end, Decimal(str(rng.random() * 600 - 200))
            )
            for iv in template.intervals
        )
        day = PriceDay(Region.NSW1, template.date, observations)
        costs = TradingCosts(2, 3, 4)
        r = fixed.run(b, w, costs, day)
        energy = b.initial_mwh
        bought = sold = money = 0.0
        for i in range(INTERVALS):
            step = r.dispatch.intervals[i]
            c, d = step.imported_mwh, step.exported_mwh
            assert c == 0 or d == 0
            assert c <= b.effective_charge_mw() / 12 + 1e-9
            assert d <= b.effective_discharge_mw() / 12 + 1e-9
            assert w.can_charge(i) or c == 0
            assert w.can_discharge(i) or d == 0
            energy += c * b.efficiency.charge - d / b.efficiency.discharge
            assert b.minimum_mwh - 1e-8 <= energy <= b.maximum_mwh + 1e-8
            assert energy == pytest.approx(step.ending_energy_mwh, abs=1e-8)
            bought += c
            sold += d
            price = float(day.intervals[i].price)
            money += (price - 3 - 4) * d - (price + 2) * c
        assert energy == pytest.approx(b.initial_mwh, abs=1e-8)
        assert r.accounting.margin == pytest.approx(money, abs=1e-7)
        assert r.accounting.losses_mwh == pytest.approx(bought - sold, abs=1e-7)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1])
def test_invalid_physical_inputs(value):
    with pytest.raises(ValueError):
        battery(1, 0, value, 12, Efficiency(1, 1))
    with pytest.raises(ValueError):
        TradingCosts(value, 0, 0)


@pytest.mark.parametrize("value", [0, -1, 1.1, float("nan"), float("inf")])
def test_invalid_efficiency(value):
    with pytest.raises(ValueError):
        Efficiency.round_trip(value)
    with pytest.raises(ValueError):
        Efficiency(1, value)


def test_invalid_bounds_and_derived_overflow():
    with pytest.raises(ValueError):
        battery(0, 0, 1, 1, Efficiency(1, 1))
    with pytest.raises(ValueError):
        battery(1, 2, 1, 1, Efficiency(1, 1))
    with pytest.raises(ValueError):
        Battery(1, 0.5, 1, 0.2, 1, 1, 1, 1, Efficiency(1, 1))
    with pytest.raises(ValueError):
        fixed.plan(
            battery(
                1, 0, 12, 12, Efficiency(1, float.fromhex("0x0.0000000000001p-1022"))
            ),
            WINDOWS,
        )
    with pytest.raises(ValueError):
        run(battery(100, 0, 1200, 1200, Efficiency(1, 1)), float("inf"), 0)


@pytest.mark.parametrize(
    "a,b,c,d",
    [(0, 0, 1, 2), (0, 3, 2, 4), (10, 12, 0, 2), (-1, 1, 2, 3), (0, 1, 2, 289)],
)
def test_rejects_unsupported_windows(a, b, c, d):
    with pytest.raises(ValueError):
        ScheduleWindows(a, b, c, d)


def test_minute_boundaries_include_midnight_but_reject_misalignment():
    assert ScheduleWindows.minutes(600, 840, 1020, 1440) == ScheduleWindows(
        120, 168, 204, 288
    )
    with pytest.raises(ValueError):
        ScheduleWindows.minutes(601, 840, 1020, 1440)


def test_price_day_rejects_gaps_duplicates_wrong_regions_and_wrong_durations():
    good = prices(0, -1)
    with pytest.raises(ValueError):
        PriceDay(good.region, good.date, good.intervals[:-1])
    original = good.intervals[1]
    variants = [
        good.intervals[0],
        PriceInterval(Region.QLD1, original.start, original.end, original.price),
        PriceInterval(
            original.region,
            original.start,
            original.end + timedelta(seconds=1),
            original.price,
        ),
        PriceInterval(
            original.region,
            original.start + timedelta(seconds=300),
            original.end + timedelta(seconds=300),
            original.price,
        ),
    ]
    for bad_interval in variants:
        bad = list(good.intervals)
        bad[1] = bad_interval
        with pytest.raises(ValueError):
            PriceDay(good.region, good.date, tuple(bad))
    with pytest.raises(ValueError):
        PriceDay(good.region, good.date + timedelta(days=1), good.intervals)
    with pytest.raises(ValueError):
        PriceInterval.from_end(good.region, good.intervals[0].end, Decimal("1e999"))


def test_market_day_is_always_fixed_offset_including_sydney_dst():
    # 2026-10-04 is a Sydney DST change day; NEM stays fixed UTC+10 with 288 slots.
    day = date(2026, 10, 4)
    start = datetime(day.year, day.month, day.day, tzinfo=NEM_OFFSET)
    exact = Decimal("-0.123456789123456789")
    entries = tuple(
        PriceInterval.from_end(
            Region.NSW1, start + timedelta(seconds=(i + 1) * 300), exact
        )
        for i in range(INTERVALS)
    )
    price_day = PriceDay(Region.NSW1, day, entries)
    assert price_day.intervals[-1].end - price_day.intervals[0].start == timedelta(
        hours=24
    )
    assert price_day.intervals[0].price == exact


def test_validator_rejects_tampered_dispatch():
    good = fixed.plan(ideal(), WINDOWS)
    variants = [
        {0: Interval(1, 0, 0.8)},  # false energy
        {0: Interval(2, 0, 2)},  # power and capacity
        {0: Interval(1, 0.1, 0.9)},  # simultaneous
        {5: Interval(0.1, 0, 0.1)},  # outside window
    ]
    for edits in variants:
        intervals = list(good.intervals)
        for i, step in edits.items():
            intervals[i] = step
        with pytest.raises(ValueError):
            dispatch_module.validate(
                ideal(), WINDOWS, Dispatch(tuple(intervals), good.limiting_reason)
            )
    unsold = [good.intervals[0]] + [Interval(0, 0, 1)] * (INTERVALS - 1)
    with pytest.raises(ValueError):
        dispatch_module.validate(
            ideal(), WINDOWS, Dispatch(tuple(unsold), good.limiting_reason)
        )
    with pytest.raises(ValueError):
        dispatch_module.validate(ideal(), WINDOWS, Dispatch((), Limit.ENERGY_HEADROOM))


def test_validator_checks_each_interval_balance_as_well_as_cumulative():
    b = battery(1, 0.5, 0, 0, Efficiency(1, 1))
    good = fixed.plan(b, WINDOWS)
    intervals = list(good.intervals)
    intervals[0] = Interval(0, 0, 0.5 + 8e-8)
    intervals[1] = Interval(0, 0, 0.5 - 8e-8)
    with pytest.raises(ValueError):
        dispatch_module.validate(
            b, WINDOWS, Dispatch(tuple(intervals), good.limiting_reason)
        )


def test_accounting_tolerance_rejects_material_errors_and_nonfinite():
    assert reconciles(197.2, 197.2 + 1e-7)
    assert not reconciles(197.2, 197.21)
    assert not reconciles(float("nan"), 0)


@pytest.mark.parametrize("day_text", ["2023-09-11", "2026-09-11"])
def test_sampled_oe_days(day_text):
    from pathlib import Path

    day = date.fromisoformat(day_text)
    lines = (
        (
            Path(__file__).parents[2]
            / "reference/java/core/src/test/resources/prices"
            / f"{day_text}.csv"
        )
        .read_text()
        .splitlines()
    )
    entries = tuple(
        PriceInterval.from_end(
            Region.NSW1,
            datetime.fromisoformat(line.split(",")[0]),
            Decimal(line.split(",")[1]),
        )
        for line in lines[1:]
    )
    price_day = PriceDay(Region.NSW1, day, entries)
    b = battery(2, 0, 1, 1, Efficiency.round_trip(0.9))
    r = fixed.run(b, ScheduleWindows.minutes(600, 840, 1020, 1260), FREE, price_day)
    # Independent decimal dot product from source prices and returned dispatch.
    expected = Decimal(0)
    for i in range(INTERVALS):
        d = r.dispatch.intervals[i]
        expected += entries[i].price * (
            Decimal(str(d.exported_mwh)) - Decimal(str(d.imported_mwh))
        )
    assert r.accounting.margin == pytest.approx(float(expected), abs=1e-8)
    assert r.dispatch.intervals[-1].ending_energy_mwh == pytest.approx(0, abs=1e-9)
    import math

    assert r.accounting.imported_mwh == pytest.approx(2 / math.sqrt(0.9), abs=1e-9)
    assert r.accounting.exported_mwh == pytest.approx(2 * math.sqrt(0.9), abs=1e-9)
