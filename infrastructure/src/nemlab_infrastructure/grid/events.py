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
from typing import cast
from uuid import UUID

import sqlalchemy as sa

from nemlab_core import decimal_text
from nemlab_core.detectors import (
    DETECTOR_PARAMS,
    DETECTOR_VERSION,
    INTERVALS_PER_DAY,
    Event,
    EventType,
    Interval,
    evaluate_demand_ramp,
    negative_price_run_scanner,
    price_spike_scanner,
)
from nemlab_core.prices import NEM_OFFSET, Region
from nemlab_infrastructure.grid.batch import Metric
from nemlab_infrastructure.prices.batch import Kind

MAX_PUBLICATION_DAYS = 31
REPLAY_MAX_DAYS = 7

_PRICE = "price"  # virtual series key; prices live in price_revision


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

    # -- publication ----------------------------------------------------------

    def publish(self, region: Region, start: date, end: date) -> Publication:
        """Detect, version, snapshot and atomically publish a window."""
        if not start < end or start + timedelta(days=MAX_PUBLICATION_DAYS) < end:
            raise ValueError("Publication window must contain 1-31 days")
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
                publication = self._publish_inside(conn, run_id, region, start, end)
        except Exception as failure:
            self._record_run(run_id, region, start, end, str(failure)[:500])
            raise
        return publication

    def _record_run(
        self,
        run_id: UUID,
        region: Region,
        start: date,
        end: date,
        diagnostic: str,
    ) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO grid_detection_run"
                    " (id,region,start_day,end_exclusive,detector_version,"
                    "  status,diagnostic)"
                    " VALUES (:id,:region,:start,:end,:version,'FAILED',:diag)"
                ),
                {
                    "id": run_id,
                    "region": region.name,
                    "start": start,
                    "end": end,
                    "version": DETECTOR_VERSION,
                    "diag": diagnostic,
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
        self, inputs: "_Inputs", start: date, end: date
    ) -> tuple[
        list[tuple[Event, dict[str, object], dict[str, object]]],
        dict[str, dict[str, object]],
    ]:
        """Run detectors; return (event, source_revisions, coverage) triples
        plus the per-day publication coverage summary."""
        price_revs, grid_revs, slots = (
            inputs.price_revs,
            inputs.grid_revs,
            inputs.slots,
        )
        negative = negative_price_run_scanner()
        spike = price_spike_scanner()
        detected: list[Event] = []
        summary: dict[str, dict[str, object]] = {}
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
        detected.extend(negative.finish())
        detected.extend(spike.finish())
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
        return events, summary

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
    ) -> Publication:
        # Pin a snapshot wide enough to cover 7-day replay windows that
        # reach past the publication window's last day.
        inputs = self._snapshot_inputs(
            conn, region, start, end + timedelta(days=REPLAY_MAX_DAYS - 1)
        )
        detected, summary = self._detect(inputs, start, end)
        publication_id = uuid.uuid4()
        event_ids: list[UUID] = []
        for event, sources, coverage in detected:
            event_ids.append(
                self._upsert_event(conn, inputs, region, event, sources, coverage)
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
                "version": DETECTOR_VERSION,
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
                "  publication_id)"
                " VALUES (:id,:region,:start,:end,:version,'COMPLETE',:publication)"
            ),
            {
                "id": run_id,
                "region": region.name,
                "start": start,
                "end": end,
                "version": DETECTOR_VERSION,
                "publication": publication_id,
            },
        )
        return Publication(
            publication_id,
            region,
            start,
            end,
            DETECTOR_VERSION,
            len(event_ids),
            summary,
            datetime.now(UTC),
        )

    def _upsert_event(
        self,
        conn: sa.Connection,
        inputs: "_Inputs",
        region: Region,
        event: Event,
        sources: dict[str, object],
        coverage: dict[str, object],
    ) -> UUID:
        start_at = _instant(event.owner_day, event.start_position)
        end_at = _instant(
            event.owner_day, event.start_position + event.interval_count - 1
        )
        params = DETECTOR_PARAMS[event.type.value]
        latest = conn.execute(
            sa.text(
                "SELECT id, version, source_revisions FROM grid_event"
                " WHERE region=:region AND type=:type"
                " AND detector_version=:version AND start_at=:start"
                " ORDER BY version DESC LIMIT 1"
            ),
            {
                "region": region.name,
                "type": event.type.value,
                "version": DETECTOR_VERSION,
                "start": start_at,
            },
        ).first()
        canonical_sources = _canonical(sources)
        if (
            latest is not None
            and _canonical(latest.source_revisions) == canonical_sources
        ):
            return cast(UUID, latest.id)  # identical inputs — dedupe
        event_id = uuid.uuid4()
        version = 1 if latest is None else latest.version + 1
        conn.execute(
            sa.text(
                "INSERT INTO grid_event"
                " (id,region,type,detector_version,detector_params,market_day,"
                "  start_at,end_at,interval_count,value,edge_incomplete,"
                "  source_revisions,coverage,version,supersedes)"
                " VALUES (:id,:region,:type,:dversion,"
                " CAST(:params AS jsonb),:day,:start,:end,:count,:value,"
                " :edge,CAST(:sources AS jsonb),CAST(:coverage AS jsonb),"
                " :version,:supersedes)"
            ),
            {
                "id": event_id,
                "region": region.name,
                "type": event.type.value,
                "dversion": DETECTOR_VERSION,
                "params": _canonical(params),
                "day": event.owner_day,
                "start": start_at,
                "end": end_at,
                "count": event.interval_count,
                "value": event.value,
                "edge": event.edge_incomplete,
                "sources": canonical_sources,
                "coverage": _canonical(coverage),
                "version": version,
                "supersedes": latest.id if latest else None,
            },
        )
        self._materialise_replay(conn, inputs, event_id, region, event)
        return event_id

    # -- replay snapshots ------------------------------------------------------

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
        price_revs, grid_revs, slots = (
            inputs.price_revs,
            inputs.grid_revs,
            inputs.slots,
        )
        manifest_series: list[dict[str, object]] = []
        payload: dict[str, dict[str, list[object]]] = {}
        price_payload: dict[str, list[object]] = {}
        price_days: dict[str, str | None] = {}
        for day in _days(days[0], window_end):
            rev = price_revs.get(day)
            price_days[day.isoformat()] = str(rev) if rev else None
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
                "days": price_days,
            }
        )
        seen = sorted({(m, s) for (m, s, _d) in grid_revs})
        for metric, series in seen:
            day_map: dict[str, str | None] = {}
            series_payload: dict[str, list[object]] = {}
            for day in _days(days[0], window_end):
                rev = grid_revs.get((metric, series, day))
                day_map[day.isoformat()] = str(rev) if rev else None
                if rev in slots:
                    series_payload[day.isoformat()] = [
                        None if v is None else decimal_text.to_plain_string(v)
                        for v in _values(slots[rev], "value")
                    ]
            key = f"{metric}:{series}" if series else metric
            if series_payload:
                payload[key] = series_payload
            manifest_series.append(
                {
                    "metric": metric,
                    "series": series or None,
                    "unit": "MW",
                    "grid": "source_label",
                    "days": day_map,
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

    def publications(self, limit: int = 50) -> list[Publication]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT * FROM grid_publication"
                    " ORDER BY created_at DESC, id LIMIT :limit"
                ),
                {"limit": limit},
            ).all()
        return [
            Publication(
                row.id,
                Region[row.region],
                row.start_day,
                row.end_exclusive,
                row.detector_version,
                self._event_count(row.id),
                row.coverage,
                _instant_utc(row.created_at),
            )
            for row in rows
        ]

    def publication(self, id: UUID) -> Publication | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.text("SELECT * FROM grid_publication WHERE id=:id"), {"id": id}
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

    def replay(self, event_id: UUID) -> dict[str, object] | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.text("SELECT manifest, payload FROM grid_replay WHERE event_id=:id"),
                {"id": event_id},
            ).first()
        if row is None:
            return None
        return {"manifest": row.manifest, "payload": row.payload}


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
        row.version,
        not row.current,
    )
