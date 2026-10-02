"""NEM-057 — detector tests against the hand-labelled gridreplay fixtures.

Fixtures are synthetic run-length-encoded inputs (see
``fixtures/gridreplay/README.md``); ``null`` and ``"ABSENT"`` both expand to
``Interval(value=None)`` — the frozen rules treat them identically.
"""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from nemlab_core.detectors import (
    DETECTOR_VERSION,
    Event,
    EventType,
    Interval,
    evaluate_demand_ramp,
    negative_price_run_scanner,
    price_spike_scanner,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "gridreplay"


def _expand(fixture: dict, metric: str) -> list[Interval]:
    days = [date.fromisoformat(d) for d in fixture["marketDays"]]
    intervals: list[Interval] = []
    index = 0
    for count, raw in fixture["series"][metric]["runs"]:
        value = None if raw is None or raw == "ABSENT" else Decimal(str(raw))
        for _ in range(count):
            intervals.append(
                Interval(day=days[index // 288], position=index % 288, value=value)
            )
            index += 1
    return intervals


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _events(scanner, intervals) -> list[Event]:
    return [*scanner.feed_all(intervals), *scanner.finish()]


def _expected(fixture: dict) -> list[tuple]:
    days = [date.fromisoformat(d) for d in fixture["marketDays"]]
    return [
        (
            EventType(e["type"]),
            days[e["startIndex"] // 288],
            e["startIndex"] % 288,
            e["intervals"],
            Decimal(str(e["value"])),
            e["edgeIncomplete"],
        )
        for e in fixture["expected"]["events"]
    ]


def _actual(events: list[Event]) -> list[tuple]:
    return [
        (
            e.type,
            e.owner_day,
            e.start_position,
            e.interval_count,
            e.value,
            e.edge_incomplete,
        )
        for e in events
    ]


def test_detector_version_is_v1() -> None:
    assert DETECTOR_VERSION == "v1"


@pytest.mark.parametrize(
    "fixture",
    [
        "negative-run-complete.json",
        "negative-run-gap-interrupts.json",
        "negative-run-cross-midnight.json",
        "edge-incomplete-run.json",
        "no-event-complete-day.json",
    ],
)
def test_negative_price_runs(fixture: str) -> None:
    doc = _load(fixture)
    intervals = _expand(doc, "price")
    expected = [e for e in _expected(doc) if e[0] is EventType.NEGATIVE_PRICE_RUN]
    got = _events(negative_price_run_scanner(), intervals)
    assert _actual(got) == expected


@pytest.mark.parametrize(
    "fixture", ["spike-thresholds.json", "no-event-complete-day.json"]
)
def test_price_spikes(fixture: str) -> None:
    doc = _load(fixture)
    intervals = _expand(doc, "price")
    expected = [e for e in _expected(doc) if e[0] is EventType.PRICE_SPIKE]
    got = _events(price_spike_scanner(), intervals)
    assert _actual(got) == expected


@pytest.mark.parametrize(
    ("fixture", "reason"),
    [
        ("ramp-complete-tie-earliest.json", "event"),
        ("ramp-insufficient-coverage.json", "insufficient_coverage"),
        ("no-event-complete-day.json", "none"),
    ],
)
def test_demand_ramp(fixture: str, reason: str) -> None:
    doc = _load(fixture)
    intervals = _expand(doc, "demand")
    day = date(2023, 9, 11)
    result = evaluate_demand_ramp(day, [i.value for i in intervals])
    assert result.reason == reason
    expected = [e for e in _expected(doc) if e[0] is EventType.DEMAND_RAMP]
    if reason == "event":
        assert result.event is not None
        assert _actual([result.event]) == expected
    else:
        assert result.event is None
        assert expected == []


@pytest.mark.parametrize("cut", [1, 5, 99, 100, 103, 104, 287, 288, 400])
def test_chunked_feed_matches_unchunked(cut: int) -> None:
    """Chunk boundaries never close a run: split feeds agree with one feed."""
    doc = _load("negative-run-cross-midnight.json")
    intervals = _expand(doc, "price")

    def run(chunks):
        scanner = negative_price_run_scanner()
        events = []
        for chunk in chunks:
            events.extend(scanner.feed_all(chunk))
        events.extend(scanner.finish())
        return events

    whole = run([intervals])
    chunked = run([intervals[:cut], intervals[cut:]])
    assert _actual(chunked) == _actual(whole)


def test_spike_grouping_and_single_interval() -> None:
    day = date(2023, 9, 11)

    def seq(*values):
        return [
            Interval(day, i, Decimal(str(v)) if v is not None else None)
            for i, v in enumerate(values)
        ]

    # one spike alone qualifies (min_intervals = 1)
    (event,) = _events(price_spike_scanner(), seq(*([50] * 10 + [1000.01] + [50] * 10)))
    assert event.interval_count == 1 and event.value == Decimal("1000.01")
    # non-5m-step gap ends a run: duplicate position then resume
    broken = seq(*[-1.0] * 3)
    broken.append(Interval(day, 2, Decimal("-1.0")))  # repeats position 2
    broken.append(Interval(day, 4, Decimal("-1.0")))
    broken.extend(seq(*[50] * 5)[1:])  # avoid re-using consumed positions
    # rebuild cleanly: positions 0,1,2 qualify; then duplicate pos 2 → gap
    events = _events(negative_price_run_scanner(), broken)
    assert [e.interval_count for e in events] == [3]
