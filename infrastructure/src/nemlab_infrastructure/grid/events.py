"""``GridCatalogue`` — detector runs and atomic catalogue publication.

One ``publish`` call evaluates the frozen ``v1`` detectors over a bounded
window, versions the resulting events, materialises a replay snapshot per new
event version, and flips the ``grid_catalogue_current`` pointer — all in one
transaction, so a failure or retry can never expose a partial publication.

Inputs are pinned by first snapshotting the current-revision pointers, then
reading revisions by id (immutable rows), so a mid-run source correction
cannot blend old and new values inside one publication.
"""

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

import sqlalchemy as sa

from nemlab_core import decimal_text
from nemlab_core.detectors import (
    DETECTOR_PARAMS,
    DETECTOR_VERSION,
    DETECTOR_VERSION_V2,
    DETECTOR_VERSIONS,
    INTERVALS_PER_DAY,
    RAMP_BASELINE_DAYS,
    RAMP_MIN_CLASS_DAYS,
    RAMP_MIN_COMPLETE_DAYS,
    RAMP_MIN_RISE_MW,
    REVERSAL_LOOKAHEAD_INTERVALS,
    Detected,
    Event,
    EventType,
    Interval,
    RampClassification,
    classify_demand_ramp,
    detect_negative_price_episodes,
    detect_price_reversals,
    evaluate_demand_ramp,
    negative_price_run_scanner,
    price_spike_scanner,
)
from nemlab_core.highlights import HIGHLIGHTS_V2, Candidate, Selection, select
from nemlab_core.prices import NEM_OFFSET, Region
from nemlab_infrastructure.grid.batch import Metric
from nemlab_infrastructure.prices.batch import Kind

MAX_PUBLICATION_DAYS = 31
REPLAY_MAX_DAYS = 7

_PRICE = "price"  # virtual series key; prices live in price_revision

# Bounded catalogue ordering: primary key, then start_at/id descending —
# matching the newest-first convention (oldest reverses all three).
_SORTS = {
    "newest": ("e.start_at", "DESC", "DESC"),
    "oldest": ("e.start_at", "ASC", "ASC"),
    "longest": ("e.interval_count", "DESC", "DESC"),
    "deepest": ("e.value", "ASC", "DESC"),
    "highest": ("e.value", "DESC", "DESC"),
    "largest_rise": ("e.value", "DESC", "DESC"),
}

# Types a catalogue sort or numeric filter applies to; anything else is an
# unsupported combination and rejected before a query runs.
_SORTABLE = {
    "longest": frozenset(
        {
            EventType.NEGATIVE_PRICE_RUN,
            EventType.PRICE_SPIKE,
            EventType.NEGATIVE_PRICE_EPISODE,
        }
    ),
    "deepest": frozenset(
        {EventType.NEGATIVE_PRICE_RUN, EventType.NEGATIVE_PRICE_EPISODE}
    ),
    "highest": frozenset({EventType.PRICE_SPIKE, EventType.PRICE_REVERSAL}),
    "largest_rise": frozenset({EventType.DEMAND_RAMP, EventType.UNUSUAL_DEMAND_RAMP}),
}
MIN_DURATION_TYPES = frozenset(
    {
        EventType.NEGATIVE_PRICE_RUN,
        EventType.PRICE_SPIKE,
        EventType.NEGATIVE_PRICE_EPISODE,
    }
)
VALUE_GTE_TYPES = frozenset(
    {
        EventType.PRICE_SPIKE,
        EventType.PRICE_REVERSAL,
        EventType.DEMAND_RAMP,
        EventType.UNUSUAL_DEMAND_RAMP,
    }
)
VALUE_LTE_TYPES = frozenset(
    {EventType.NEGATIVE_PRICE_RUN, EventType.NEGATIVE_PRICE_EPISODE}
)

_SCOPE_WHERE = (
    "pe.publication_id = :publication"
    " AND (CAST(:type AS text) IS NULL OR e.type = :type)"
    " AND (CAST(:from_start AS timestamptz) IS NULL"
    "      OR e.end_at > :from_start)"
    " AND (CAST(:to_end AS timestamptz) IS NULL"
    "      OR e.start_at < :to_end)"
    " AND (CAST(:min_dur AS integer) IS NULL"
    "      OR e.interval_count * 5 >= :min_dur)"
    " AND (CAST(:value_gte AS numeric) IS NULL OR e.value >= :value_gte)"
    " AND (CAST(:value_lte AS numeric) IS NULL OR e.value <= :value_lte)"
)

_EVENTS_FROM = " FROM grid_event e JOIN grid_publication_event pe ON pe.event_id = e.id"

# Keyset continuation per sort family — static clauses selected by the
# validated sort name; values are always bound parameters.
_KEYSET = {
    "newest": (
        "(CAST(:k1 AS timestamptz) IS NOT NULL AND"
        " (e.start_at < :k1 OR (e.start_at = :k1 AND e.id::text < :k2)))"
    ),
    "oldest": (
        "(CAST(:k1 AS timestamptz) IS NOT NULL AND"
        " (e.start_at > :k1 OR (e.start_at = :k1 AND e.id::text > :k2)))"
    ),
    "asc_value": (
        "(CAST(:k0 AS numeric) IS NOT NULL AND"
        " (e.value > :k0 OR (e.value = :k0 AND (e.start_at < :k1"
        "  OR (e.start_at = :k1 AND e.id::text < :k2)))))"
    ),
    "desc_primary": (
        "(CAST(:k0 AS numeric) IS NOT NULL AND"
        " ({primary} < :k0 OR ({primary} = :k0 AND (e.start_at < :k1"
        "  OR (e.start_at = :k1 AND e.id::text < :k2)))))"
    ),
}

# Card previews (NEM-086): an event-local series reduced to bounded slots.
PREVIEW_VERSION = "preview-v1"
PREVIEW_CONTEXT_INTERVALS = 12  # one hour either side, coverage permitting
PREVIEW_MAX_SLOTS = 48  # two plotted points per slot -> <= 96 points


@dataclass(frozen=True)
class EventQuery:
    """Normalised catalogue scope: one publication plus filters and sort."""

    event_type: EventType | None = None
    start: date | None = None
    end: date | None = None
    sort: str = "newest"
    min_duration_minutes: int | None = None
    value_gte: Decimal | None = None
    value_lte: Decimal | None = None

    def validate(self) -> None:
        if (self.start is None) != (self.end is None) or (
            self.start is not None and self.end is not None and self.start > self.end
        ):
            raise ValueError("from/to must be a complete inclusive range")
        if self.sort not in _SORTS:
            raise ValueError(f"unsupported sort {self.sort!r}")
        if self.sort == "oldest" and self.event_type is not None:
            raise ValueError("sort 'oldest' is only supported without a type")
        if self.sort in _SORTABLE and self.event_type not in _SORTABLE[self.sort]:
            raise ValueError(f"sort {self.sort!r} is not supported for this type")
        if self.min_duration_minutes is not None and (
            self.min_duration_minutes < 0 or self.event_type not in MIN_DURATION_TYPES
        ):
            raise ValueError(
                "minDurationMinutes is only supported for run, spike and episode types"
            )
        if self.value_gte is not None and self.event_type not in VALUE_GTE_TYPES:
            raise ValueError("valueGte is not supported for this type")
        if self.value_lte is not None and self.event_type not in VALUE_LTE_TYPES:
            raise ValueError("valueLte is not supported for this type")


@dataclass(frozen=True)
class _Inputs:
    """Pinned revisions for one publication snapshot."""

    price_revs: dict[date, UUID]
    grid_revs: dict[tuple[str, str, date], UUID]
    slots: dict[UUID, str]  # revision id -> slots json text


@dataclass(frozen=True)
class StoredEvent:
    id: UUID
    region: Region
    type: EventType
    detector_version: str
    detector_params: dict[str, object]
    market_day: date
    start_at: datetime
    end_at: datetime
    interval_count: int
    value: Decimal
    edge_incomplete: bool
    source_revisions: dict[str, object]
    coverage: dict[str, object]
    detail: dict[str, object] | None
    version: int
    superseded: bool


@dataclass(frozen=True)
class Publication:
    id: UUID
    region: Region
    start: date
    end: date
    detector_version: str
    event_count: int
    coverage: dict[str, dict[str, object]]
    created_at: datetime
    run_id: UUID | None = None
    actor: str | None = None
    attempt_key: str | None = None


@dataclass(frozen=True)
class DetectionAttempt:
    """One publication attempt (detection run) — the reconciliation record
    for a lost publish response; FAILED rows outlive their transaction."""

    id: UUID
    region: Region
    start: date
    end: date
    detector_version: str
    status: str
    publication_id: UUID | None
    diagnostic: str | None
    actor: str | None
    attempt_key: str | None
    created_at: datetime


@dataclass(frozen=True)
class BaselineReadiness:
    """Ramp-baseline readiness for one candidate publication day: complete
    demand days in its own preceding 90-day window, same-class count and
    the detector's thresholds — insufficient baseline is reported, never
    merged into event counts."""

    day: date
    complete_days: int
    class_days: int
    ready: bool


def _canonical(params: object) -> str:
    return json.dumps(params, sort_keys=True, separators=(",", ":"))


def _days(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days)]


def _member_days(event: Event) -> list[date]:
    first = event.owner_day.toordinal() * INTERVALS_PER_DAY + event.start_position
    last = first + event.interval_count - 1
    return [
        date.fromordinal(d)
        for d in range(first // INTERVALS_PER_DAY, last // INTERVALS_PER_DAY + 1)
    ]


def _instant(day: date, position: int) -> datetime:
    """Interval-end instant of grid position ``position`` on ``day``."""
    return datetime.combine(day, datetime.min.time(), tzinfo=NEM_OFFSET) + timedelta(
        minutes=5 * (position + 1)
    )


def instant_label(index: int) -> str:
    """Interval-end instant of an absolute market-grid index."""
    day = date.fromordinal(index // INTERVALS_PER_DAY)
    return _instant(day, index % INTERVALS_PER_DAY).isoformat()


def _values(slots_text: str, field: str) -> tuple[Decimal | None, ...]:
    raw = json.loads(slots_text, parse_float=Decimal, parse_int=Decimal)
    return tuple(
        Decimal(str(e[field])) if e["kind"] == Kind.VALUE.name else None for e in raw
    )


def _kinds(slots_text: str) -> tuple[str, ...]:
    return tuple(e["kind"] for e in json.loads(slots_text))


class GridCatalogue:
    def __init__(self, engine: sa.engine.Engine) -> None:
        self.engine = engine
        # Lazily computed, bounded card previews keyed by immutable event id.
        self._previews: dict[UUID, dict[str, object]] = {}

    # -- publication ----------------------------------------------------------

    def publish(
        self,
        region: Region,
        start: date,
        end: date,
        suite: str = DETECTOR_VERSION,
        actor: str | None = None,
        attempt_key: str | None = None,
    ) -> Publication:
        """Detect, version, snapshot and atomically publish a window.

        ``suite`` selects the detector suite: ``v1`` (the frozen initial
        rules) or ``v2`` (v1 plus the calibrated reversal/episode/unusual-ramp
        detectors). Publishing new types is an explicit operator choice.
        ``actor``/``attempt_key`` annotate the detection-run audit row for
        lost-response reconciliation; they never deduplicate publishes.
        """
        if suite not in (DETECTOR_VERSION, DETECTOR_VERSION_V2):
            raise ValueError("detector suite must be v1 or v2")
        if not start < end or start + timedelta(days=MAX_PUBLICATION_DAYS) < end:
            raise ValueError("Publication window must contain 1-31 days")
        if attempt_key is not None and not 1 <= len(attempt_key) <= 128:
            raise ValueError("Attempt key must be 1-128 characters")
        run_id = uuid.uuid4()
        try:
            # REPEATABLE READ pins every read in the publication to one
            # snapshot, so a concurrent import cannot blend revisions.
            with (
                self.engine.connect().execution_options(
                    isolation_level="REPEATABLE READ"
                ) as conn,
                conn.begin(),
            ):
                publication = self._publish_inside(
                    conn, run_id, region, start, end, suite, actor, attempt_key
                )
        except Exception as failure:
            self._record_run(
                run_id,
                region,
                start,
                end,
                str(failure)[:500],
                suite,
                actor,
                attempt_key,
            )
            raise
        return publication

    def _record_run(
        self,
        run_id: UUID,
        region: Region,
        start: date,
        end: date,
        diagnostic: str,
        suite: str = DETECTOR_VERSION,
        actor: str | None = None,
        attempt_key: str | None = None,
    ) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO grid_detection_run"
                    " (id,region,start_day,end_exclusive,detector_version,"
                    "  status,diagnostic,actor,request_key)"
                    " VALUES (:id,:region,:start,:end,:version,'FAILED',:diag,"
                    " :actor,:key)"
                ),
                {
                    "id": run_id,
                    "region": region.name,
                    "start": start,
                    "end": end,
                    "version": suite,
                    "diag": diagnostic,
                    "actor": actor,
                    "key": attempt_key,
                },
            )

    def _snapshot_inputs(
        self, conn: sa.Connection, region: Region, start: date, end: date
    ) -> "_Inputs":
        """Pin current pointers, then load the immutable revision payloads."""
        price_days = {
            row.market_day: row.revision_id
            for row in conn.execute(
                sa.text(
                    "SELECT market_day, revision_id FROM price_current"
                    " WHERE region=:region AND market_day>=:start"
                    " AND market_day<:end"
                ),
                {"region": region.name, "start": start, "end": end},
            )
        }
        grid_days = {
            (row.metric, row.series, row.market_day): row.revision_id
            for row in conn.execute(
                sa.text(
                    "SELECT metric, series, market_day, revision_id"
                    " FROM grid_current WHERE region=:region"
                    " AND market_day>=:start AND market_day<:end"
                ),
                {"region": region.name, "start": start, "end": end},
            )
        }
        slots: dict[UUID, str] = {}
        ids = set(price_days.values()) | set(grid_days.values())
        for rev_id, text in conn.execute(
            sa.text("SELECT id, slots::text FROM price_revision WHERE id = ANY(:ids)"),
            {"ids": list(ids)},
        ).all():
            slots[rev_id] = text
        for rev_id, text in conn.execute(
            sa.text("SELECT id, slots::text FROM grid_revision WHERE id = ANY(:ids)"),
            {"ids": list(ids)},
        ).all():
            slots[rev_id] = text
        return _Inputs(price_days, grid_days, slots)

    def _detect(
        self,
        inputs: "_Inputs",
        start: date,
        end: date,
        suite: str,
    ) -> tuple[
        list[tuple[Event, dict[str, object], dict[str, object]]],
        list[tuple[Detected, dict[str, object], dict[str, object]]],
        dict[str, dict[str, object]],
    ]:
        """Run detectors; return v1 (event, sources, coverage) triples, v2
        ``Detected`` triples and the per-day publication coverage summary."""
        price_revs, grid_revs, slots = (
            inputs.price_revs,
            inputs.grid_revs,
            inputs.slots,
        )
        negative = negative_price_run_scanner()
        spike = price_spike_scanner()
        detected: list[Event] = []
        detected_v2: list[tuple[Detected, dict[str, object], dict[str, object]]] = []
        summary: dict[str, dict[str, object]] = {}
        ramps: dict[date, Event] = {}
        for day in _days(start, end):
            day_str = day.isoformat()
            price_rev = price_revs.get(day)
            prices = _values(slots[price_rev], "price") if price_rev in slots else None
            demand_rev = grid_revs.get((Metric.DEMAND.value, "", day))
            demands = (
                _values(slots[demand_rev], "value") if demand_rev in slots else None
            )
            missing_price = (
                288 if prices is None else sum(1 for v in prices if v is None)
            )
            missing_demand = (
                288 if demands is None else sum(1 for v in demands if v is None)
            )
            for position in range(INTERVALS_PER_DAY):
                value = None if prices is None else prices[position]
                interval = Interval(day, position, value)
                detected.extend(negative.feed(interval))
                detected.extend(spike.feed(interval))
            ramp = evaluate_demand_ramp(
                day, list(demands) if demands is not None else [None] * 288
            )
            summary[day_str] = {
                "price": {"evaluated": 288, "missing": missing_price},
                "demand": {"evaluated": 288, "missing": missing_demand},
                "demand_ramp": ramp.reason,
            }
            if ramp.event is not None:
                detected.append(ramp.event)
                ramps[day] = ramp.event
        detected.extend(negative.finish())
        detected.extend(spike.finish())

        if suite == DETECTOR_VERSION_V2:
            detected_v2 = self._detect_v2(inputs, start, end, detected, ramps, summary)

        # Pin every member day's revision (cross-midnight runs touch days
        # beyond their owner day).
        events: list[tuple[Event, dict[str, object], dict[str, object]]] = []
        for event in detected:
            key = (
                _PRICE
                if event.type is not EventType.DEMAND_RAMP
                else Metric.DEMAND.value
            )
            sources: dict[str, object] = {
                key: {
                    day.isoformat(): str(rev) if rev else None
                    for day in _member_days(event)
                    for rev in [
                        price_revs.get(day)
                        if key == _PRICE
                        else grid_revs.get((key, "", day))
                    ]
                }
            }
            events.append(
                (
                    event,
                    sources,
                    self._coverage(event, key, price_revs, grid_revs, slots),
                )
            )
        return events, detected_v2, summary

    def _detect_v2(
        self,
        inputs: "_Inputs",
        start: date,
        end: date,
        detected: list[Event],
        ramps: dict[date, Event],
        summary: dict[str, dict[str, object]],
    ) -> list[tuple[Detected, dict[str, object], dict[str, object]]]:
        """Detector-v2 suite over the pinned snapshot: price reversals and
        grouped episodes over complete v1 runs, and unusual ramps against a
        preceding-history baseline. Insufficient baseline is recorded in the
        day coverage, never labelled "normal"."""
        price_revs, grid_revs, slots = (
            inputs.price_revs,
            inputs.grid_revs,
            inputs.slots,
        )
        price_index: dict[int, Decimal | None] = {}
        demand_index: dict[int, Decimal | None] = {}
        for rev_day, rev in price_revs.items():
            if rev in slots:
                for position, value in enumerate(_values(slots[rev], "price")):
                    price_index[rev_day.toordinal() * INTERVALS_PER_DAY + position] = (
                        value
                    )
        for (metric, series, rev_day), rev in grid_revs.items():
            if metric == Metric.DEMAND.value and not series and rev in slots:
                for position, value in enumerate(_values(slots[rev], "value")):
                    demand_index[rev_day.toordinal() * INTERVALS_PER_DAY + position] = (
                        value
                    )
        runs = [
            e
            for e in detected
            if e.type is EventType.NEGATIVE_PRICE_RUN and not e.edge_incomplete
        ]
        price_at = lambda i: price_index.get(i)  # noqa: E731
        out: list[tuple[Detected, dict[str, object], dict[str, object]]] = []

        for det in detect_price_reversals(runs, price_at):
            run = det.linked[0]
            evidence_days = _days(
                run.owner_day,
                date.fromordinal(
                    (
                        run.owner_day.toordinal() * INTERVALS_PER_DAY
                        + run.start_position
                        + run.interval_count
                        - 1
                        + REVERSAL_LOOKAHEAD_INTERVALS
                    )
                    // INTERVALS_PER_DAY
                )
                + timedelta(days=1),
            )
            sources: dict[str, object] = {
                _PRICE: {
                    d.isoformat(): (
                        str(src_rev) if (src_rev := price_revs.get(d)) else None
                    )
                    for d in evidence_days
                }
            }
            coverage: dict[str, object] = {
                # run span plus the complete six-hour look-ahead, all
                # verified present by the detector
                "evaluated": run.interval_count + REVERSAL_LOOKAHEAD_INTERVALS,
                "missing": 0,
                "edge_incomplete": False,
            }
            out.append((det, sources, coverage))

        for det in detect_negative_price_episodes(runs, price_at):
            episode_sources: dict[str, object] = {
                _PRICE: {
                    d.isoformat(): (
                        str(src_rev) if (src_rev := price_revs.get(d)) else None
                    )
                    for d in _member_days(det.event)
                }
            }
            episode_coverage: dict[str, object] = {
                "evaluated": det.event.interval_count,
                "missing": 0,
                "edge_incomplete": False,
            }
            out.append((det, episode_sources, episode_coverage))

        for day, ramp in ramps.items():
            classification, baseline = self._ramp_baseline(inputs, day, ramp.value)
            summary[day.isoformat()]["unusual_demand_ramp"] = classification.reason
            if classification.reason != "unusual":
                continue
            baseline_start = day - timedelta(days=RAMP_BASELINE_DAYS)
            det = Detected(
                event=Event(
                    type=EventType.UNUSUAL_DEMAND_RAMP,
                    owner_day=ramp.owner_day,
                    start_position=ramp.start_position,
                    interval_count=ramp.interval_count,
                    value=ramp.value,
                    edge_incomplete=False,
                ),
                detail={
                    "riseMw": str(ramp.value),
                    "baselineStart": baseline_start.isoformat(),
                    "baselineEnd": (day - timedelta(days=1)).isoformat(),
                    "dayClass": ("weekday" if day.weekday() < 5 else "weekend"),
                    "completeDays": baseline["complete_days"],
                    "classSamples": baseline["class_samples"],
                    "quantile": "P90",
                    "quantileValue": str(classification.quantile),
                    "minRiseMw": str(RAMP_MIN_RISE_MW),
                    "baselineRevisions": baseline["revisions"],
                },
                linked=(ramp,),
            )
            ramp_sources: dict[str, object] = {
                Metric.DEMAND.value: {
                    day.isoformat(): (
                        str(src_rev)
                        if (src_rev := grid_revs.get((Metric.DEMAND.value, "", day)))
                        else None
                    )
                }
            }
            ramp_coverage: dict[str, object] = {
                "evaluated": ramp.interval_count,
                "missing": 0,
                "edge_incomplete": False,
            }
            out.append((det, ramp_sources, ramp_coverage))
        return out

    def _ramp_baseline(
        self, inputs: "_Inputs", day: date, rise: Decimal
    ) -> tuple[RampClassification, dict[str, object]]:
        """Classify ``rise`` against the preceding 90-day same-class daily
        ramp distribution; also returns the baseline manifest for evidence."""
        grid_revs, slots = inputs.grid_revs, inputs.slots
        weekday = day.weekday() < 5
        baseline_start = day - timedelta(days=RAMP_BASELINE_DAYS)
        complete_days = 0
        class_samples: list[Decimal] = []
        revisions: dict[str, object] = {}
        for offset in range(RAMP_BASELINE_DAYS):
            baseline_day = baseline_start + timedelta(days=offset)
            rev = grid_revs.get((Metric.DEMAND.value, "", baseline_day))
            revisions[baseline_day.isoformat()] = str(rev) if rev else None
            if rev not in slots:
                continue
            values = _values(slots[rev], "value")
            evaluation = evaluate_demand_ramp(baseline_day, list(values))
            if evaluation.reason == "insufficient_coverage":
                continue
            complete_days += 1
            if (baseline_day.weekday() < 5) == weekday:
                class_samples.append(
                    evaluation.event.value
                    if evaluation.event is not None
                    else Decimal(0)
                )
        classification = classify_demand_ramp(rise, class_samples, complete_days)
        baseline = {
            "complete_days": complete_days,
            "class_samples": len(class_samples),
            "revisions": revisions,
        }
        return classification, baseline

    def _coverage(
        self,
        event: Event,
        key: str,
        price_revs: dict[date, UUID],
        grid_revs: dict[tuple[str, str, date], UUID],
        slots: dict[UUID, str],
    ) -> dict[str, object]:
        missing = 0
        for event_day in _member_days(event):
            rev = (
                price_revs.get(event_day)
                if key == _PRICE
                else grid_revs.get((key, "", event_day))
            )
            if rev is None or rev not in slots:
                missing += INTERVALS_PER_DAY
                continue
            values = _values(slots[rev], "price" if key == _PRICE else "value")
            # count only member positions of that day
            for i, v in enumerate(values):
                if v is None and self._is_member(event, event_day, i):
                    missing += 1
        return {
            "evaluated": event.interval_count,
            "missing": missing,
            "edge_incomplete": event.edge_incomplete,
        }

    @staticmethod
    def _is_member(event: Event, day: date, position: int) -> bool:
        index = day.toordinal() * INTERVALS_PER_DAY + position
        first = event.owner_day.toordinal() * INTERVALS_PER_DAY + event.start_position
        return first <= index <= first + event.interval_count - 1

    def _publish_inside(
        self,
        conn: sa.Connection,
        run_id: UUID,
        region: Region,
        start: date,
        end: date,
        suite: str,
        actor: str | None = None,
        attempt_key: str | None = None,
    ) -> Publication:
        # Pin a snapshot wide enough to cover 7-day replay windows that
        # reach past the publication window's last day. The v2 suite also
        # needs the preceding ramp-baseline history.
        snapshot_start = (
            start - timedelta(days=RAMP_BASELINE_DAYS)
            if suite == DETECTOR_VERSION_V2
            else start
        )
        inputs = self._snapshot_inputs(
            conn, region, snapshot_start, end + timedelta(days=REPLAY_MAX_DAYS - 1)
        )
        detected, detected_v2, summary = self._detect(inputs, start, end, suite)
        publication_id = uuid.uuid4()
        event_ids: list[UUID] = []
        identity: dict[tuple[EventType, date, int], UUID] = {}
        for event, sources, coverage in detected:
            event_id = self._upsert_event(
                conn, inputs, region, event, sources, coverage
            )
            event_ids.append(event_id)
            identity[(event.type, event.owner_day, event.start_position)] = event_id
        for det, sources, coverage in detected_v2:
            member_ids = [
                str(identity[(link.type, link.owner_day, link.start_position)])
                for link in det.linked
                if (link.type, link.owner_day, link.start_position) in identity
            ]
            detail = {**det.detail, "memberIds": member_ids}
            event_ids.append(
                self._upsert_event(
                    conn, inputs, region, det.event, sources, coverage, detail
                )
            )
        conn.execute(
            sa.text(
                "INSERT INTO grid_publication"
                " (id,region,start_day,end_exclusive,detector_version,coverage)"
                " VALUES (:id,:region,:start,:end,:version,"
                " CAST(:coverage AS jsonb))"
            ),
            {
                "id": publication_id,
                "region": region.name,
                "start": start,
                "end": end,
                "version": suite,
                "coverage": _canonical(summary),
            },
        )
        for event_id in event_ids:
            conn.execute(
                sa.text(
                    "INSERT INTO grid_publication_event"
                    " (publication_id,event_id) VALUES (:publication,:event)"
                ),
                {"publication": publication_id, "event": event_id},
            )
        conn.execute(
            sa.text(
                "INSERT INTO grid_catalogue_current"
                " (region,start_day,end_exclusive,publication_id)"
                " VALUES (:region,:start,:end,:publication)"
                " ON CONFLICT(region,start_day,end_exclusive) DO UPDATE"
                " SET publication_id=EXCLUDED.publication_id,"
                "     published_at=clock_timestamp()"
            ),
            {
                "region": region.name,
                "start": start,
                "end": end,
                "publication": publication_id,
            },
        )
        conn.execute(
            sa.text(
                "INSERT INTO grid_detection_run"
                " (id,region,start_day,end_exclusive,detector_version,status,"
                "  publication_id,actor,request_key)"
                " VALUES (:id,:region,:start,:end,:version,'COMPLETE',"
                " :publication,:actor,:key)"
            ),
            {
                "id": run_id,
                "region": region.name,
                "start": start,
                "end": end,
                "version": suite,
                "publication": publication_id,
                "actor": actor,
                "key": attempt_key,
            },
        )
        return Publication(
            publication_id,
            region,
            start,
            end,
            suite,
            len(event_ids),
            summary,
            datetime.now(UTC),
            run_id,
            actor,
            attempt_key,
        )

    def _upsert_event(
        self,
        conn: sa.Connection,
        inputs: "_Inputs",
        region: Region,
        event: Event,
        sources: dict[str, object],
        coverage: dict[str, object],
        detail: dict[str, object] | None = None,
    ) -> UUID:
        start_at = _instant(event.owner_day, event.start_position)
        end_at = _instant(
            event.owner_day, event.start_position + event.interval_count - 1
        )
        params = DETECTOR_PARAMS[event.type.value]
        event_version = DETECTOR_VERSIONS[event.type.value]
        latest = conn.execute(
            sa.text(
                "SELECT id, version, source_revisions, detail FROM grid_event"
                " WHERE region=:region AND type=:type"
                " AND detector_version=:version AND start_at=:start"
                " ORDER BY version DESC LIMIT 1"
            ),
            {
                "region": region.name,
                "type": event.type.value,
                "version": event_version,
                "start": start_at,
            },
        ).first()
        canonical_sources = _canonical(sources)
        if (
            latest is not None
            and _canonical(latest.source_revisions) == canonical_sources
            # v2 evidence (baseline manifest, members) is part of the event
            # identity — a corrected/backfilled baseline must re-version.
            and _canonical(latest.detail) == _canonical(detail)
            # Detector inputs can be unchanged while replay context (e.g. a
            # later price import) differs — pin drift still versions the event.
            and self._pins_match(conn, latest.id, inputs, event)
        ):
            return cast(UUID, latest.id)  # identical inputs — dedupe
        event_id = uuid.uuid4()
        version = 1 if latest is None else latest.version + 1
        conn.execute(
            sa.text(
                "INSERT INTO grid_event"
                " (id,region,type,detector_version,detector_params,market_day,"
                "  start_at,end_at,interval_count,value,edge_incomplete,"
                "  source_revisions,coverage,detail,version,supersedes)"
                " VALUES (:id,:region,:type,:dversion,"
                " CAST(:params AS jsonb),:day,:start,:end,:count,:value,"
                " :edge,CAST(:sources AS jsonb),CAST(:coverage AS jsonb),"
                " CAST(:detail AS jsonb),:version,:supersedes)"
            ),
            {
                "id": event_id,
                "region": region.name,
                "type": event.type.value,
                "dversion": event_version,
                "params": _canonical(params),
                "day": event.owner_day,
                "start": start_at,
                "end": end_at,
                "count": event.interval_count,
                "value": event.value,
                "edge": event.edge_incomplete,
                "sources": canonical_sources,
                "coverage": _canonical(coverage),
                "detail": None if detail is None else _canonical(detail),
                "version": version,
                "supersedes": latest.id if latest else None,
            },
        )
        self._materialise_replay(conn, inputs, event_id, region, event)
        return event_id

    # -- replay snapshots ------------------------------------------------------

    @staticmethod
    def _window_series(inputs: "_Inputs", days: list[date]) -> list[tuple[str, str]]:
        """Series with at least one pinned revision inside ``days`` — a
        series that only exists outside the window (e.g. baseline history
        under the v2 suite) never enters a replay manifest."""
        present = set(days)
        return sorted(
            {
                (m, s)
                for (m, s, d) in inputs.grid_revs
                if d in present and inputs.grid_revs[(m, s, d)] is not None
            }
        )

    @staticmethod
    def _pin_map(
        inputs: "_Inputs", days: list[date]
    ) -> dict[str, dict[str, str | None]]:
        """Revision id (or None) pinned per series key per member day."""
        pins: dict[str, dict[str, str | None]] = {
            _PRICE: {
                day.isoformat(): (
                    str(rev) if (rev := inputs.price_revs.get(day)) else None
                )
                for day in days
            }
        }
        for metric, series in GridCatalogue._window_series(inputs, days):
            pins[f"{metric}:{series}" if series else metric] = {
                day.isoformat(): (
                    str(rev)
                    if (rev := inputs.grid_revs.get((metric, series, day)))
                    else None
                )
                for day in days
            }
        return pins

    def _pins_match(
        self,
        conn: sa.Connection,
        event_id: UUID,
        inputs: "_Inputs",
        event: Event,
    ) -> bool:
        manifest_row = conn.execute(
            sa.text("SELECT manifest FROM grid_replay WHERE event_id=:id"),
            {"id": event_id},
        ).first()
        if manifest_row is None:
            return False
        days = _member_days(event)
        window_end = min(
            days[-1] + timedelta(days=1), days[0] + timedelta(days=REPLAY_MAX_DAYS)
        )
        stored = {
            s["metric"] + (f":{s['series']}" if s.get("series") else ""): s["days"]
            for s in manifest_row.manifest["series"]
        }
        return stored == self._pin_map(inputs, _days(days[0], window_end))

    def _materialise_replay(
        self,
        conn: sa.Connection,
        inputs: "_Inputs",
        event_id: UUID,
        region: Region,
        event: Event,
    ) -> None:
        days = _member_days(event)
        window_end = min(
            days[-1] + timedelta(days=1), days[0] + timedelta(days=REPLAY_MAX_DAYS)
        )
        span = _days(days[0], window_end)
        pins = self._pin_map(inputs, span)
        price_revs, grid_revs, slots = (
            inputs.price_revs,
            inputs.grid_revs,
            inputs.slots,
        )
        manifest_series: list[dict[str, object]] = []
        payload: dict[str, dict[str, list[object]]] = {}
        price_payload: dict[str, list[object]] = {}
        for day in span:
            rev = price_revs.get(day)
            if rev in slots:
                price_payload[day.isoformat()] = [
                    None if v is None else decimal_text.to_plain_string(v)
                    for v in _values(slots[rev], "price")
                ]
        if price_payload:
            payload[_PRICE] = price_payload
        manifest_series.append(
            {
                "metric": _PRICE,
                "unit": "AUD/MWh",
                "grid": "interval_end",
                "days": pins[_PRICE],
            }
        )
        for metric, series in self._window_series(inputs, span):
            key = f"{metric}:{series}" if series else metric
            series_payload: dict[str, list[object]] = {}
            for day in span:
                rev = grid_revs.get((metric, series, day))
                if rev in slots:
                    series_payload[day.isoformat()] = [
                        None if v is None else decimal_text.to_plain_string(v)
                        for v in _values(slots[rev], "value")
                    ]
            if series_payload:
                payload[key] = series_payload
            manifest_series.append(
                {
                    "metric": metric,
                    "series": series or None,
                    "unit": "MW",
                    "grid": "source_label",
                    "days": pins[key],
                }
            )
        manifest = {
            "event_id": str(event_id),
            "window": {
                "start_day": days[0].isoformat(),
                "end_exclusive": window_end.isoformat(),
            },
            "series": manifest_series,
        }
        conn.execute(
            sa.text(
                "INSERT INTO grid_replay"
                " (id,event_id,start_day,end_exclusive,manifest,payload)"
                " VALUES (:id,:event,:start,:end,"
                " CAST(:manifest AS jsonb),CAST(:payload AS jsonb))"
            ),
            {
                "id": uuid.uuid4(),
                "event": event_id,
                "start": days[0],
                "end": window_end,
                "manifest": json.dumps(manifest),
                "payload": json.dumps(payload),
            },
        )

    # -- reads ------------------------------------------------------------------

    def current(self, region: Region, start: date, end: date) -> Publication | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.text(
                    "SELECT p.id, p.coverage, p.created_at"
                    " FROM grid_catalogue_current c"
                    " JOIN grid_publication p ON p.id = c.publication_id"
                    " WHERE c.region=:region AND c.start_day=:start"
                    " AND c.end_exclusive=:end"
                ),
                {"region": region.name, "start": start, "end": end},
            ).first()
        if row is None:
            return None
        count = self._event_count(row.id)
        return Publication(
            row.id,
            region,
            start,
            end,
            DETECTOR_VERSION,
            count,
            row.coverage,
            _instant_utc(row.created_at),
        )

    @staticmethod
    def _publication(row: sa.Row[Any], event_count: int) -> Publication:
        return Publication(
            row.id,
            Region[row.region],
            row.start_day,
            row.end_exclusive,
            row.detector_version,
            event_count,
            row.coverage,
            _instant_utc(row.created_at),
            row.run_id,
            row.actor,
            row.request_key,
        )

    def publications(self, limit: int = 50) -> list[Publication]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT p.*, r.id AS run_id, r.actor, r.request_key"
                    " FROM grid_publication p"
                    " LEFT JOIN grid_detection_run r"
                    " ON r.publication_id = p.id"
                    " ORDER BY p.created_at DESC, p.id LIMIT :limit"
                ),
                {"limit": limit},
            ).all()
        return [self._publication(row, self._event_count(row.id)) for row in rows]

    def publication(self, id: UUID) -> Publication | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.text(
                    "SELECT p.*, r.id AS run_id, r.actor, r.request_key"
                    " FROM grid_publication p"
                    " LEFT JOIN grid_detection_run r"
                    " ON r.publication_id = p.id"
                    " WHERE p.id=:id"
                ),
                {"id": id},
            ).first()
        if row is None:
            return None
        return self._publication(row, self._event_count(row.id))

    def attempts(self, limit: int = 50) -> list[DetectionAttempt]:
        """Bounded publication-attempt history — COMPLETE and FAILED runs —
        for reconciling lost publish responses and inspecting correlation."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT id, region, start_day, end_exclusive,"
                    " detector_version, status, publication_id, diagnostic,"
                    " actor, request_key, created_at FROM grid_detection_run"
                    " ORDER BY created_at DESC, id LIMIT :limit"
                ),
                {"limit": limit},
            ).all()
        return [
            DetectionAttempt(
                row.id,
                Region[row.region],
                row.start_day,
                row.end_exclusive,
                row.detector_version,
                row.status,
                row.publication_id,
                row.diagnostic,
                row.actor,
                row.request_key,
                _instant_utc(row.created_at),
            )
            for row in rows
        ]

    def event_counts(self, publication: UUID) -> dict[str, int]:
        """Per-type event totals pinned to one publication."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT e.type, count(*) AS n FROM grid_publication_event p"
                    " JOIN grid_event e ON e.id = p.event_id"
                    " WHERE p.publication_id = :id GROUP BY e.type"
                ),
                {"id": publication},
            ).all()
        return {row.type: row.n for row in rows}

    def baseline_readiness(
        self, region: Region, start: date, end: date
    ) -> list[BaselineReadiness]:
        """Per-candidate-day ramp-baseline readiness: each day's own 90-day
        preceding window counts demand-complete days and same-class days
        against the detector's thresholds. Computed from coverage counts
        with prefix sums — one bounded query regardless of window size."""
        if not start < end or start + timedelta(days=MAX_PUBLICATION_DAYS) < end:
            raise ValueError("Candidate window must contain 1-31 days")
        first_baseline = start - timedelta(days=RAMP_BASELINE_DAYS)
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT c.market_day, r.valid_count FROM grid_current c"
                    " JOIN grid_revision r ON r.id = c.revision_id"
                    " WHERE c.region = :region AND c.metric = 'demand'"
                    " AND c.market_day >= :start AND c.market_day < :end"
                ),
                {
                    "region": region.name,
                    "start": first_baseline,
                    "end": end,
                },
            ).all()
        complete = {row.market_day for row in rows if row.valid_count == 288}
        # Prefix-sum weekday/weekend completeness separately — each
        # candidate day's same-class count picks the matching series, and
        # every 90-day window lookup is O(1).
        span = (end - first_baseline).days
        totals = [0] * (span + 1)
        classes = {"weekday": [0] * (span + 1), "weekend": [0] * (span + 1)}
        for offset in range(span):
            day = first_baseline + timedelta(days=offset)
            weekday = day.weekday() < 5
            done = day in complete
            totals[offset + 1] = totals[offset] + done
            for name, series in classes.items():
                series[offset + 1] = series[offset] + (
                    done and weekday == (name == "weekday")
                )
        readiness: list[BaselineReadiness] = []
        for day in _days(start, end):
            offset = (day - first_baseline).days
            complete_days = totals[offset] - totals[offset - RAMP_BASELINE_DAYS]
            series = classes["weekday" if day.weekday() < 5 else "weekend"]
            class_days = series[offset] - series[offset - RAMP_BASELINE_DAYS]
            readiness.append(
                BaselineReadiness(
                    day,
                    complete_days,
                    class_days,
                    complete_days >= RAMP_MIN_COMPLETE_DAYS
                    and class_days >= RAMP_MIN_CLASS_DAYS,
                )
            )
        return readiness

    def _event_count(self, publication: UUID) -> int:
        with self.engine.connect() as conn:
            return cast(
                int,
                conn.execute(
                    sa.text(
                        "SELECT count(*) FROM grid_publication_event"
                        " WHERE publication_id=:id"
                    ),
                    {"id": publication},
                ).scalar_one(),
            )

    def events(self, publication: UUID) -> list[StoredEvent]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT e.*, NOT EXISTS"
                    " (SELECT 1 FROM grid_event s WHERE s.supersedes = e.id)"
                    " AS current FROM grid_event e"
                    " JOIN grid_publication_event p ON p.event_id = e.id"
                    " WHERE p.publication_id=:id ORDER BY e.start_at, e.type"
                ),
                {"id": publication},
            ).all()
        return [_stored_event(row) for row in rows]

    def replay(
        self, event_id: UUID, start: date | None = None, end: date | None = None
    ) -> dict[str, object] | None:
        """Immutable replay snapshot; an optional sub-window must fit inside
        the stored window."""
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.text(
                    "SELECT start_day, end_exclusive, manifest, payload"
                    " FROM grid_replay WHERE event_id=:id"
                ),
                {"id": event_id},
            ).first()
        if row is None:
            return None
        if (start is not None or end is not None) and (
            start is None
            or end is None
            or start < row.start_day
            or end > row.end_exclusive
            or not start < end
        ):
            raise ValueError("Replay window must fit the stored snapshot")
        manifest = row.manifest
        payload = row.payload
        if start is not None and end is not None:
            days = {
                (start + timedelta(days=i)).isoformat()
                for i in range((end - start).days)
            }
            manifest = {
                **manifest,
                "window": {
                    "start_day": start.isoformat(),
                    "end_exclusive": end.isoformat(),
                },
                "series": [
                    {
                        **series,
                        "days": {d: r for d, r in series["days"].items() if d in days},
                    }
                    for series in manifest["series"]
                ],
            }
            payload = {
                key: {d: v for d, v in by_day.items() if d in days}
                for key, by_day in payload.items()
            }
        return {
            "startDay": row.start_day,
            "endExclusive": row.end_exclusive,
            "manifest": manifest,
            "payload": payload,
        }

    # -- public catalogue reads ---------------------------------------------------

    def current_publication(self, region: Region) -> Publication | None:
        """The newest current catalogue publication for a region."""
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.text(
                    "SELECT p.* FROM grid_catalogue_current c"
                    " JOIN grid_publication p ON p.id = c.publication_id"
                    " WHERE c.region=:region"
                    " ORDER BY c.published_at DESC, p.id LIMIT 1"
                ),
                {"region": region.name},
            ).first()
        if row is None:
            return None
        return Publication(
            row.id,
            Region[row.region],
            row.start_day,
            row.end_exclusive,
            row.detector_version,
            self._event_count(row.id),
            row.coverage,
            _instant_utc(row.created_at),
        )

    def _scope_params(self, publication: UUID, query: EventQuery) -> dict[str, object]:
        return {
            "publication": publication,
            "type": query.event_type.value if query.event_type else None,
            "from_start": (
                datetime.combine(query.start, datetime.min.time(), tzinfo=NEM_OFFSET)
                if query.start
                else None
            ),
            "to_end": (
                datetime.combine(
                    query.end + timedelta(days=1),
                    datetime.min.time(),
                    tzinfo=NEM_OFFSET,
                )
                if query.end
                else None
            ),
            "min_dur": query.min_duration_minutes,
            "value_gte": query.value_gte,
            "value_lte": query.value_lte,
        }

    def catalogue_totals(
        self, publication: UUID, query: EventQuery
    ) -> tuple[int, dict[str, int]]:
        """Matching total and per-type counts, independent of page size."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT e.type, count(*)"
                    + _EVENTS_FROM
                    + " WHERE "
                    + _SCOPE_WHERE
                    + " GROUP BY e.type"
                ),
                self._scope_params(publication, query),
            ).all()
        totals = {row[0]: int(row[1]) for row in rows}
        return sum(totals.values()), totals

    def catalogue_events(
        self,
        publication: UUID,
        query: EventQuery,
        limit: int,
        cursor: tuple[Decimal | None, datetime, UUID] | None,
    ) -> tuple[list[StoredEvent], bool]:
        """One page of a pinned publication under the query's sort; returns
        the page and whether more events follow. ``cursor`` is the decoded
        sort tuple (primary value, start_at, id) of the last row."""
        column, direction, tie = _SORTS[query.sort]
        if query.sort in ("newest", "oldest"):
            order = f"e.start_at {direction}, e.id {tie}"
            keyset = _KEYSET[query.sort]
        elif query.sort == "deepest":
            order = f"{column} {direction}, e.start_at {tie}, e.id {tie}"
            keyset = _KEYSET["asc_value"]
        else:
            order = f"{column} {direction}, e.start_at {tie}, e.id {tie}"
            keyset = _KEYSET["desc_primary"].replace("{primary}", column)
        params = {
            **self._scope_params(publication, query),
            "limit": limit + 1,
            "k0": cursor[0] if cursor else None,
            "k1": cursor[1].isoformat() if cursor else None,
            "k2": str(cursor[2]) if cursor else None,
        }
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT e.*, NOT EXISTS"  # noqa: S608 -- static clauses, bound params only
                    " (SELECT 1 FROM grid_event s WHERE s.supersedes = e.id)"
                    " AS current"
                    + _EVENTS_FROM
                    + " WHERE "
                    + _SCOPE_WHERE
                    + (" AND " + keyset if cursor else "")
                    + f" ORDER BY {order} LIMIT :limit"
                ),
                params,
            ).all()
        return [_stored_event(row) for row in rows[:limit]], len(rows) > limit

    def all_scope_events(
        self, publication: UUID, query: EventQuery
    ) -> list[StoredEvent]:
        """Every event matching the scope — ranking works over the whole
        publication, never a page. Publications are bounded (<= 31 days)."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT e.*, NOT EXISTS"  # noqa: S608 -- static clauses, bound params only
                    " (SELECT 1 FROM grid_event s WHERE s.supersedes = e.id)"
                    " AS current"
                    + _EVENTS_FROM
                    + " WHERE "
                    + _SCOPE_WHERE
                    + " ORDER BY e.start_at, e.id"
                ),
                self._scope_params(publication, query),
            ).all()
        return [_stored_event(row) for row in rows]

    @staticmethod
    def _eligible(event: StoredEvent) -> bool:
        missing = event.coverage.get("missing")
        return not event.edge_incomplete and missing == 0

    @staticmethod
    def _candidate(event: StoredEvent) -> Candidate:
        detail = event.detail or {}
        linked: list[tuple[EventType, datetime]] = []
        if event.type is EventType.UNUSUAL_DEMAND_RAMP:
            linked.append((EventType.DEMAND_RAMP, event.start_at))
        elif event.type is EventType.PRICE_REVERSAL:
            linked += [
                (
                    EventType.NEGATIVE_PRICE_RUN,
                    datetime.fromisoformat(m["startAt"]),
                )
                for m in cast(list[dict[str, Any]], detail.get("memberRuns", []))
            ]
        elif event.type is EventType.NEGATIVE_PRICE_EPISODE:
            linked += [
                (
                    EventType.NEGATIVE_PRICE_RUN,
                    datetime.fromisoformat(m["startAt"]),
                )
                for m in cast(list[dict[str, Any]], detail.get("members", []))
            ]
        return Candidate(
            id=event.id,
            type=event.type,
            market_day=event.market_day,
            start_at=event.start_at,
            interval_count=event.interval_count,
            value=event.value,
            linked=tuple(linked),
        )

    def highlights(
        self, publication: UUID, query: EventQuery
    ) -> tuple[
        list[tuple[StoredEvent, Selection]],
        int,
        dict[str, int],
        int,
        int,
    ]:
        """``highlights-v2`` selection over the whole pinned publication.

        Returns the selected (event, Selection) pairs in display order plus
        matching total, per-type totals, eligible and excluded counts.
        Incomplete or unknown-coverage events never qualify but still count
        towards ``excluded``.
        """
        events = self.all_scope_events(publication, query)
        matching, totals = (
            len(events),
            {t.value: sum(1 for e in events if e.type is t) for t in EventType},
        )
        eligible = [e for e in events if self._eligible(e)]
        chosen = select(
            [self._candidate(e) for e in eligible],
            event_type=query.event_type,
            version=HIGHLIGHTS_V2,
        )
        by_id = {e.id: e for e in eligible}
        selections = [(by_id[s.candidate.id], s) for s in chosen]
        return selections, matching, totals, len(eligible), len(events) - len(eligible)

    # -- card previews ---------------------------------------------------------

    def preview(self, event_id: UUID) -> dict[str, object] | None:
        """Bounded event-local price/demand preview from the immutable
        replay snapshot — never current data. ``None`` when no snapshot or no
        usable context exists."""
        cached = self._previews.get(event_id)
        if cached is not None:
            return cached
        event = self.event(event_id)
        if event is None:
            return None
        replay = self.replay(event_id)
        if replay is None:
            return None
        metric = (
            "demand"
            if event.type in (EventType.DEMAND_RAMP, EventType.UNUSUAL_DEMAND_RAMP)
            else _PRICE
        )
        manifest = cast(dict[str, Any], replay["manifest"])
        all_payload = cast(dict[str, dict[str, list[str | None]]], replay["payload"])
        payload = all_payload.get(metric, {})
        window_start = date.fromisoformat(manifest["window"]["start_day"])
        day_count = (
            date.fromisoformat(manifest["window"]["end_exclusive"]) - window_start
        ).days
        origin = window_start.toordinal() * INTERVALS_PER_DAY

        def index_of(instant: datetime) -> int:
            local = instant.astimezone(NEM_OFFSET)
            return (
                local.toordinal() * INTERVALS_PER_DAY
                + (local.hour * 60 + local.minute) // 5
                - 1
                - origin
            )

        detail = event.detail or {}
        ranges: list[tuple[int, int]] = []
        member_ranges = cast(
            list[dict[str, str]],
            detail.get("memberRuns") or detail.get("members") or [],
        )
        if member_ranges:
            ranges = [
                (
                    index_of(datetime.fromisoformat(m["startAt"])),
                    index_of(datetime.fromisoformat(m["endAt"])),
                )
                for m in member_ranges
            ]
        else:
            ranges = [(index_of(event.start_at), index_of(event.end_at))]
        first, last = ranges[0][0], ranges[-1][1]
        lo = max(0, first - PREVIEW_CONTEXT_INTERVALS)
        hi = min(day_count * INTERVALS_PER_DAY - 1, last + PREVIEW_CONTEXT_INTERVALS)
        if hi <= lo:
            return None
        raw: list[Decimal | None] = []
        for i in range(lo, hi + 1):
            day_key = (
                window_start + timedelta(days=i // INTERVALS_PER_DAY)
            ).isoformat()
            values = payload.get(day_key)
            raw_v = None if values is None else values[i % INTERVALS_PER_DAY]
            raw.append(decimal_text.parse(raw_v) if raw_v is not None else None)
        n = len(raw)
        slots = min(n, PREVIEW_MAX_SLOTS)
        out_slots: list[dict[str, object]] = []
        for s in range(slots):
            a, b = s * n // slots, (s + 1) * n // slots
            chunk = raw[a:b]
            present = [v for v in chunk if v is not None]
            out_slots.append(
                {
                    "min": (
                        decimal_text.to_plain_string(min(present)) if present else None
                    ),
                    "max": (
                        decimal_text.to_plain_string(max(present)) if present else None
                    ),
                    "gap": len(present) != len(chunk),
                }
            )

        def slot_of(index: int) -> int:
            return min((index - lo) * slots // n, slots - 1)

        event_slots = [
            {"startSlot": slot_of(a), "endSlot": slot_of(b)} for a, b in ranges
        ]
        markers: dict[str, int] = {}
        if event.type is EventType.PRICE_REVERSAL and "peakAt" in detail:
            markers["peakSlot"] = slot_of(
                index_of(datetime.fromisoformat(str(detail["peakAt"])))
            )
        result: dict[str, object] = {
            "version": PREVIEW_VERSION,
            "metric": metric,
            "unit": "MW" if metric == "demand" else "AUD/MWh",
            "intervalMinutes": 5,
            "startAt": instant_label(lo + origin),
            "endAt": instant_label(hi + origin),
            "sourcePoints": n,
            "slots": out_slots,
            "eventRanges": event_slots,
            "markers": markers,
            "localScale": True,
        }
        if len(self._previews) >= 512:
            self._previews.clear()
        self._previews[event_id] = result
        return result

    def replay_window(self, event_id: UUID) -> tuple[date, date] | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.text(
                    "SELECT start_day, end_exclusive FROM grid_replay"
                    " WHERE event_id=:id"
                ),
                {"id": event_id},
            ).first()
        return None if row is None else (row.start_day, row.end_exclusive)

    def event(self, id: UUID) -> StoredEvent | None:
        """Any stored version — superseded ids remain reproducible."""
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.text(
                    "SELECT e.*, NOT EXISTS"
                    " (SELECT 1 FROM grid_event s WHERE s.supersedes = e.id)"
                    " AS current FROM grid_event e WHERE e.id=:id"
                ),
                {"id": id},
            ).first()
        return None if row is None else _stored_event(row)


def _instant_utc(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo else value


def _stored_event(row: sa.Row[tuple[object, ...]]) -> StoredEvent:
    return StoredEvent(
        row.id,
        Region[row.region],
        EventType(row.type),
        row.detector_version,
        row.detector_params,
        row.market_day,
        _instant_utc(row.start_at),
        _instant_utc(row.end_at),
        row.interval_count,
        row.value,
        row.edge_incomplete,
        row.source_revisions,
        row.coverage,
        row.detail,
        row.version,
        not row.current,
    )
