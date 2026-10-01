"""Ports of Java ``PriceThresholdTest`` cases."""

from collections.abc import Callable
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from nemlab_core import dispatch as dispatch_module
from nemlab_core import threshold
from nemlab_core.accounting import calculate
from nemlab_core.battery import Battery, Efficiency, TradingCosts
from nemlab_core.prices import INTERVALS, NEM_OFFSET, Interval, PriceDay, Region
from nemlab_core.threshold import Thresholds

THIRTY_150 = Thresholds(Decimal("30"), Decimal("150"))


def site(
    capacity,
    minimum,
    maximum,
    initial,
    charge,
    discharge,
    import_limit,
    export_limit,
    efficiency,
):
    return Battery(
        capacity,
        minimum,
        maximum,
        initial,
        charge,
        discharge,
        import_limit,
        export_limit,
        efficiency,
    )


def ideal():
    return site(1, 0, 1, 0.5, 12, 12, 12, 12, Efficiency(1, 1))


def day(price: Callable[[int], Decimal]) -> PriceDay:
    d = date(2026, 9, 11)
    start = datetime(d.year, d.month, d.day, tzinfo=NEM_OFFSET)
    values = tuple(
        Interval.from_end(
            Region.NSW1, start + timedelta(seconds=(i + 1) * 300), price(i)
        )
        for i in range(INTERVALS)
    )
    return PriceDay(Region.NSW1, d, values)


def flat(price: float) -> PriceDay:
    return day(lambda i: Decimal(str(price)))


@pytest.mark.parametrize("price", [30, 150])
def test_exact_threshold_equality_holds(price):
    dispatch = threshold.plan(ideal(), THIRTY_150, flat(price))
    for step in dispatch.intervals:
        assert step.imported_mwh == pytest.approx(0, abs=1e-9)
        assert step.exported_mwh == pytest.approx(0, abs=1e-9)
        assert step.ending_energy_mwh == pytest.approx(0.5, abs=1e-9)


def test_decimal_boundaries_are_exact():
    thresholds = Thresholds(Decimal("0.1"), Decimal("0.2"))
    equal = threshold.plan(ideal(), thresholds, day(lambda i: Decimal("0.1")))
    assert equal.intervals[0].imported_mwh == pytest.approx(0, abs=1e-9)
    below = threshold.plan(ideal(), thresholds, day(lambda i: Decimal("0.099")))
    assert below.intervals[0].imported_mwh > 0


def test_charges_below_and_discharges_above():
    prices = day(
        lambda i: (
            Decimal("10") if i == 0 else Decimal("200") if i == 1 else Decimal("50")
        )
    )
    dispatch = threshold.plan(ideal(), THIRTY_150, prices)
    assert dispatch.intervals[0].imported_mwh == pytest.approx(0.5, abs=1e-9)
    assert dispatch.intervals[0].ending_energy_mwh == pytest.approx(1, abs=1e-9)
    assert dispatch.intervals[1].exported_mwh == pytest.approx(1, abs=1e-9)
    assert dispatch.intervals[1].ending_energy_mwh == pytest.approx(0, abs=1e-9)
    a = calculate(ideal(), TradingCosts(0, 0, 0), prices, dispatch)
    assert a.imported_mwh == pytest.approx(0.5, abs=1e-9)
    assert a.exported_mwh == pytest.approx(1, abs=1e-9)
    assert a.margin == pytest.approx(195, abs=1e-9)  # 200*1 - 10*0.5


def test_ends_below_initial_energy_without_forced_trade():
    dispatch = threshold.plan(
        ideal(), THIRTY_150, day(lambda i: Decimal("200") if i < 2 else Decimal("50"))
    )
    assert dispatch.intervals[287].ending_energy_mwh == pytest.approx(0, abs=1e-9)
    dispatch_module.validate_unrestricted(ideal(), dispatch)


def test_holds_between_thresholds_all_day():
    dispatch = threshold.plan(ideal(), THIRTY_150, flat(50))
    assert dispatch.intervals[287].ending_energy_mwh == pytest.approx(0.5, abs=1e-9)
    assert all(s.imported_mwh == 0 and s.exported_mwh == 0 for s in dispatch.intervals)


def test_negative_thresholds_and_prices_work():
    thresholds = Thresholds(Decimal("-10"), Decimal("-5"))
    prices = day(
        lambda i: (
            Decimal("-50") if i == 0 else Decimal("0") if i == 1 else Decimal("-7")
        )
    )
    dispatch = threshold.plan(ideal(), thresholds, prices)
    assert dispatch.intervals[0].imported_mwh == pytest.approx(0.5, abs=1e-9)
    assert dispatch.intervals[1].exported_mwh == pytest.approx(1, abs=1e-9)
    assert dispatch.intervals[2].imported_mwh == pytest.approx(0, abs=1e-9)
    assert dispatch.intervals[2].exported_mwh == pytest.approx(0, abs=1e-9)


def test_repeats_cycles_across_the_day():
    b = site(0.5, 0, 0.5, 0, 6, 6, 6, 6, Efficiency(1, 1))  # .5 MWh per interval
    prices = day(lambda i: Decimal("0") if i % 2 == 0 else Decimal("200"))
    dispatch = threshold.plan(b, THIRTY_150, prices)
    for i, step in enumerate(dispatch.intervals):
        assert step.imported_mwh == pytest.approx(0.5 if i % 2 == 0 else 0, abs=1e-9)
        assert step.exported_mwh == pytest.approx(0 if i % 2 == 0 else 0.5, abs=1e-9)
    a = calculate(b, TradingCosts(0, 0, 0), prices, dispatch)
    assert a.imported_mwh == pytest.approx(72, abs=1e-9)
    assert a.exported_mwh == pytest.approx(72, abs=1e-9)
    assert a.margin == pytest.approx(14400, abs=1e-9)


def test_clamps_partial_intervals_at_energy_bounds():
    b = site(0.6, 0.1, 0.6, 0.5, 12, 12, 12, 12, Efficiency(1, 1))
    prices = day(
        lambda i: (
            Decimal("0") if i == 0 else Decimal("200") if i == 1 else Decimal("50")
        )
    )
    dispatch = threshold.plan(b, THIRTY_150, prices)
    assert dispatch.intervals[0].imported_mwh == pytest.approx(0.1, abs=1e-9)
    assert dispatch.intervals[0].ending_energy_mwh == pytest.approx(0.6, abs=1e-9)
    assert dispatch.intervals[1].exported_mwh == pytest.approx(0.5, abs=1e-9)
    assert dispatch.intervals[1].ending_energy_mwh == pytest.approx(0.1, abs=1e-9)


def test_full_and_empty_sites_do_not_trade():
    full = site(1, 0, 1, 1, 12, 12, 12, 12, Efficiency(1, 1))
    assert threshold.plan(full, THIRTY_150, flat(-100)).intervals[
        0
    ].imported_mwh == pytest.approx(0, abs=1e-9)
    empty = site(1, 0.4, 1, 0.4, 12, 12, 12, 12, Efficiency(1, 1))
    assert threshold.plan(empty, THIRTY_150, flat(1000)).intervals[
        0
    ].exported_mwh == pytest.approx(0, abs=1e-9)


def test_power_and_connection_limits_apply():
    limited = site(2, 0, 2, 0, 12, 12, 6, 3, Efficiency(1, 1))
    prices = day(
        lambda i: Decimal("0") if i < 4 else Decimal("200") if i == 4 else Decimal("50")
    )
    dispatch = threshold.plan(limited, THIRTY_150, prices)
    assert dispatch.intervals[0].imported_mwh == pytest.approx(
        0.5, abs=1e-9
    )  # 6 MW import limit
    assert dispatch.intervals[3].ending_energy_mwh == pytest.approx(2, abs=1e-9)
    assert dispatch.intervals[4].exported_mwh == pytest.approx(
        0.25, abs=1e-9
    )  # 3 MW export
    dead = site(2, 0, 2, 1, 0, 12, 12, 12, Efficiency(1, 1))
    assert threshold.plan(dead, THIRTY_150, flat(-50)).intervals[
        0
    ].imported_mwh == pytest.approx(0, abs=1e-9)


def test_losses_and_fees_can_erase_attractive_trades():
    thresholds = Thresholds(Decimal("35"), Decimal("40"))
    lossy = site(4, 0, 4, 0, 12, 12, 12, 12, Efficiency(0.8, 0.8))
    costs = TradingCosts(2, 2, 10)
    prices = day(
        lambda i: Decimal("29") if i < 4 else Decimal("41") if i == 4 else Decimal("37")
    )
    dispatch = threshold.plan(lossy, thresholds, prices)
    a = calculate(lossy, costs, prices, dispatch)
    assert a.imported_mwh == pytest.approx(4, abs=1e-9)
    assert a.exported_mwh == pytest.approx(1, abs=1e-9)
    assert a.margin == pytest.approx(-95, abs=1e-9)  # 41 - 116 - 8 - 2 - 10
    assert a.margin < 0


def test_later_prices_do_not_change_earlier_dispatch():
    first = day(
        lambda i: (
            Decimal("0")
            if i < 100 and i % 2 == 0
            else Decimal("200")
            if i < 100
            else Decimal("50")
        )
    )
    second = day(
        lambda i: (
            Decimal("0")
            if i < 100 and i % 2 == 0
            else Decimal("200")
            if i < 100
            else Decimal("-500")
            if i % 3 == 0
            else Decimal("2000")
        )
    )
    a = threshold.plan(ideal(), THIRTY_150, first).intervals
    b = threshold.plan(ideal(), THIRTY_150, second).intervals
    for i in range(100):
        assert a[i] == b[i], f"interval {i}"


def test_rejects_unordered_or_missing_thresholds():
    with pytest.raises(ValueError):
        Thresholds(Decimal("150"), Decimal("30"))
    with pytest.raises(ValueError):
        Thresholds(Decimal("30"), Decimal("30"))
