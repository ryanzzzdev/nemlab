"""Deterministic GridReplay event detectors — frozen ``v1`` rules.

Decision 020 fixes the rules; ``fixtures/gridreplay/`` holds the labelled
cases. Detectors are pure: they take ordered ``Interval`` sequences (an
``Interval`` whose value is ``None`` covers both a null and an absent row —
both terminate qualifying runs identically) and return factual events. No
renewable-ratio synthesis, no causal titles.

Price runs scan continuously across market-day boundaries; chunk boundaries
never close a run (feed observations through ``RunScanner.feed`` in any
chunking — the output is identical to an unchunked scan). A run still open at
the left/right edge of the evaluated window is ``edge_incomplete`` — recorded,
not presented as a finished run.
"""

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Literal

DETECTOR_VERSION = "v1"

MIN_RUN_INTERVALS = 3
SPIKE_THRESHOLD = Decimal("1000")
RAMP_WINDOW_INTERVALS = 36
RAMP_WINDOW_OBSERVATIONS = RAMP_WINDOW_INTERVALS + 1
INTERVALS_PER_DAY = 288

# Canonical detector parameters — embedded verbatim in stored events.
DETECTOR_PARAMS = {
    "negative_price_run": {
        "threshold": "0",
        "comparison": "lt",
        "min_intervals": MIN_RUN_INTERVALS,
    },
    "price_spike": {
        "threshold": str(SPIKE_THRESHOLD),
        "comparison": "gt",
        "min_intervals": 1,
    },
    "demand_ramp": {
        "window_intervals": RAMP_WINDOW_INTERVALS,
        "per_day": True,
        "tie": "earliest",
    },
}


class EventType(StrEnum):
    NEGATIVE_PRICE_RUN = "negative_price_run"
    PRICE_SPIKE = "price_spike"
    DEMAND_RAMP = "demand_ramp"


@dataclass(frozen=True)
class Interval:
    """One five-minute observation. ``value=None`` for null or absent rows."""

    day: date
    position: int  # 0..287 within the market day
    value: Decimal | None


@dataclass(frozen=True)
class Event:
    """A detected event on the market-day grid."""

    type: EventType
    owner_day: date  # the market day owning the event start
    start_position: int  # 0..287 within owner_day
    interval_count: int
    value: Decimal  # min price / peak price / ramp MW
    edge_incomplete: bool


@dataclass(frozen=True)
class RampEvaluation:
    """Per-day demand-ramp outcome."""

    event: Event | None
    reason: Literal["event", "none", "insufficient_coverage"]


def _next_position(day: date, position: int) -> tuple[date, int]:
    return (
        (day, position + 1)
        if position < INTERVALS_PER_DAY - 1
        else (day + timedelta(days=1), 0)
    )


class RunScanner:
    """Stateful run detector; chunked and unchunked feeds agree.

    ``feed`` must receive observations in strict grid order. ``finish`` marks
    the evaluated window's right edge; an ``Event`` whose run was open at an
    edge is flagged ``edge_incomplete`` rather than reported as complete.
    """

    def __init__(
        self,
        event_type: EventType,
        qualifies: Callable[[Decimal], bool],
        extreme: Callable[[Decimal, Decimal], Decimal],
        min_intervals: int,
    ) -> None:
        self._event_type = event_type
        self._qualifies = qualifies
        self._extreme = extreme
        self._min = min_intervals
        self._open: _Run | None = None
        self._previous: tuple[date, int] | None = None
        self._seen_any = False

    def feed(self, interval: Interval) -> Iterator[Event]:
        value = interval.value
        gap = self._previous is not None and (
            interval.day,
            interval.position,
        ) != _next_position(*self._previous)
        qualifying = not gap and value is not None and self._qualifies(value)
        if not qualifying and self._open is not None:
            event = self._close(edge=False)
            if event is not None:
                yield event
        if qualifying and value is not None:
            if self._open is None:
                # A run opened on the very first observation touches the
                # window's left edge — it may extend before the window.
                self._open = _Run(
                    interval.day, interval.position, 0, value, not self._seen_any
                )
            self._open.count += 1
            self._open.extreme = self._extreme(self._open.extreme, value)
        self._previous = (interval.day, interval.position)
        self._seen_any = True

    def feed_all(self, intervals: Iterable[Interval]) -> Iterator[Event]:
        for interval in intervals:
            yield from self.feed(interval)

    def finish(self) -> Iterator[Event]:
        """Close the evaluated window; an open run is edge-incomplete."""
        if self._open is not None:
            event = self._close(edge=True)
            if event is not None:
                yield event

    def _close(self, edge: bool) -> Event | None:
        run = self._open
        self._open = None
        if run is None or run.count < self._min:
            return None
        return Event(
            type=self._event_type,
            owner_day=run.start_day,
            start_position=run.start_pos,
            interval_count=run.count,
            value=run.extreme,
            edge_incomplete=edge or run.edge_left,
        )


@dataclass
class _Run:
    start_day: date
    start_pos: int
    count: int
    extreme: Decimal
    edge_left: bool


def negative_price_run_scanner() -> RunScanner:
    """Strict ``price < 0`` for at least ``MIN_RUN_INTERVALS`` intervals."""
    return RunScanner(
        EventType.NEGATIVE_PRICE_RUN,
        lambda v: v < 0,
        min,
        MIN_RUN_INTERVALS,
    )


def price_spike_scanner() -> RunScanner:
    """Strict ``price > 1000``; contiguous qualifying intervals group."""
    return RunScanner(
        EventType.PRICE_SPIKE,
        lambda v: v > SPIKE_THRESHOLD,
        max,
        1,
    )


def evaluate_demand_ramp(day: date, values: list[Decimal | None]) -> RampEvaluation:
    """Largest positive scheduled-demand change over a 36-step window.

    All 288 observations must be numeric; any missing value withholds the
    daily-largest claim entirely (``insufficient_coverage``) — never a
    best-effort ramp. A complete day without a positive change yields
    ``none``.
    """
    if len(values) != INTERVALS_PER_DAY or any(v is None for v in values):
        return RampEvaluation(None, "insufficient_coverage")
    best_index: int | None = None
    best = Decimal(0)
    for i in range(0, INTERVALS_PER_DAY - RAMP_WINDOW_INTERVALS):
        diff = values[i + RAMP_WINDOW_INTERVALS] - values[i]  # type: ignore[operator]
        if best_index is None or diff > best:
            best_index, best = i, diff
    if best_index is None or best <= 0:
        return RampEvaluation(None, "none")
    return RampEvaluation(
        Event(
            type=EventType.DEMAND_RAMP,
            owner_day=day,
            start_position=best_index,
            interval_count=RAMP_WINDOW_OBSERVATIONS,
            value=best,
            edge_incomplete=False,
        ),
        "event",
    )
