"""``PriceStore`` — SQLAlchemy Core port of the Java JdbcTemplate store.

All statements are parameterised text SQL identical to the Java queries,
including the optimistic checkpoint fence in ``commit_day`` and the
``retrieved_at`` freshness guard on ``price_current``. JSONB is sent as text
and cast, matching ``?::jsonb``.
"""

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import UUID

import sqlalchemy as sa

from nemlab_core import decimal_text
from nemlab_core.prices import NEM_OFFSET, PriceDay, Region
from nemlab_infrastructure.prices.batch import Kind, PriceBatch, Slot
from nemlab_infrastructure.prices.source import Fetch

EARLIEST_DAY = date(2021, 10, 1)


@dataclass(frozen=True)
class Coverage:
    revision: UUID
    valid: int
    missing: int
    source_null: int
    retrieved_at: datetime


@dataclass(frozen=True)
class Backfill:
    id: UUID
    region: Region
    start: date
    end: date
    next: date
    status: str
    diagnostic: str | None


@dataclass(frozen=True)
class Attempt:
    id: UUID
    retrieved_at: datetime
    status: str
    revision: UUID | None
    response_hash: str | None
    source_version: str | None
    diagnostic: str | None


def _slots_json(slots: tuple[Slot, ...]) -> str:
    """The Jackson ``{"kind":...,"price":...}`` shape with plain decimals."""
    parts = []
    for slot in slots:
        price = (
            "null" if slot.price is None else decimal_text.to_plain_string(slot.price)
        )
        parts.append(f'{{"kind":"{slot.kind.name}","price":{price}}}')
    return "[" + ",".join(parts) + "]"


def _read_slots(text: str) -> tuple[Slot, ...]:
    raw = json.loads(text, parse_float=Decimal, parse_int=Decimal)
    return tuple(
        Slot(
            Kind[entry["kind"]],
            None if entry["price"] is None else Decimal(str(entry["price"])),
        )
        for entry in raw
    )


def _instant(value: datetime) -> datetime:
    """pg timestamptz read → UTC instant, like ``Timestamp.toInstant()``."""
    return value.astimezone(UTC) if value.tzinfo else value


class PriceStore:
    def __init__(self, engine: sa.engine.Engine) -> None:
        self.engine = engine

    # -- revisions ----------------------------------------------------------

    def save(self, fetch: Fetch) -> UUID:
        with self.engine.begin() as conn:
            return self._save_inside(conn, fetch)

    def _save_inside(self, conn: sa.Connection, fetch: Fetch) -> UUID:
        batch = fetch.batch
        conn.execute(
            sa.text(
                "INSERT INTO price_revision"
                " (id,region,market_day,content_hash,slots,"
                "  valid_count,missing_count,null_count)"
                " VALUES (:id,:region,:day,:hash,"
                " CAST(:slots AS jsonb),:valid,:missing,:nulls)"
                " ON CONFLICT(region,market_day,content_hash) DO NOTHING"
            ),
            {
                "id": uuid.uuid4(),
                "region": batch.region.name,
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
                    "SELECT id FROM price_revision"
                    " WHERE region=:region AND market_day=:day"
                    " AND content_hash=:hash"
                ),
                {
                    "region": batch.region.name,
                    "day": batch.day,
                    "hash": batch.content_hash(),
                },
            ).scalar_one(),
        )
        conn.execute(
            sa.text(
                "INSERT INTO price_current"
                " (region,market_day,revision_id,retrieved_at)"
                " VALUES (:region,:day,:revision,:at)"
                " ON CONFLICT(region,market_day) DO UPDATE"
                " SET revision_id=EXCLUDED.revision_id,"
                "     retrieved_at=EXCLUDED.retrieved_at"
                " WHERE price_current.retrieved_at <= EXCLUDED.retrieved_at"
            ),
            {
                "region": batch.region.name,
                "day": batch.day,
                "revision": revision,
                "at": fetch.retrieved_at,
            },
        )
        conn.execute(
            sa.text(
                "INSERT INTO price_import_attempt"
                " (id,region,market_day,retrieved_at,status,revision_id,"
                "  response_hash,source_version)"
                " VALUES (:id,:region,:day,:at,:status,:revision,:resp,:version)"
            ),
            {
                "id": uuid.uuid4(),
                "region": batch.region.name,
                "day": batch.day,
                "at": fetch.retrieved_at,
                "status": "COMPLETE" if batch.complete() else "INCOMPLETE",
                "revision": revision,
                "resp": fetch.response_hash,
                "version": fetch.source_version,
            },
        )
        return revision

    # -- reads ----------------------------------------------------------------

    def coverage(self, region: Region, day: date) -> Coverage | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.text(
                    "SELECT r.id, r.valid_count, r.missing_count, r.null_count,"
                    " c.retrieved_at FROM price_current c"
                    " JOIN price_revision r ON r.id = c.revision_id"
                    " WHERE c.region = :region AND c.market_day = :day"
                ),
                {"region": region.name, "day": day},
            ).first()
        if row is None:
            return None
        return Coverage(
            row.id,
            row.valid_count,
            row.missing_count,
            row.null_count,
            _instant(row.retrieved_at),
        )

    def coverage_range(
        self, region: Region, start: date, end: date
    ) -> dict[date, Coverage]:
        if not start < end or start + timedelta(days=31) < end:
            raise ValueError("Coverage range must contain 1-31 days")
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT c.market_day, r.id, r.valid_count, r.missing_count,"
                    " r.null_count, c.retrieved_at FROM price_current c"
                    " JOIN price_revision r ON r.id = c.revision_id"
                    " WHERE c.region = :region AND c.market_day >= :start"
                    " AND c.market_day < :end ORDER BY c.market_day"
                ),
                {"region": region.name, "start": start, "end": end},
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
                    "SELECT * FROM price_import_attempt"
                    " WHERE region = :region AND market_day = :day"
                    " ORDER BY retrieved_at, id"
                ),
                {"region": region.name, "day": day},
            ).all()
        return [
            Attempt(
                row.id,
                _instant(row.retrieved_at),
                row.status,
                row.revision_id,
                row.response_hash,
                row.source_version,
                row.diagnostic,
            )
            for row in rows
        ]

    def revision(self, id: UUID) -> PriceBatch:
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.text(
                    "SELECT region, market_day, slots::text AS slots"
                    " FROM price_revision WHERE id = :id"
                ),
                {"id": id},
            ).one()
        return PriceBatch(Region[row.region], row.market_day, _read_slots(row.slots))

    # -- snapshots ------------------------------------------------------------

    def snapshot(self, revision: UUID) -> UUID:
        id = uuid.uuid4()
        with self.engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO price_snapshot(id, revision_id) VALUES (:id, :rev)"
                ),
                {"id": id, "rev": revision},
            )
        return id

    def snapshot_prices(self, snapshot: UUID) -> PriceDay:
        with self.engine.connect() as conn:
            revision = cast(
                UUID,
                conn.execute(
                    sa.text("SELECT revision_id FROM price_snapshot WHERE id = :id"),
                    {"id": snapshot},
                ).scalar_one(),
            )
        return self.revision(revision).to_price_day()

    # -- backfills -------------------------------------------------------------

    def create_backfill(
        self,
        region: Region,
        start: date,
        end: date,
        clock: Callable[[], datetime] | None = None,
    ) -> UUID:
        with self.engine.begin() as conn:
            return self._create_backfill(conn, region, start, end, clock)

    def _create_backfill(
        self,
        conn: sa.Connection,
        region: Region,
        start: date,
        end: date,
        clock: Callable[[], datetime] | None = None,
    ) -> UUID:
        now = (clock or _utc_now)().astimezone(NEM_OFFSET).date()
        if (
            start < EARLIEST_DAY
            or not start < end
            or start + timedelta(days=31) < end
            or end > now
        ):
            raise ValueError("require 1..31 completed post-settlement days")
        id = uuid.uuid4()
        conn.execute(
            sa.text(
                "INSERT INTO price_backfill"
                " (id,region,start_day,end_exclusive,next_day,status)"
                " VALUES (:id,:region,:start,:end,:next,'ACTIVE')"
            ),
            {
                "id": id,
                "region": region.name,
                "start": start,
                "end": end,
                "next": start,
            },
        )
        return id

    def backfill(self, id: UUID) -> Backfill:
        with self.engine.connect() as conn:
            return self._backfill(conn, id)

    def _backfill(self, conn: sa.Connection, id: UUID) -> Backfill:
        row = conn.execute(
            sa.text("SELECT * FROM price_backfill WHERE id = :id"), {"id": id}
        ).one()
        return Backfill(
            id,
            Region[row.region],
            row.start_day,
            row.end_exclusive,
            row.next_day,
            row.status,
            row.diagnostic,
        )

    def commit_day(self, id: UUID, expected: date, fetch: Fetch) -> bool:
        """Optimistic checkpoint fence: concurrent/stale work rolls back its
        entire write."""
        with self.engine.begin() as conn:
            return self._commit_day(conn, id, expected, fetch)

    def _commit_day(
        self, conn: sa.Connection, id: UUID, expected: date, fetch: Fetch
    ) -> bool:
        row = conn.execute(
            sa.text("SELECT * FROM price_backfill WHERE id = :id"),
            {"id": id},
        ).one()
        batch = fetch.batch
        if (
            row.next_day != expected
            or batch.day != expected
            or row.region != batch.region.name
            or not expected < row.end_exclusive
        ):
            raise ValueError("stale or mismatched backfill day")
        self._save_inside(conn, fetch)
        complete = batch.complete()
        next_day = expected + timedelta(days=1) if complete else expected
        status = (
            ("COMPLETE" if next_day == row.end_exclusive else "ACTIVE")
            if complete
            else "PAUSED"
        )
        changed = conn.execute(
            sa.text(
                "UPDATE price_backfill SET next_day=:next, status=:status,"
                " diagnostic=:diag WHERE id=:id AND next_day=:expected"
            ),
            {
                "next": next_day,
                "status": status,
                "diag": None
                if complete
                else "Incomplete price day; refresh before advancing",
                "id": id,
                "expected": expected,
            },
        ).rowcount
        if changed != 1:
            raise ValueError("backfill checkpoint changed concurrently")
        return complete

    def record_failure(self, task: Backfill, at: datetime, category: str) -> None:
        with self.engine.begin() as conn:
            self._record_failure(conn, task, at, category)

    def _record_failure(
        self, conn: sa.Connection, task: Backfill, at: datetime, category: str
    ) -> None:
        conn.execute(
            sa.text(
                "INSERT INTO price_import_attempt"
                " (id,region,market_day,retrieved_at,status,diagnostic)"
                " VALUES (:id,:region,:day,:at,'FAILED',:diag)"
            ),
            {
                "id": uuid.uuid4(),
                "region": task.region.name,
                "day": task.next,
                "at": at,
                "diag": category,
            },
        )
        conn.execute(
            sa.text(
                "UPDATE price_backfill SET status='PAUSED', diagnostic=:diag"
                " WHERE id=:id AND next_day=:next AND status<>'COMPLETE'"
            ),
            {"diag": category, "id": task.id, "next": task.next},
        )


def _utc_now() -> datetime:
    return datetime.now(UTC)
