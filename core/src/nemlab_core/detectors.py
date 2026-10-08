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
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from nemlab_core.prices import NEM_OFFSET

DETECTOR_VERSION = "v1"
DETECTOR_VERSION_V2 = "v2"

MIN_RUN_INTERVALS = 3
SPIKE_THRESHOLD = Decimal("1000")
RAMP_WINDOW_INTERVALS = 36
RAMP_WINDOW_OBSERVATIONS = RAMP_WINDOW_INTERVALS + 1
INTERVALS_PER_DAY = 288

# Frozen detector-v2 parameters (decision 022, calibrated in NEM-087).
REVERSAL_LOOKAHEAD_INTERVALS = 72  # 6 h of five-minute intervals
REVERSAL_PEAK_MIN = Decimal("300")  # AUD/MWh
REVERSAL_RISE_MIN = Decimal("300")  # AUD/MWh trough-to-peak
EPISODE_MAX_GAP_INTERVALS = 3  # <= 15 minutes between members
EPISODE_MAX_GAP_PRICE = Decimal("50")  # AUD/MWh, intervening observations
EPISODE_MAX_TOTAL_GAP_INTERVALS = 6  # <= 30 minutes cumulative
EPISODE_MIN_MEMBERS = 2
RAMP_BASELINE_DAYS = 90
RAMP_MIN_COMPLETE_DAYS = 60
RAMP_MIN_CLASS_DAYS = 20
RAMP_QUANTILE_PERCENT = 90
RAMP_MIN_RISE_MW = Decimal("1000")

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
    "unusual_demand_ramp": {
        "window_intervals": RAMP_WINDOW_INTERVALS,
        "baseline_days": RAMP_BASELINE_DAYS,
        "min_complete_days": RAMP_MIN_COMPLETE_DAYS,
        "min_class_days": RAMP_MIN_CLASS_DAYS,
        "quantile": "P90",
        "quantile_method": "nearest_rank",
        "comparison": "gt",
        "min_rise_mw": str(RAMP_MIN_RISE_MW),
        "class": "weekday_weekend",
    },
    "price_reversal": {
        "min_run_intervals": MIN_RUN_INTERVALS,
        "peak_at_least": str(REVERSAL_PEAK_MIN),
        "rise_at_least": str(REVERSAL_RISE_MIN),
        "lookahead_intervals": REVERSAL_LOOKAHEAD_INTERVALS,
        "tie": "highest_then_earliest",
    },
    "negative_price_episode": {
        "max_gap_intervals": EPISODE_MAX_GAP_INTERVALS,
        "max_gap_price": str(EPISODE_MAX_GAP_PRICE),
        "max_total_gap_intervals": EPISODE_MAX_TOTAL_GAP_INTERVALS,
        "min_members": EPISODE_MIN_MEMBERS,
    },
}

# Event rows carry the version of the rule that produced them; v1 rules are
# unchanged under the v2 suite so their rows keep "v1".
DETECTOR_VERSIONS = {
    "negative_price_run": DETECTOR_VERSION,
    "price_spike": DETECTOR_VERSION,
    "demand_ramp": DETECTOR_VERSION,
    "unusual_demand_ramp": DETECTOR_VERSION_V2,
    "price_reversal": DETECTOR_VERSION_V2,
    "negative_price_episode": DETECTOR_VERSION_V2,
}


class EventType(StrEnum):
    NEGATIVE_PRICE_RUN = "negative_price_run"
    PRICE_SPIKE = "price_spike"
    DEMAND_RAMP = "demand_ramp"
    UNUSUAL_DEMAND_RAMP = "unusual_demand_ramp"
    PRICE_REVERSAL = "price_reversal"
    NEGATIVE_PRICE_EPISODE = "negative_price_episode"


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


@dataclass(frozen=True)
class Detected:
    """A detector-v2 event plus its stored evidence payload.

    ``linked`` lists the v1 events this event subsumes or groups — the
    publication layer resolves them to stored event ids for ``detail`` and
    for highlight suppression. ``detail`` becomes the immutable per-event
    evidence JSON (baseline, members, trough/peak — never detector config).
    """

    event: Event
    detail: dict[str, object]
    linked: tuple[Event, ...] = ()


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


# -- detector v2 ---------------------------------------------------------------
#
# Positions convert to a single absolute index
# ``day.toordinal() * 288 + position`` so runs and look-ahead windows cross
# market-day boundaries without special cases.


def _absolute(day: date, position: int) -> int:
    return day.toordinal() * INTERVALS_PER_DAY + position


def _split(index: int) -> tuple[date, int]:
    return date.fromordinal(index // INTERVALS_PER_DAY), index % INTERVALS_PER_DAY


def nearest_rank(samples: list[Decimal], percent: int) -> Decimal:
    """Nearest-rank quantile: the ``ceil(p/100 * n)``-th smallest sample."""
    if not samples or not 0 < percent <= 100:
        raise ValueError("quantile needs samples and a percent in (0, 100]")
    ordered = sorted(samples)
    rank = max(1, -(-percent * len(ordered) // 100))
    return ordered[rank - 1]


def classify_demand_ramp(
    rise: Decimal,
    class_samples: list[Decimal],
    complete_days: int,
) -> "RampClassification":
    """Is ``rise`` unusual against the same-class daily-ramp distribution?

    ``class_samples`` holds each complete same-class baseline day's largest
    positive three-hour change (complete nonpositive days contribute 0);
    ``complete_days`` counts every complete baseline day of either class.
    Short history reports ``insufficient_baseline`` — never "normal".
    """
    if (
        complete_days < RAMP_MIN_COMPLETE_DAYS
        or len(class_samples) < RAMP_MIN_CLASS_DAYS
    ):
        return RampClassification("insufficient_baseline", None)
    quantile = nearest_rank(class_samples, RAMP_QUANTILE_PERCENT)
    unusual = rise > quantile and rise >= RAMP_MIN_RISE_MW
    return RampClassification(
        "unusual" if unusual else "ordinary",
        quantile if unusual else None,
    )


@dataclass(frozen=True)
class RampClassification:
    reason: Literal["unusual", "ordinary", "insufficient_baseline"]
    quantile: Decimal | None  # the P90 the rise cleared, when unusual


def detect_price_reversals(
    runs: list[Event],
    value_at: Callable[[int], Decimal | None],
) -> list[Detected]:
    """Complete negative run, then >= ``REVERSAL_PEAK_MIN`` within 6 h.

    ``value_at`` maps an absolute interval index to a stored price or None;
    any missing observation inside the look-ahead window withholds the
    reversal claim entirely — the "highest qualifying price" needs the whole
    window. Runs sharing a peak keep the largest-rise candidate (earliest run
    start on ties) and retain the other runs as linked evidence.
    """
    candidates: list[tuple[Event, int, Decimal, Decimal]] = []
    for run in runs:
        if run.edge_incomplete or run.interval_count < MIN_RUN_INTERVALS:
            continue
        start = _absolute(run.owner_day, run.start_position)
        end = start + run.interval_count - 1
        window = [
            value_at(i) for i in range(end + 1, end + 1 + REVERSAL_LOOKAHEAD_INTERVALS)
        ]
        if any(v is None for v in window):
            continue
        qualifying = [
            (end + 1 + offset, value)
            for offset, value in enumerate(window)
            if value is not None
            and value >= REVERSAL_PEAK_MIN
            and value - run.value >= REVERSAL_RISE_MIN
        ]
        if not qualifying:
            continue
        peak_index, peak = max(qualifying, key=lambda iv: (iv[1], -iv[0]))
        candidates.append((run, peak_index, peak, peak - run.value))
    by_peak: dict[int, list[tuple[Event, int, Decimal, Decimal]]] = {}
    for candidate in candidates:
        by_peak.setdefault(candidate[1], []).append(candidate)
    detected: list[Detected] = []
    for group in by_peak.values():
        run, peak_index, peak, rise = max(
            group,
            key=lambda c: (
                c[3],
                -_absolute(c[0].owner_day, c[0].start_position),
            ),
        )
        linked = tuple(c[0] for c in group if c[0] is not run)
        start = _absolute(run.owner_day, run.start_position)
        end = start + run.interval_count - 1
        peak_day, _peak_position = _split(peak_index)

        def _run_range(member: Event) -> dict[str, str]:
            member_start = _absolute(member.owner_day, member.start_position)
            return {
                "startAt": _instant_label(member_start),
                "endAt": _instant_label(member_start + member.interval_count - 1),
            }

        detail: dict[str, object] = {
            "trough": str(run.value),
            "peak": str(peak),
            "rise": str(rise),
            "riseMinutes": (peak_index - end) * 5,
            "runStartAt": _instant_label(start),
            "runEndAt": _instant_label(end),
            "peakAt": _instant_label(peak_index),
            "peakMarketDay": peak_day.isoformat(),
            "peakPosition": _peak_position,
            "memberRuns": [_run_range(m) for m in (run, *linked)],
        }
        detected.append(
            Detected(
                event=Event(
                    type=EventType.PRICE_REVERSAL,
                    owner_day=run.owner_day,
                    start_position=run.start_position,
                    interval_count=peak_index - start + 1,
                    value=peak,
                    edge_incomplete=False,
                ),
                detail=detail,
                linked=(run, *linked),
            )
        )
    return detected


def _instant_label(index: int) -> str:
    """Interval-end instant of absolute index, fixed NEM UTC+10."""
    day, position = _split(index)
    instant = datetime.combine(day, datetime.min.time(), tzinfo=NEM_OFFSET) + timedelta(
        minutes=5 * (position + 1)
    )
    return instant.isoformat()


def detect_negative_price_episodes(
    runs: list[Event],
    value_at: Callable[[int], Decimal | None],
) -> list[Detected]:
    """Join consecutive complete runs separated by short low-price gaps.

    A join requires every intervening observation present, nonnegative and at
    most ``EPISODE_MAX_GAP_PRICE``, at most ``EPISODE_MAX_GAP_INTERVALS``
    intervals per gap and ``EPISODE_MAX_TOTAL_GAP_INTERVALS`` cumulative per
    episode. Missing observations simply prevent joining — runs are never
    merged across unknown data.
    """
    ordered = sorted(
        (r for r in runs if not r.edge_incomplete),
        key=lambda r: _absolute(r.owner_day, r.start_position),
    )
    groups: list[list[Event]] = []
    current: list[Event] = []
    gap_total = 0
    for run in ordered:
        start = _absolute(run.owner_day, run.start_position)
        if current:
            previous_end = (
                _absolute(current[-1].owner_day, current[-1].start_position)
                + current[-1].interval_count
                - 1
            )
            gap = start - previous_end - 1
            gap_values = [value_at(i) for i in range(previous_end + 1, start)]
            joinable = (
                0 < gap <= EPISODE_MAX_GAP_INTERVALS
                and gap_total + gap <= EPISODE_MAX_TOTAL_GAP_INTERVALS
                and all(
                    v is not None and 0 <= v <= EPISODE_MAX_GAP_PRICE
                    for v in gap_values
                )
            )
            if joinable:
                current.append(run)
                gap_total += gap
                continue
        if len(current) >= EPISODE_MIN_MEMBERS:
            groups.append(current)
        current = [run]
        gap_total = 0
    if len(current) >= EPISODE_MIN_MEMBERS:
        groups.append(current)

    detected: list[Detected] = []
    for members in groups:
        first, last = members[0], members[-1]
        start = _absolute(first.owner_day, first.start_position)
        end = _absolute(last.owner_day, last.start_position) + last.interval_count - 1
        negative = sum(m.interval_count for m in members)
        detail = {
            "memberCount": len(members),
            "negativeMinutes": negative * 5,
            "gapMinutes": (end - start + 1 - negative) * 5,
            "spanMinutes": (end - start + 1) * 5,
            "members": [
                {
                    "startAt": _instant_label(_absolute(m.owner_day, m.start_position)),
                    "endAt": _instant_label(
                        _absolute(m.owner_day, m.start_position) + m.interval_count - 1
                    ),
                }
                for m in members
            ],
        }
        detected.append(
            Detected(
                event=Event(
                    type=EventType.NEGATIVE_PRICE_EPISODE,
                    owner_day=first.owner_day,
                    start_position=first.start_position,
                    interval_count=end - start + 1,
                    value=min(m.value for m in members),
                    edge_incomplete=False,
                ),
                detail=detail,
                linked=tuple(members),
            )
        )
    return detected
