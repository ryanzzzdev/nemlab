"""``GridStore`` — versioned per-series grid observations.

Same revision discipline as ``PriceStore``: immutable content-keyed
revisions, a mutable ``grid_current`` pointer fenced by ``retrieved_at``,
and one audit row per provider request. ``series`` is ``""`` for
single-series metrics and the fueltech for ``power``.
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
from nemlab_core.prices import Region
from nemlab_infrastructure.grid.batch import GridBatch, Metric, Slot
from nemlab_infrastructure.grid.source import GridFetch
from nemlab_infrastructure.prices.batch import Kind

SeriesKey = tuple[Metric, str]


@dataclass(frozen=True)
class Coverage:
    revision: UUID
    valid: int
    missing: int
    source_null: int
    retrieved_at: datetime

    @property
    def complete(self) -> bool:
        return self.valid == 288


@dataclass(frozen=True)
class Attempt:
    id: UUID
    metrics: tuple[str, ...]
    retrieved_at: datetime
    status: str
    revision_count: int
    response_hash: str | None
    source_version: str | None
    diagnostic: str | None


def _slots_json(slots: tuple[Slot, ...]) -> str:
    parts = []
    for slot in slots:
        value = (
            "null" if slot.value is None else decimal_text.to_plain_string(slot.value)
        )
        parts.append(f'{{"kind":"{slot.kind.name}","value":{value}}}')
    return "[" + ",".join(parts) + "]"


def _read_slots(text: str) -> tuple[Slot, ...]:
    raw = json.loads(text, parse_float=Decimal, parse_int=Decimal)
    return tuple(
        Slot(
            Kind[entry["kind"]],
            None if entry["value"] is None else Decimal(str(entry["value"])),
        )
        for entry in raw
    )


def _instant(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo else value


class GridStore:
    def __init__(self, engine: sa.engine.Engine) -> None:
        self.engine = engine

    # -- writes ---------------------------------------------------------------

    def save(self, fetch: GridFetch) -> dict[SeriesKey, UUID]:
        """Persist every series revision + current pointers + one attempt
        row, atomically. Identical content dedupes to the same revision."""
        with self.engine.begin() as conn:
            revisions = {}
            for batch in fetch.series:
                revisions[(batch.metric, batch.series)] = self._save_series(
                    conn, batch, fetch.retrieved_at
                )
            conn.execute(
                sa.text(
                    "INSERT INTO grid_import_attempt"
                    " (id,region,market_day,metrics,retrieved_at,status,"
                    "  revision_count,response_hash,source_version)"
                    " VALUES (:id,:region,:day,:metrics,:at,:status,:count,"
                    "  :resp,:version)"
                ),
                {
                    "id": uuid.uuid4(),
                    "region": fetch.series[0].region.name,
                    "day": fetch.series[0].day,
                    "metrics": sorted({b.metric.value for b in fetch.series}),
                    "at": fetch.retrieved_at,
                    "status": "COMPLETE"
                    if all(b.complete() for b in fetch.series)
                    else "INCOMPLETE",
                    "count": len(fetch.series),
                    "resp": fetch.response_hash,
                    "version": fetch.source_version,
                },
            )
        return revisions

    def _save_series(
        self, conn: sa.Connection, batch: GridBatch, retrieved_at: datetime
    ) -> UUID:
        conn.execute(
            sa.text(
                "INSERT INTO grid_revision"
                " (id,region,metric,series,market_day,content_hash,slots,"
                "  valid_count,missing_count,null_count)"
                " VALUES (:id,:region,:metric,:series,:day,:hash,"
                " CAST(:slots AS jsonb),:valid,:missing,:nulls)"
                " ON CONFLICT(region,metric,series,market_day,content_hash)"
                " DO NOTHING"
            ),
            {
                "id": uuid.uuid4(),
                "region": batch.region.name,
                "metric": batch.metric.value,
                "series": batch.series,
                "day": batch.day,
                "hash": batch.content_hash(),
                "slots": _slots_json(batch.slots),
                "valid": batch.count(Kind.VALUE),
                "missing": batch.count(Kind.MISSING),
                "nulls": batch.count(Kind.SOURCE_NULL),
            },
        )
        revision = cast(
            UUID,
            conn.execute(
                sa.text(
                    "SELECT id FROM grid_revision"
                    " WHERE region=:region AND metric=:metric"
                    " AND series=:series AND market_day=:day"
                    " AND content_hash=:hash"
                ),
                {
                    "region": batch.region.name,
                    "metric": batch.metric.value,
                    "series": batch.series,
                    "day": batch.day,
                    "hash": batch.content_hash(),
                },
            ).scalar_one(),
        )
        conn.execute(
            sa.text(
                "INSERT INTO grid_current"
                " (region,metric,series,market_day,revision_id,retrieved_at)"
                " VALUES (:region,:metric,:series,:day,:revision,:at)"
                " ON CONFLICT(region,metric,series,market_day) DO UPDATE"
                " SET revision_id=EXCLUDED.revision_id,"
                "     retrieved_at=EXCLUDED.retrieved_at"
                " WHERE grid_current.retrieved_at <= EXCLUDED.retrieved_at"
            ),
            {
                "region": batch.region.name,
                "metric": batch.metric.value,
                "series": batch.series,
                "day": batch.day,
                "revision": revision,
                "at": retrieved_at,
            },
        )
        return revision

    def record_failure(
        self,
        region: Region,
        day: date,
        metrics: tuple[str, ...],
        at: datetime,
        category: str,
    ) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO grid_import_attempt"
                    " (id,region,market_day,metrics,retrieved_at,status,"
                    "  revision_count,diagnostic)"
                    " VALUES (:id,:region,:day,:metrics,:at,'FAILED',0,:diag)"
                ),
                {
                    "id": uuid.uuid4(),
                    "region": region.name,
                    "day": day,
                    "metrics": list(metrics),
                    "at": at,
                    "diag": category,
                },
            )

    # -- reads ----------------------------------------------------------------

    def coverage(self, region: Region, day: date) -> dict[SeriesKey, Coverage]:
        """Current-revision coverage for every stored series of a day."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT c.metric, c.series, r.id, r.valid_count,"
                    " r.missing_count, r.null_count, c.retrieved_at"
                    " FROM grid_current c"
                    " JOIN grid_revision r ON r.id = c.revision_id"
                    " WHERE c.region = :region AND c.market_day = :day"
                    " ORDER BY c.metric, c.series"
                ),
                {"region": region.name, "day": day},
            ).all()
        return {
            (Metric(row.metric), row.series): Coverage(
                row.id,
                row.valid_count,
                row.missing_count,
                row.null_count,
                _instant(row.retrieved_at),
            )
            for row in rows
        }

    def coverage_range(
        self,
        region: Region,
        metric: Metric,
        series: str,
        start: date,
        end: date,
    ) -> dict[date, Coverage]:
        if not start < end or start + timedelta(days=31) < end:
            raise ValueError("Coverage range must contain 1-31 days")
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT c.market_day, r.id, r.valid_count, r.missing_count,"
                    " r.null_count, c.retrieved_at FROM grid_current c"
                    " JOIN grid_revision r ON r.id = c.revision_id"
                    " WHERE c.region = :region AND c.metric = :metric"
                    " AND c.series = :series AND c.market_day >= :start"
                    " AND c.market_day < :end ORDER BY c.market_day"
                ),
                {
                    "region": region.name,
                    "metric": metric.value,
                    "series": series,
                    "start": start,
                    "end": end,
                },
            ).all()
        return {
            row.market_day: Coverage(
                row.id,
                row.valid_count,
                row.missing_count,
                row.null_count,
                _instant(row.retrieved_at),
            )
            for row in rows
        }

    def history(self, region: Region, day: date) -> list[Attempt]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT * FROM grid_import_attempt"
                    " WHERE region = :region AND market_day = :day"
                    " ORDER BY retrieved_at, id"
                ),
                {"region": region.name, "day": day},
            ).all()
        return [
            Attempt(
                row.id,
                tuple(row.metrics),
                _instant(row.retrieved_at),
                row.status,
                row.revision_count,
                row.response_hash,
                row.source_version,
                row.diagnostic,
            )
            for row in rows
        ]

    def series_keys(self, region: Region, day: date) -> list[SeriesKey]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT DISTINCT metric, series FROM grid_revision"
                    " WHERE region = :region AND market_day = :day"
                    " ORDER BY metric, series"
                ),
                {"region": region.name, "day": day},
            ).all()
        return [(Metric(row.metric), row.series) for row in rows]

    def batch(
        self, region: Region, metric: Metric, series: str, day: date
    ) -> GridBatch | None:
        """Current-revision series; ``None`` when the series-day was never
        imported — distinct from a stored all-MISSING series."""
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.text(
                    "SELECT r.slots::text AS slots FROM grid_current c"
                    " JOIN grid_revision r ON r.id = c.revision_id"
                    " WHERE c.region = :region AND c.metric = :metric"
                    " AND c.series = :series AND c.market_day = :day"
                ),
                {
                    "region": region.name,
                    "metric": metric.value,
                    "series": series,
                    "day": day,
                },
            ).first()
        if row is None:
            return None
        return GridBatch(region, metric, series, day, _read_slots(row.slots))

    def revision(self, id: UUID) -> GridBatch:
        """Exact replay of one pinned revision — corrections never rewrite it."""
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.text(
                    "SELECT region, metric, series, market_day,"
                    " slots::text AS slots FROM grid_revision WHERE id = :id"
                ),
                {"id": id},
            ).one()
        return GridBatch(
            Region[row.region],
            Metric(row.metric),
            row.series,
            row.market_day,
            _read_slots(row.slots),
        )

    def values(
        self, region: Region, metric: Metric, series: str, day: date
    ) -> tuple[Decimal | None, ...] | None:
        """Current values for detectors — ``None`` slot = missing or
        source-null (both non-observations); ``None`` result = no series."""
        batch = self.batch(region, metric, series, day)
        if batch is None:
            return None
        return tuple(
            slot.value if slot.kind is Kind.VALUE else None for slot in batch.slots
        )
