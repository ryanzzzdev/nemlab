"""NEM-088/089/090 — calibrated detector-v2 tests.

Hand-labelled cases for the frozen ``v2`` rules: negative-to-high price
reversals (exact thresholds, six-hour look-ahead, gaps, shared peaks),
grouped negative-price episodes (gap and cumulative limits, missing data),
and the unusual-demand-ramp baseline classification.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from nemlab_core.detectors import (
    EPISODE_MAX_GAP_INTERVALS,
    EPISODE_MAX_GAP_PRICE,
    EPISODE_MAX_TOTAL_GAP_INTERVALS,
    MIN_RUN_INTERVALS,
    RAMP_MIN_CLASS_DAYS,
    RAMP_MIN_COMPLETE_DAYS,
    REVERSAL_LOOKAHEAD_INTERVALS,
    Event,
    EventType,
    Interval,
    classify_demand_ramp,
    detect_negative_price_episodes,
    detect_price_reversals,
    nearest_rank,
    negative_price_run_scanner,
)

DAY = date(2023, 9, 4)
DAY2 = DAY + timedelta(days=1)


def _run(day: date, position: int, count: int, low: str) -> Event:
    return Event(
        type=EventType.NEGATIVE_PRICE_RUN,
        owner_day=day,
        start_position=position,
        interval_count=count,
        value=Decimal(low),
        edge_incomplete=False,
    )


def _grid(days: list[date], fill: Decimal | None) -> dict[int, Decimal | None]:
    return {d.toordinal() * 288 + p: fill for d in days for p in range(288)}


def _scan_negative(days: list[date], values: dict[int, Decimal | None]) -> list[Event]:
    scanner = negative_price_run_scanner()
    events = []
    for d in days:
        for p in range(288):
            events.extend(
                scanner.feed(Interval(d, p, values.get(d.toordinal() * 288 + p)))
            )
    events.extend(scanner.finish())
    return events


# -- reversals -----------------------------------------------------------------


def test_reversal_exact_thresholds() -> None:
    """Peak exactly at 300 and rise exactly at 300 both qualify."""
    grid = _grid([DAY], Decimal("50"))
    for i in range(10, 13):
        grid[DAY.toordinal() * 288 + i] = Decimal("-100")
    run = _run(DAY, 10, 3, "-100")
    # peak 300 exactly: rise = 300 - (-100) = 400 >= 300 -> qualifies
    grid[DAY.toordinal() * 288 + 40] = Decimal("300")
    detected = detect_price_reversals([run], grid.get)
    assert len(detected) == 1
    event = detected[0].event
    assert event.type is EventType.PRICE_REVERSAL
    assert event.value == Decimal("300")
    assert detected[0].detail["trough"] == "-100"
    assert detected[0].detail["peak"] == "300"
    assert detected[0].detail["peakPosition"] == 40


def test_reversal_peak_threshold_boundary() -> None:
    """Peak 299.99 fails the >= 300 peak rule even though the rise clears."""
    grid = _grid([DAY], Decimal("50"))
    run = _run(DAY, 10, 3, "-0.01")
    grid[DAY.toordinal() * 288 + 30] = Decimal("299.99")
    assert detect_price_reversals([run], grid.get) == []
    grid[DAY.toordinal() * 288 + 30] = Decimal("300")
    assert len(detect_price_reversals([run], grid.get)) == 1


def test_reversal_lookahead_boundary() -> None:
    """The look-ahead is exactly 72 intervals (6 h); a peak at 73 misses."""
    grid = _grid([DAY], Decimal("50"))
    run = _run(DAY, 10, 3, "-100")
    last_inside = 12 + REVERSAL_LOOKAHEAD_INTERVALS
    grid[DAY.toordinal() * 288 + last_inside] = Decimal("500")
    detected = detect_price_reversals([run], grid.get)
    assert detected[0].detail["peakPosition"] == last_inside
    # move the peak one interval past the window
    grid[DAY.toordinal() * 288 + last_inside] = Decimal("50")
    grid[DAY.toordinal() * 288 + last_inside + 1] = Decimal("500")
    assert detect_price_reversals([run], grid.get) == []


def test_reversal_high_before_low_does_not_count() -> None:
    """A high price before the run is not a reversal."""
    grid = _grid([DAY], Decimal("50"))
    grid[DAY.toordinal() * 288 + 5] = Decimal("2000")
    run = _run(DAY, 10, 3, "-100")
    assert detect_price_reversals([run], grid.get) == []


def test_reversal_gap_in_lookahead_withholds() -> None:
    grid = _grid([DAY], Decimal("50"))
    run = _run(DAY, 10, 3, "-100")
    grid[DAY.toordinal() * 288 + 40] = Decimal("2000")
    grid[DAY.toordinal() * 288 + 20] = None  # one missing interval
    assert detect_price_reversals([run], grid.get) == []


def test_reversal_incomplete_lookahead_at_window_edge() -> None:
    """A run ending near the evaluated edge lacks a full 6 h look-ahead."""
    grid = _grid([DAY], Decimal("50"))
    run = _run(DAY, 280, 3, "-100")
    for i in range(283, 288):
        grid[DAY.toordinal() * 288 + i] = Decimal("900")
    assert detect_price_reversals([run], grid.get) == []


def test_reversal_equal_peaks_earliest_wins() -> None:
    """Equal qualifying peaks resolve to the earliest interval."""
    grid = _grid([DAY], Decimal("50"))
    run = _run(DAY, 10, 3, "-100")
    grid[DAY.toordinal() * 288 + 40] = Decimal("800")
    grid[DAY.toordinal() * 288 + 60] = Decimal("800")
    detected = detect_price_reversals([run], grid.get)
    assert detected[0].detail["peakPosition"] == 40


def test_reversal_shared_peak_largest_rise_wins() -> None:
    """Two runs whose look-aheads share one peak: keep the deepest trough."""
    grid = _grid([DAY], Decimal("50"))
    run_a = _run(DAY, 10, 3, "-100")
    run_b = _run(DAY, 30, 3, "-500")
    grid[DAY.toordinal() * 288 + 50] = Decimal("2000")
    detected = detect_price_reversals([run_a, run_b], grid.get)
    assert len(detected) == 1
    assert detected[0].detail["trough"] == "-500"
    assert len(detected[0].linked) == 2  # both runs recorded as evidence
    members = detected[0].detail["memberRuns"]
    assert len(members) == 2


def test_reversal_cross_midnight() -> None:
    """A run crossing market-day midnight reverses into the next day."""
    grid = _grid([DAY, DAY2], Decimal("50"))
    run = _run(DAY, 284, 6, "-120")  # spans the boundary
    peak_index = DAY2.toordinal() * 288 + 30
    grid[peak_index] = Decimal("1200")
    detected = detect_price_reversals([run], grid.get)
    assert len(detected) == 1
    assert detected[0].detail["peakMarketDay"] == DAY2.isoformat()
    assert detected[0].detail["peakPosition"] == 30


def test_reversal_edge_incomplete_run_never_detected() -> None:
    grid = _grid([DAY, DAY2], Decimal("50"))
    run = _run(DAY, 280, 6, "-100")
    incomplete = Event(
        type=run.type,
        owner_day=run.owner_day,
        start_position=run.start_position,
        interval_count=run.interval_count,
        value=run.value,
        edge_incomplete=True,
    )
    grid[DAY2.toordinal() * 288 + 10] = Decimal("2000")
    assert detect_price_reversals([incomplete], grid.get) == []


def test_reversal_short_run_not_considered() -> None:
    grid = _grid([DAY], Decimal("50"))
    run = _run(DAY, 10, MIN_RUN_INTERVALS - 1, "-100")
    grid[DAY.toordinal() * 288 + 30] = Decimal("2000")
    assert detect_price_reversals([run], grid.get) == []


# -- episodes ------------------------------------------------------------------


def test_episode_exact_gap_limits() -> None:
    """Gap of exactly 3 intervals joins; 4 does not."""
    a = _run(DAY, 10, 3, "-20")
    grid = _grid([DAY, DAY2], Decimal("50"))
    for i in range(10, 13):
        grid[DAY.toordinal() * 288 + i] = Decimal("-20")
    # gap of exactly EPISODE_MAX_GAP_INTERVALS joins
    gap_start = 13 + EPISODE_MAX_GAP_INTERVALS
    b = _run(DAY, gap_start, 3, "-30")
    detected = detect_negative_price_episodes([a, b], grid.get)
    assert len(detected) == 1
    assert detected[0].detail["memberCount"] == 2
    # one interval wider -> no join
    b_far = _run(DAY, gap_start + 1, 3, "-30")
    assert detect_negative_price_episodes([a, b_far], grid.get) == []


def test_episode_gap_price_limit() -> None:
    a = _run(DAY, 10, 3, "-20")
    b = _run(DAY, 14, 3, "-30")  # one-interval gap at position 13
    grid = _grid([DAY], Decimal("50"))
    grid[DAY.toordinal() * 288 + 13] = EPISODE_MAX_GAP_PRICE  # exactly 50 joins
    assert len(detect_negative_price_episodes([a, b], grid.get)) == 1
    grid[DAY.toordinal() * 288 + 13] = EPISODE_MAX_GAP_PRICE + Decimal("0.01")
    assert detect_negative_price_episodes([a, b], grid.get) == []


def test_episode_gap_must_be_nonnegative() -> None:
    """An intervening negative observation extends the run — a would-be
    episode joining across it is rejected by the price ceiling anyway."""
    a = _run(DAY, 10, 3, "-20")
    b = _run(DAY, 14, 3, "-30")
    grid = _grid([DAY], Decimal("50"))
    grid[DAY.toordinal() * 288 + 13] = Decimal("-0.5")
    assert detect_negative_price_episodes([a, b], grid.get) == []


def test_episode_cumulative_gap_limit() -> None:
    """Three members joined by two gaps of 3 intervals = 6 (the cap)."""
    a = _run(DAY, 10, 3, "-20")
    b = _run(DAY, 16, 3, "-30")  # gap of 3 (positions 13-15)
    c = _run(DAY, 22, 3, "-40")  # gap of 3 (positions 19-21)
    grid = _grid([DAY], Decimal("50"))
    detected = detect_negative_price_episodes([a, b, c], grid.get)
    assert len(detected) == 1
    assert detected[0].detail["memberCount"] == 3
    assert detected[0].detail["gapMinutes"] == EPISODE_MAX_TOTAL_GAP_INTERVALS * 5
    # a fourth run after another 3-gap exceeds the cumulative cap
    d = _run(DAY, 28, 3, "-50")
    detected = detect_negative_price_episodes([a, b, c, d], grid.get)
    assert len(detected) == 1
    assert detected[0].detail["memberCount"] == 3


def test_episode_missing_observation_prevents_join() -> None:
    a = _run(DAY, 10, 3, "-20")
    b = _run(DAY, 14, 3, "-30")
    grid = _grid([DAY], Decimal("50"))
    grid[DAY.toordinal() * 288 + 13] = None
    assert detect_negative_price_episodes([a, b], grid.get) == []


def test_episode_single_run_no_group() -> None:
    grid = _grid([DAY], Decimal("50"))
    assert detect_negative_price_episodes([_run(DAY, 10, 5, "-9")], grid.get) == []


def test_episode_cross_midnight() -> None:
    """A run ending at day end joins a next-day run through a short gap."""
    a = _run(DAY, 285, 3, "-20")  # last three intervals of DAY
    b = _run(DAY2, 1, 3, "-30")  # one gap interval at position 0
    grid = _grid([DAY, DAY2], Decimal("50"))
    grid[DAY2.toordinal() * 288] = Decimal("10")
    detected = detect_negative_price_episodes([a, b], grid.get)
    assert len(detected) == 1
    event = detected[0].event
    assert event.owner_day == DAY
    assert event.interval_count == 7  # 3 + 1 + 3 across the boundary
    detail = detected[0].detail
    assert detail["negativeMinutes"] == 30
    assert detail["gapMinutes"] == 5
    assert detail["spanMinutes"] == 35
    assert detail["memberCount"] == 2


def test_episode_skips_edge_incomplete_members() -> None:
    incomplete = Event(
        type=EventType.NEGATIVE_PRICE_RUN,
        owner_day=DAY,
        start_position=10,
        interval_count=5,
        value=Decimal("-9"),
        edge_incomplete=True,
    )
    complete = _run(DAY, 30, 4, "-11")
    grid = _grid([DAY], Decimal("50"))
    assert detect_negative_price_episodes([incomplete, complete], grid.get) == []


# -- unusual demand ramp classification ------------------------------------------


def test_ramp_insufficient_baseline_is_explicit() -> None:
    """Below the day floors the outcome is insufficient, never 'normal'."""
    result = classify_demand_ramp(
        Decimal("5000"),
        [Decimal("100")] * (RAMP_MIN_CLASS_DAYS - 1),
        RAMP_MIN_COMPLETE_DAYS,
    )
    assert result.reason == "insufficient_baseline" and result.quantile is None
    result = classify_demand_ramp(
        Decimal("5000"),
        [Decimal("100")] * RAMP_MIN_CLASS_DAYS,
        RAMP_MIN_COMPLETE_DAYS - 1,
    )
    assert result.reason == "insufficient_baseline"


def test_ramp_unusual_above_quantile_and_floor() -> None:
    samples = [Decimal(str(i * 100)) for i in range(RAMP_MIN_CLASS_DAYS)]
    # P90 of 20 samples = the 18th smallest = 1700
    result = classify_demand_ramp(Decimal("1701"), samples, RAMP_MIN_COMPLETE_DAYS)
    assert result.reason == "unusual"
    assert result.quantile == Decimal("1700")


def test_ramp_at_quantile_is_ordinary() -> None:
    """Strictly greater than the quantile is required."""
    samples = [Decimal("100")] * RAMP_MIN_CLASS_DAYS
    result = classify_demand_ramp(Decimal("2000"), samples, 60)
    # P90 = 100, rise clears it and the 1000 MW floor -> unusual
    assert result.reason == "unusual"
    result = classify_demand_ramp(Decimal("100"), samples, 60)
    assert result.reason == "ordinary"


def test_ramp_min_rise_floor() -> None:
    """A rise under 1000 MW is ordinary even when above the quantile."""
    samples = [Decimal("50")] * RAMP_MIN_CLASS_DAYS
    result = classify_demand_ramp(Decimal("999"), samples, 60)
    assert result.reason == "ordinary"
    result = classify_demand_ramp(Decimal("1000"), samples, 60)
    assert result.reason == "unusual"


def test_nearest_rank_quantile() -> None:
    samples = [Decimal(str(v)) for v in range(1, 101)]
    assert nearest_rank(samples, 90) == Decimal("90")
    assert nearest_rank(samples, 50) == Decimal("50")
    assert nearest_rank(samples, 100) == Decimal("100")
    with pytest.raises(ValueError):
        nearest_rank([], 90)


def test_reversal_uses_scanner_runs() -> None:
    """End-to-end: scanned v1 runs feed the reversal detector."""
    days = [DAY, DAY2]
    values = _grid(days, Decimal("50"))
    for i in range(280, 284):
        values[DAY.toordinal() * 288 + i] = Decimal("-80")
    values[DAY.toordinal() * 288 + 287] = Decimal("900")
    runs = _scan_negative(days, values)
    detected = detect_price_reversals(runs, values.get)
    assert len(detected) == 1
    assert detected[0].event.value == Decimal("900")
    assert detected[0].detail["riseMinutes"] == (287 - 283) * 5
