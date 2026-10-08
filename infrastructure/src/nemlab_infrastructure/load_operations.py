"""Resumable bounded load operations (NEM-102).

A lightweight record linking one owner-declared region/range to the
<=31-day chunk submissions it fans out across the existing grid-import
and price-refresh queues — grid phase first, then prices. No second
scheduler: children reference the durable job rows those queues own.

Crash/reload safety comes from deterministic request keys
(``load:{operation}:{phase}:{start}``) plus the queues' own idempotency:
a submission lost between enqueue and link recording resubmits the same
key and binds to the same jobs — never duplicates. Pause stops new
dispatch only; already queued children keep running independently.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

import sqlalchemy as sa

from nemlab_core.prices import NEM_OFFSET, Region
from nemlab_infrastructure.grid.imports import GridImportJobs
from nemlab_infrastructure.grid.imports import QueueFull as GridQueueFull
from nemlab_infrastructure.jobs import QueueFull as PriceQueueFull
from nemlab_infrastructure.jobs import RefreshJobService
from nemlab_infrastructure.prices.store import EARLIEST_DAY

CHUNK_DAYS = 31
MAX_OPERATION_DAYS = 366


class LoadNotFound(RuntimeError):
    pass


class LoadConflict(RuntimeError):
    """Paused, already dispatched or concurrently moved operation."""


@dataclass(frozen=True)
class LoadOperation:
    id: UUID
    region: Region
    start: date
    end: date
    actor: str
    status: Literal["dispatching", "paused", "dispatched"]
    phase: Literal["grid", "price"]
    next_day: date
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class LoadChild:
    phase: str
    request_key: str
    start: date
    end: date
    job_ids: tuple[UUID, ...]
    created_at: datetime


@dataclass(frozen=True)
class DispatchOutcome:
    """`submitted` links a new chunk; `backpressured` hit a queue cap and
    nothing moved; `dispatched` means every chunk is already submitted
    (children may still be running in the queues)."""

    kind: Literal["submitted", "backpressured", "dispatched"]
    child: LoadChild | None


def _operation(row: sa.Row[Any]) -> LoadOperation:
    return LoadOperation(
        row.id,
        Region[row.region],
        row.start_day,
        row.end_exclusive,
        row.actor,
        row.status,
        row.phase,
        row.next_day,
        row.created_at,
        row.updated_at,
    )


def _child(row: sa.Row[Any]) -> LoadChild:
    return LoadChild(
        row.phase,
        row.request_key,
        row.start_day,
        row.end_exclusive,
        tuple(row.job_ids),
        row.created_at,
    )


class LoadOperations:
    def __init__(
        self,
        engine: sa.engine.Engine,
        grid_jobs: GridImportJobs,
        price_jobs: RefreshJobService,
    ) -> None:
        self.engine = engine
        self.grid_jobs = grid_jobs
        self.price_jobs = price_jobs

    def begin(
        self, region: Region, start: date, end: date, actor: str
    ) -> LoadOperation:
        today = datetime.now(UTC).astimezone(NEM_OFFSET).date()
        if (
            not start < end
            or start + timedelta(days=MAX_OPERATION_DAYS) < end
            or start < EARLIEST_DAY
            or end > today
        ):
            raise ValueError("Require a 1-366 day range of completed NEM market days")
        op_id = uuid.uuid4()
        with self.engine.begin() as conn:
            row = conn.execute(
                sa.text(
                    "INSERT INTO load_operation"
                    " (id, region, start_day, end_exclusive, actor, status,"
                    "  phase, next_day)"
                    " VALUES (:id, :region, :start, :end, :actor,"
                    "  'dispatching', 'grid', :start)"
                    " RETURNING *"
                ),
                {
                    "id": op_id,
                    "region": region.name,
                    "start": start,
                    "end": end,
                    "actor": actor,
                },
            ).one()
        return _operation(row)

    def get(self, op_id: UUID) -> LoadOperation | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.text("SELECT * FROM load_operation WHERE id = :id"),
                {"id": op_id},
            ).first()
        return _operation(row) if row is not None else None

    def _require(self, op_id: UUID) -> LoadOperation:
        op = self.get(op_id)
        if op is None:
            raise LoadNotFound
        return op

    def recent(self, limit: int = 50) -> list[LoadOperation]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT * FROM load_operation"
                    " ORDER BY created_at DESC, id LIMIT :limit"
                ),
                {"limit": min(limit, 200)},
            ).all()
        return [_operation(row) for row in rows]

    def children(self, op_id: UUID) -> list[LoadChild]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT * FROM load_operation_child"
                    " WHERE operation_id = :id"
                    " ORDER BY phase, start_day, request_key"
                ),
                {"id": op_id},
            ).all()
        return [_child(row) for row in rows]

    def job_states(self, op_id: UUID) -> dict[UUID, dict[str, object]]:
        """Current queue state for every linked job, keyed by job id —
        joined from the owning queue tables, never duplicated state."""
        states: dict[UUID, dict[str, object]] = {}
        with self.engine.connect() as conn:
            for child in self.children(op_id):
                if child.phase == "grid":
                    rows = conn.execute(
                        sa.text(
                            "SELECT id, status, attempts, diagnostic, next_day"
                            " FROM grid_import_job WHERE id = ANY(:ids)"
                        ),
                        {"ids": list(child.job_ids)},
                    ).all()
                else:
                    rows = conn.execute(
                        sa.text(
                            "SELECT id, status, attempts, diagnostic"
                            " FROM refresh_job WHERE id = ANY(:ids)"
                        ),
                        {"ids": list(child.job_ids)},
                    ).all()
                for row in rows:
                    states[row.id] = {
                        "status": row.status,
                        "attempts": row.attempts,
                        "diagnostic": row.diagnostic,
                        **(
                            {"nextDay": str(row.next_day)}
                            if child.phase == "grid"
                            else {}
                        ),
                    }
        return states

    def dispatch(self, op_id: UUID, actor: str) -> DispatchOutcome:
        """Submit the next <=31-day chunk of the current phase. Deterministic
        request keys make a lost submission idempotent, and the post-submit
        cursor check serialises concurrent dispatchers."""
        op = self._require(op_id)
        if op.status == "dispatched":
            return DispatchOutcome("dispatched", None)
        if op.status == "paused":
            raise LoadConflict("Operation is paused — resume to dispatch")
        chunk_start = op.next_day
        chunk_end = min(chunk_start + timedelta(days=CHUNK_DAYS), op.end)
        key = f"load:{op_id}:{op.phase}:{chunk_start.isoformat()}"
        try:
            job_ids = self._submit(op, key, chunk_start, chunk_end, actor)
        except (GridQueueFull, PriceQueueFull):
            return DispatchOutcome("backpressured", None)
        with self.engine.begin() as conn:
            row = conn.execute(
                sa.text("SELECT * FROM load_operation WHERE id = :id FOR UPDATE"),
                {"id": op_id},
            ).one()
            current = _operation(row)
            if (
                current.status != "dispatching"
                or current.phase != op.phase
                or current.next_day != chunk_start
            ):
                raise LoadConflict("Operation moved during dispatch")
            conn.execute(
                sa.text(
                    "INSERT INTO load_operation_child"
                    " (operation_id, phase, request_key, start_day,"
                    "  end_exclusive, job_ids)"
                    " VALUES (:op, :phase, :key, :start, :end, :jobs)"
                    " ON CONFLICT (operation_id, request_key) DO UPDATE"
                    " SET job_ids = EXCLUDED.job_ids"
                ),
                {
                    "op": op_id,
                    "phase": op.phase,
                    "key": key,
                    "start": chunk_start,
                    "end": chunk_end,
                    "jobs": list(job_ids),
                },
            )
            if chunk_end < op.end:
                conn.execute(
                    sa.text(
                        "UPDATE load_operation SET next_day = :next,"
                        " updated_at = clock_timestamp() WHERE id = :id"
                    ),
                    {"next": chunk_end, "id": op_id},
                )
            elif op.phase == "grid":
                conn.execute(
                    sa.text(
                        "UPDATE load_operation SET phase = 'price',"
                        " next_day = start_day,"
                        " updated_at = clock_timestamp() WHERE id = :id"
                    ),
                    {"id": op_id},
                )
            else:
                conn.execute(
                    sa.text(
                        "UPDATE load_operation SET status = 'dispatched',"
                        " updated_at = clock_timestamp() WHERE id = :id"
                    ),
                    {"id": op_id},
                )
        return DispatchOutcome(
            "submitted",
            LoadChild(
                op.phase,
                key,
                chunk_start,
                chunk_end,
                tuple(job_ids),
                datetime.now(UTC),
            ),
        )

    def _submit(
        self,
        op: LoadOperation,
        key: str,
        start: date,
        end: date,
        actor: str,
    ) -> list[UUID]:
        if op.phase == "grid":
            return [self.grid_jobs.submit(key, op.region, start, end, actor)]
        return self.price_jobs.submit_window(key, op.region, start, end, actor)

    def pause(self, op_id: UUID) -> LoadOperation:
        """Stop submitting new chunks. Queued children keep running; cancel
        those through the job routes — pause is dispatch only."""
        with self.engine.begin() as conn:
            updated = conn.execute(
                sa.text(
                    "UPDATE load_operation SET status = 'paused',"
                    " updated_at = clock_timestamp()"
                    " WHERE id = :id AND status = 'dispatching'"
                ),
                {"id": op_id},
            ).rowcount
        if updated == 0:
            if self.get(op_id) is None:
                raise LoadNotFound
            raise LoadConflict("Only a dispatching operation can pause")
        return self._require(op_id)

    def resume(self, op_id: UUID) -> LoadOperation:
        """Re-enable dispatch after a pause or interruption. Reconciliation
        needs no extra pass: the next dispatch recomputes the deterministic
        request key and binds to the same queue jobs."""
        with self.engine.begin() as conn:
            updated = conn.execute(
                sa.text(
                    "UPDATE load_operation SET status = 'dispatching',"
                    " updated_at = clock_timestamp()"
                    " WHERE id = :id AND status = 'paused'"
                ),
                {"id": op_id},
            ).rowcount
        if updated == 0:
            if self.get(op_id) is None:
                raise LoadNotFound
            raise LoadConflict("Only a paused operation can resume")
        return self._require(op_id)
