"""``GridImportJobs`` — bounded operator imports with lease fencing.

Same queue discipline as ``RefreshJobService``: short serialised
transactions on the advisory queue lock, claim tokens fence stale writers,
expired leases recover. One job imports a 1-31 day window day-by-day; each
``complete_day`` commits the day's revisions, advances ``next_day`` and
renews the lease, so a restart resumes exactly where it stopped and
re-saved days deduplicate by content hash. Core (market) fetch failures
retry the job; optional (power) failures are counted and recorded as FAILED
attempts without blocking the window.
"""

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import text

from nemlab_core.prices import NEM_OFFSET, Region
from nemlab_infrastructure.grid.source import GridFetch
from nemlab_infrastructure.grid.store import GridStore

MAX_PENDING_JOBS = 20
MAX_ATTEMPTS = 3
LEASE_SECONDS = 300
MAX_WINDOW_DAYS = 31
# Serialises grid-import queue transitions; distinct from the price lock.
QUEUE_LOCK = 735_056

_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]*")
_DIAGNOSTIC = re.compile(r"[A-Z][A-Z0-9_]*")


class QueueFull(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Grid import queue is full; wait for existing jobs")


class RequestKeyConflict(ValueError):
    def __init__(self) -> None:
        super().__init__("Request key already belongs to another import")


class StaleClaimException(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "Import claim expired, was cancelled, or belongs to another worker"
        )


class Status(Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class GridImportJob:
    id: UUID
    region: Region
    start: date
    end: date
    next_day: date
    status: Status
    attempts: int
    optional_failures: int
    claim_token: UUID | None
    lease_until: datetime | None
    available_at: datetime
    diagnostic: str | None


@dataclass(frozen=True)
class JobEvent:
    id: int
    occurred_at: datetime
    actor: str
    action: str
    diagnostic: str | None


@dataclass(frozen=True)
class DayOutcome:
    """One committed market day: a market (core) fetch is mandatory; the
    power fetch is either a ``GridFetch`` or a diagnostic failure code."""

    day: date
    market: GridFetch
    power: GridFetch | None = None
    power_failure: str | None = None

    def __post_init__(self) -> None:
        if (self.power is None) == (self.power_failure is None):
            raise ValueError("Exactly one of power fetch or failure is required")
        for fetch in (self.market, self.power):
            if fetch is not None and fetch.series[0].day != self.day:
                raise ValueError("fetch day does not match the outcome day")


def _job(row: sa.engine.Row[Any]) -> GridImportJob:
    return GridImportJob(
        row.id,
        Region[row.region],
        row.start_day,
        row.end_exclusive,
        row.next_day,
        Status[row.status],
        row.attempts,
        row.optional_failures,
        row.claim_token,
        row.lease_until,
        row.available_at,
        row.diagnostic,
    )


def _validate_label(value: str, maximum: int) -> None:
    if not value or len(value) > maximum or not _LABEL.fullmatch(value):
        raise ValueError("Invalid operational identifier")


def _validate_diagnostic(code: str) -> None:
    _validate_label(code, 80)
    if not _DIAGNOSTIC.fullmatch(code):
        raise ValueError(
            "Use a diagnostic code, never an exception message or response body"
        )


def _validate_limit(limit: int) -> None:
    if limit < 1 or limit > 100:
        raise ValueError("Limit must be between 1 and 100")


class GridImportJobs:
    def __init__(self, engine: sa.engine.Engine, grid: GridStore) -> None:
        self.engine = engine
        self.grid = grid

    # -- submissions -----------------------------------------------------------

    def submit(
        self,
        request_key: str,
        region: Region,
        start: date,
        end: date,
        actor: str,
        clock: Any = None,
    ) -> UUID:
        """Bounded operator submission: deduplicates by idempotency key and
        by an identical active window. ``end`` is exclusive; the window must
        cover 1..31 completed market days."""
        _validate_label(request_key, 120)
        _validate_label(actor, 80)
        today = (clock or _utc_now)().astimezone(NEM_OFFSET).date()
        if (
            not start < end
            or start + timedelta(days=MAX_WINDOW_DAYS) < end
            or end > today
        ):
            raise ValueError("require a 1..31 day window of completed market days")
        with self.engine.begin() as conn:
            self._lock_queue(conn)
            existing = conn.execute(
                text(
                    "SELECT job.* FROM grid_import_job job"
                    " JOIN grid_import_request request ON request.job_id = job.id"
                    " WHERE request.request_key = :key"
                ),
                {"key": request_key},
            ).first()
            if existing is not None:
                job = _job(existing)
                if job.region is not region or job.start != start or job.end != end:
                    raise RequestKeyConflict()
                self._event(conn, job.id, actor, "DUPLICATE_REQUEST", None)
                return job.id
            active = self._active_window(conn, region, start, end)
            if active is not None:
                conn.execute(
                    text(
                        "INSERT INTO grid_import_request(request_key, job_id)"
                        " VALUES (:key, :job)"
                    ),
                    {"key": request_key, "job": active.id},
                )
                self._event(conn, active.id, actor, "DEDUPLICATED", None)
                return active.id
            pending: int = conn.execute(
                text(
                    "SELECT count(*) FROM grid_import_job"
                    " WHERE status IN ('QUEUED','RUNNING')"
                )
            ).scalar_one()
            if pending >= MAX_PENDING_JOBS:
                raise QueueFull()
            job_id = uuid.uuid4()
            conn.execute(
                text(
                    "INSERT INTO grid_import_job"
                    " (id,region,start_day,end_exclusive,next_day,status)"
                    " VALUES (:id,:region,:start,:end,:next,'QUEUED')"
                ),
                {
                    "id": job_id,
                    "region": region.name,
                    "start": start,
                    "end": end,
                    "next": start,
                },
            )
            conn.execute(
                text(
                    "INSERT INTO grid_import_request(request_key, job_id)"
                    " VALUES (:key, :job)"
                ),
                {"key": request_key, "job": job_id},
            )
            self._event(conn, job_id, actor, "SUBMITTED", None)
            return job_id

    def _active_window(
        self, conn: sa.Connection, region: Region, start: date, end: date
    ) -> GridImportJob | None:
        row = conn.execute(
            text(
                "SELECT * FROM grid_import_job"
                " WHERE region = :region AND start_day = :start"
                " AND end_exclusive = :end"
                " AND status IN ('QUEUED','RUNNING','PAUSED')"
            ),
            {"region": region.name, "start": start, "end": end},
        ).first()
        return _job(row) if row is not None else None

    # -- worker lifecycle --------------------------------------------------------

    def claim(self) -> GridImportJob | None:
        """One running import globally; expired leases recover to QUEUED."""
        with self.engine.begin() as conn:
            self._lock_queue(conn)
            expired = conn.execute(
                text(
                    "SELECT * FROM grid_import_job"
                    " WHERE status = 'RUNNING'"
                    " AND lease_until <= clock_timestamp() FOR UPDATE"
                )
            ).all()
            for job in (_job(row) for row in expired):
                self._retry_or_fail(conn, job, "LEASE_EXPIRED", True)
            running: int = conn.execute(
                text("SELECT count(*) FROM grid_import_job WHERE status='RUNNING'")
            ).scalar_one()
            if running > 0:
                return None
            ready = conn.execute(
                text(
                    "SELECT * FROM grid_import_job"
                    " WHERE status = 'QUEUED'"
                    " AND available_at <= clock_timestamp()"
                    " ORDER BY available_at, created_at, id"
                    " LIMIT 1 FOR UPDATE SKIP LOCKED"
                )
            ).first()
            if ready is None:
                return None
            conn.execute(
                text(
                    "UPDATE grid_import_job"
                    " SET status = 'RUNNING', attempts = attempts + 1,"
                    " claim_token = :token,"
                    " lease_until = clock_timestamp() + make_interval(secs => :secs)"
                    " WHERE id = :id"
                ),
                {"token": uuid.uuid4(), "secs": LEASE_SECONDS, "id": ready.id},
            )
            self._event(conn, ready.id, "worker", "CLAIMED", None)
            return self._find(conn, ready.id)

    def complete_day(self, id: UUID, token: UUID | None, outcome: DayOutcome) -> bool:
        """Commit one market day atomically: market revisions + attempt,
        optional power revisions or a FAILED power attempt, the ``next_day``
        checkpoint and a lease renewal. Returns ``True`` when the window is
        finished (job SUCCEEDED)."""
        with self.engine.begin() as conn:
            job = self._require_live_claim(conn, id, token)
            if outcome.day != job.next_day:
                raise ValueError("outcome day does not match the job checkpoint")
            self.grid._save_inside(conn, outcome.market)
            if outcome.power is not None:
                self.grid._save_inside(conn, outcome.power)
            else:
                assert outcome.power_failure is not None
                self.grid._record_failure_inside(
                    conn,
                    job.region,
                    outcome.day,
                    ("power",),
                    outcome.market.retrieved_at,
                    outcome.power_failure,
                )
            done = outcome.day + timedelta(days=1) == job.end
            status = "SUCCEEDED" if done else "RUNNING"
            changed = conn.execute(
                text(
                    "UPDATE grid_import_job"
                    " SET next_day = :next, status = :status,"
                    " lease_until = CASE WHEN :done THEN NULL"
                    "   ELSE clock_timestamp() + make_interval(secs => :secs) END,"
                    " claim_token = CASE WHEN :done THEN NULL ELSE claim_token END,"
                    " optional_failures = optional_failures + :opt,"
                    " diagnostic = :diag"
                    " WHERE id = :id AND claim_token = :token"
                    " AND lease_until > clock_timestamp()"
                ),
                {
                    "next": outcome.day + timedelta(days=1),
                    "status": status,
                    "done": done,
                    "secs": LEASE_SECONDS,
                    "opt": 1 if outcome.power_failure is not None else 0,
                    "diag": outcome.power_failure,
                    "id": id,
                    "token": token,
                },
            ).rowcount
            if changed != 1:
                raise StaleClaimException()
            self._event(
                conn,
                id,
                "worker",
                "DAY_COMMITTED" if not done else "SUCCEEDED",
                outcome.power_failure,
            )
            return done

    def fail(self, id: UUID, token: UUID, diagnostic_code: str) -> None:
        """Retryable core failure: checkpoint preserved, bounded retry."""
        _validate_diagnostic(diagnostic_code)
        with self.engine.begin() as conn:
            job = self._require_live_claim(conn, id, token)
            self._retry_or_fail(conn, job, diagnostic_code, False)

    def fail_permanently(self, id: UUID, token: UUID, diagnostic_code: str) -> None:
        _validate_diagnostic(diagnostic_code)
        with self.engine.begin() as conn:
            job = self._require_live_claim(conn, id, token)
            self._finish(conn, job, "FAILED", diagnostic_code)
            self._event(conn, id, "worker", "FAILED", diagnostic_code)

    def cancel(self, id: UUID, actor: str) -> bool:
        _validate_label(actor, 80)
        with self.engine.begin() as conn:
            self._lock_queue(conn)
            changed = conn.execute(
                text(
                    "UPDATE grid_import_job"
                    " SET status = 'CANCELLED', claim_token = NULL,"
                    " lease_until = NULL, diagnostic = 'CANCELLED_BY_OPERATOR'"
                    " WHERE id = :id AND status IN ('QUEUED','RUNNING','PAUSED')"
                ),
                {"id": id},
            ).rowcount
            if changed == 1:
                self._event(conn, id, actor, "CANCELLED", None)
            elif self._find(conn, id) is not None:
                self._event(conn, id, actor, "CANCEL_NOOP", None)
            return changed == 1

    # -- reads ----------------------------------------------------------------

    def find(self, id: UUID) -> GridImportJob | None:
        with self.engine.connect() as conn:
            return self._find(conn, id)

    def _find(self, conn: sa.Connection, id: UUID) -> GridImportJob | None:
        row = conn.execute(
            text("SELECT * FROM grid_import_job WHERE id = :id"), {"id": id}
        ).first()
        return _job(row) if row is not None else None

    def recent(self, limit: int) -> list[GridImportJob]:
        _validate_limit(limit)
        with self.engine.connect() as conn:
            return [
                _job(row)
                for row in conn.execute(
                    text(
                        "SELECT * FROM grid_import_job"
                        " ORDER BY created_at DESC, id DESC LIMIT :limit"
                    ),
                    {"limit": limit},
                )
            ]

    def events(self, id: UUID, after: int, limit: int) -> list[JobEvent]:
        _validate_limit(limit)
        if after < 0:
            raise ValueError("Event cursor must be nonnegative")
        with self.engine.connect() as conn:
            return [
                JobEvent(row.id, row.occurred_at, row.actor, row.action, row.diagnostic)
                for row in conn.execute(
                    text(
                        "SELECT id, occurred_at, actor, action, diagnostic"
                        " FROM grid_import_job_event"
                        " WHERE job_id = :id AND id > :after ORDER BY id"
                        " LIMIT :limit"
                    ),
                    {"id": id, "after": after, "limit": limit},
                ).all()
            ]

    # -- internals ---------------------------------------------------------------

    def _require_live_claim(
        self, conn: sa.Connection, id: UUID, token: UUID | None
    ) -> GridImportJob:
        if token is None:
            raise StaleClaimException()
        row = conn.execute(
            text(
                "SELECT * FROM grid_import_job"
                " WHERE id = :id AND status = 'RUNNING' AND claim_token = :token"
                " AND lease_until > clock_timestamp() FOR UPDATE"
            ),
            {"id": id, "token": token},
        ).first()
        if row is None:
            raise StaleClaimException()
        return _job(row)

    def _retry_or_fail(
        self,
        conn: sa.Connection,
        job: GridImportJob,
        diagnostic: str,
        recovering_expired_claim: bool,
    ) -> None:
        status = "FAILED" if job.attempts >= MAX_ATTEMPTS else "QUEUED"
        changed = conn.execute(
            text(
                "UPDATE grid_import_job"
                " SET status = :status, claim_token = NULL, lease_until = NULL,"
                " diagnostic = :diag,"
                " available_at = clock_timestamp() + make_interval(secs => :delay)"
                " WHERE id = :id AND claim_token = :token"
                " AND (:recovering OR lease_until > clock_timestamp())"
            ),
            {
                "status": status,
                "diag": diagnostic,
                "delay": 30 * job.attempts,
                "id": job.id,
                "token": job.claim_token,
                "recovering": recovering_expired_claim,
            },
        ).rowcount
        if changed != 1:
            raise StaleClaimException()
        self._event(
            conn,
            job.id,
            "worker",
            "FAILED" if status == "FAILED" else "RETRY_SCHEDULED",
            diagnostic,
        )

    def _finish(
        self,
        conn: sa.Connection,
        job: GridImportJob,
        status: str,
        diagnostic: str | None,
    ) -> None:
        changed = conn.execute(
            text(
                "UPDATE grid_import_job"
                " SET status = :status, diagnostic = :diag, claim_token = NULL,"
                " lease_until = NULL"
                " WHERE id = :id AND claim_token = :token"
                " AND lease_until > clock_timestamp()"
            ),
            {
                "status": status,
                "diag": diagnostic,
                "id": job.id,
                "token": job.claim_token,
            },
        ).rowcount
        if changed != 1:
            raise StaleClaimException()

    def _lock_queue(self, conn: sa.Connection) -> None:
        conn.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": QUEUE_LOCK})

    def _event(
        self,
        conn: sa.Connection,
        id: UUID,
        actor: str,
        action: str,
        diagnostic: str | None,
    ) -> None:
        conn.execute(
            text(
                "INSERT INTO grid_import_job_event"
                " (job_id, actor, action, diagnostic)"
                " VALUES (:job, :actor, :action, :diag)"
            ),
            {"job": id, "actor": actor, "action": action, "diag": diagnostic},
        )


def _utc_now() -> datetime:
    return datetime.now(UTC)
