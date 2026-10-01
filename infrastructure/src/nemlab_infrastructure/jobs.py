"""``RefreshJobService`` — fenced refresh queue on SQLAlchemy Core.

Ports the Java service exactly: every public method is one short transaction
(serialised by the ``pg_advisory_xact_lock`` queue lock), claim tokens fence
stale writers, leases recover expired claims, and price writes share the job
transaction so partial outcomes roll back together. No network work inside
transactions — fetch OE data after ``claim()`` returns, then pass the result
to ``complete()``.
"""

import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import text

from nemlab_core.prices import Region
from nemlab_infrastructure.prices.source import Fetch
from nemlab_infrastructure.prices.store import PriceStore

MAX_PENDING_JOBS = 100
MAX_ATTEMPTS = 3
LEASE_SECONDS = 300
# Anonymous fetches stay a minority of the shared queue and retry a bounded
# number of times per day.
MAX_VISITOR_PENDING = 10
MAX_VISITOR_ATTEMPTS = 3
VISITOR_KEY_PREFIX = "visitor-price-v1:"

# Serialises short queue transitions across processes, not network requests.
QUEUE_LOCK = 735_028

_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]*")
_DIAGNOSTIC = re.compile(r"[A-Z][A-Z0-9_]*")


class RequestKeyConflict(ValueError):
    def __init__(self) -> None:
        super().__init__("Request key already belongs to another price day")


class QueueFull(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Refresh queue is full; wait for existing jobs")


class VisitorLimited(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Too many visitor-triggered fetches are pending")


class RefreshAttemptsExhausted(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Visitor-triggered fetches for this day have been exhausted")


class StaleClaimException(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "Refresh claim expired, was cancelled, or belongs to another worker"
        )


class Status(Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class RefreshJob:
    id: UUID
    backfill_id: UUID
    region: Region
    day: date
    status: Status
    attempts: int
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


def _job(row: sa.engine.Row[Any]) -> RefreshJob:
    return RefreshJob(
        row.id,
        row.backfill_id,
        Region[row.region],
        row.market_day,
        Status[row.status],
        row.attempts,
        row.claim_token,
        row.lease_until,
        row.available_at,
        row.diagnostic,
    )


def _validate_label(value: str, maximum: int) -> None:
    if not value or len(value) > maximum or not _LABEL.fullmatch(value):
        raise ValueError("Invalid operational identifier")


def _validate_limit(limit: int) -> None:
    if limit < 1 or limit > 100:
        raise ValueError("Limit must be between 1 and 100")


class RefreshJobService:
    def __init__(self, engine: sa.engine.Engine, prices: PriceStore) -> None:
        self.engine = engine
        self.prices = prices

    # -- submissions ---------------------------------------------------------

    def submit(self, request_key: str, region: Region, day: date, actor: str) -> UUID:
        _validate_label(request_key, 120)
        _validate_label(actor, 80)
        if region is None or day is None:
            raise ValueError("Region and completed market day are required")
        with self.engine.begin() as conn:
            self._lock_queue(conn)
            return self._submit_inside(conn, request_key, region, day, actor)

    def submit_visitor(self, region: Region, day: date) -> UUID:
        """Enqueue a price fetch for an anonymous visitor submission. Keys are
        deterministic per region/day, so repeat polls deduplicate onto any
        active job regardless of origin. After a terminal outcome the next
        request starts a fresh job under a suffixed key, up to
        MAX_VISITOR_ATTEMPTS per day."""
        if region is None or day is None:
            raise ValueError("Region and completed market day are required")
        base = f"{VISITOR_KEY_PREFIX}{region.name}:{day}"
        with self.engine.begin() as conn:
            self._lock_queue(conn)
            used: int = conn.execute(
                text(
                    "SELECT count(*) FROM refresh_request"
                    " WHERE request_key LIKE :prefix"
                ),
                {"prefix": base + "%"},
            ).scalar_one()
            active = self._active_for(conn, region, day)
            if used == 0:
                if active is None:
                    self._check_visitor_pending(conn)
                return self._submit_inside(conn, base, region, day, "visitor")
            if active is not None:
                self._event(conn, active.id, "visitor", "DUPLICATE_REQUEST", None)
                return active.id
            if used >= MAX_VISITOR_ATTEMPTS:
                raise RefreshAttemptsExhausted()
            self._check_visitor_pending(conn)
            return self._submit_inside(
                conn, f"{base}:r{used + 1}", region, day, "visitor"
            )

    def _submit_inside(
        self,
        conn: sa.Connection,
        request_key: str,
        region: Region,
        day: date,
        actor: str,
    ) -> UUID:
        """``submit`` inline on an already queue-locked transaction."""
        existing = conn.execute(
            text(
                "SELECT job.* FROM refresh_job job"
                " JOIN refresh_request request ON request.job_id = job.id"
                " WHERE request.request_key = :key"
            ),
            {"key": request_key},
        ).first()
        if existing is not None:
            job = _job(existing)
            if job.region is not region or job.day != day:
                raise RequestKeyConflict()
            self._event(conn, job.id, actor, "DUPLICATE_REQUEST", None)
            return job.id
        active = self._active_for(conn, region, day)
        if active is not None:
            job_id = active.id
        else:
            pending: int = conn.execute(
                text(
                    "SELECT count(*) FROM refresh_job"
                    " WHERE status IN ('QUEUED', 'RUNNING')"
                )
            ).scalar_one()
            if pending >= MAX_PENDING_JOBS:
                raise QueueFull()
            backfill_id = self.prices._create_backfill(
                conn, region, day, day + _ONE_DAY
            )
            job_id = uuid.uuid4()
            conn.execute(
                text(
                    "INSERT INTO refresh_job"
                    " (id, backfill_id, region, market_day, status)"
                    " VALUES (:id, :backfill, :region, :day, 'QUEUED')"
                ),
                {
                    "id": job_id,
                    "backfill": backfill_id,
                    "region": region.name,
                    "day": day,
                },
            )
        conn.execute(
            text(
                "INSERT INTO refresh_request(request_key, job_id) VALUES (:key, :job)"
            ),
            {"key": request_key, "job": job_id},
        )
        self._event(
            conn,
            job_id,
            actor,
            "DEDUPLICATED" if active is not None else "SUBMITTED",
            None,
        )
        return job_id

    def _active_for(
        self, conn: sa.Connection, region: Region, day: date
    ) -> RefreshJob | None:
        row = conn.execute(
            text(
                "SELECT * FROM refresh_job"
                " WHERE region = :region AND market_day = :day"
                " AND status IN ('QUEUED', 'RUNNING')"
            ),
            {"region": region.name, "day": day},
        ).first()
        return _job(row) if row is not None else None

    def _check_visitor_pending(self, conn: sa.Connection) -> None:
        pending: int = conn.execute(
            text(
                "SELECT count(DISTINCT job.id) FROM refresh_job job"
                " JOIN refresh_request request ON request.job_id = job.id"
                " WHERE job.status IN ('QUEUED', 'RUNNING')"
                " AND request.request_key LIKE :prefix"
            ),
            {"prefix": VISITOR_KEY_PREFIX + "%"},
        ).scalar_one()
        if pending >= MAX_VISITOR_PENDING:
            raise VisitorLimited()

    # -- worker lifecycle ------------------------------------------------------

    def claim(self) -> RefreshJob | None:
        """Initially permits one running ingestion globally, including
        multiple worker processes."""
        with self.engine.begin() as conn:
            self._lock_queue(conn)
            expired = conn.execute(
                text(
                    "SELECT * FROM refresh_job"
                    " WHERE status = 'RUNNING' AND lease_until <= clock_timestamp()"
                    " FOR UPDATE"
                )
            ).all()
            for job in (_job(row) for row in expired):
                self._retry_or_fail(conn, job, "LEASE_EXPIRED", True)
            running: int = conn.execute(
                text("SELECT count(*) FROM refresh_job WHERE status = 'RUNNING'")
            ).scalar_one()
            if running > 0:
                return None
            ready = conn.execute(
                text(
                    "SELECT * FROM refresh_job"
                    " WHERE status = 'QUEUED' AND available_at <= clock_timestamp()"
                    " ORDER BY available_at, created_at, id"
                    " LIMIT 1 FOR UPDATE SKIP LOCKED"
                )
            ).first()
            if ready is None:
                return None
            job_id = ready.id
            conn.execute(
                text(
                    "UPDATE refresh_job"
                    " SET status = 'RUNNING', attempts = attempts + 1,"
                    " claim_token = :token,"
                    " lease_until = clock_timestamp() + make_interval(secs => :secs)"
                    " WHERE id = :id"
                ),
                {"token": uuid.uuid4(), "secs": LEASE_SECONDS, "id": job_id},
            )
            self._event(conn, job_id, "worker", "CLAIMED", None)
            return self._find(conn, job_id)

    def complete(self, id: UUID, token: UUID, fetch: Fetch) -> None:
        with self.engine.begin() as conn:
            job = self._require_live_claim(conn, id, token)
            complete = self.prices._commit_day(conn, job.backfill_id, job.day, fetch)
            if complete:
                self._finish(conn, job, "SUCCEEDED", None)
                self._event(conn, id, "worker", "SUCCEEDED", None)
            else:
                self._require_live_claim(conn, id, token)
                self._retry_or_fail(conn, job, "INCOMPLETE_PRICE_DAY", False)

    def fail(self, id: UUID, token: UUID, diagnostic_code: str) -> None:
        self._record_failure(id, token, diagnostic_code, retryable=True)

    def fail_permanently(self, id: UUID, token: UUID, diagnostic_code: str) -> None:
        self._record_failure(id, token, diagnostic_code, retryable=False)

    def _record_failure(
        self, id: UUID, token: UUID, diagnostic_code: str, retryable: bool
    ) -> None:
        _validate_label(diagnostic_code, 80)
        if not _DIAGNOSTIC.fullmatch(diagnostic_code):
            raise ValueError(
                "Use a diagnostic code, never an exception message or response body"
            )
        with self.engine.begin() as conn:
            job = self._require_live_claim(conn, id, token)
            at: datetime = conn.execute(text("SELECT clock_timestamp()")).scalar_one()
            self.prices._record_failure(
                conn,
                self.prices._backfill(conn, job.backfill_id),
                at,
                diagnostic_code,
            )
            self._require_live_claim(conn, id, token)
            if retryable:
                self._retry_or_fail(conn, job, diagnostic_code, False)
            else:
                self._finish(conn, job, "FAILED", diagnostic_code)
                self._event(conn, id, "worker", "FAILED", diagnostic_code)

    def cancel(self, id: UUID, actor: str) -> bool:
        _validate_label(actor, 80)
        with self.engine.begin() as conn:
            # Matching claim() lock order prevents cancellation/recovery
            # deadlocks.
            self._lock_queue(conn)
            changed = conn.execute(
                text(
                    "UPDATE refresh_job"
                    " SET status = 'CANCELLED', claim_token = NULL,"
                    " lease_until = NULL, diagnostic = 'CANCELLED_BY_OPERATOR'"
                    " WHERE id = :id AND status IN ('QUEUED', 'RUNNING')"
                ),
                {"id": id},
            ).rowcount
            if changed == 1:
                self._event(conn, id, actor, "CANCELLED", None)
            elif self._find(conn, id) is not None:
                self._event(conn, id, actor, "CANCEL_NOOP", None)
            return changed == 1

    # -- reads -------------------------------------------------------------------

    def find(self, id: UUID) -> RefreshJob | None:
        with self.engine.connect() as conn:
            return self._find(conn, id)

    def _find(self, conn: sa.Connection, id: UUID) -> RefreshJob | None:
        row = conn.execute(
            text("SELECT * FROM refresh_job WHERE id = :id"), {"id": id}
        ).first()
        return _job(row) if row is not None else None

    def recent(self, limit: int) -> list[RefreshJob]:
        _validate_limit(limit)
        with self.engine.connect() as conn:
            return [
                _job(row)
                for row in conn.execute(
                    text(
                        "SELECT * FROM refresh_job"
                        " ORDER BY created_at DESC, id DESC LIMIT :limit"
                    ),
                    {"limit": limit},
                ).all()
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
                        " FROM refresh_job_event"
                        " WHERE job_id = :id AND id > :after ORDER BY id LIMIT :limit"
                    ),
                    {"id": id, "after": after, "limit": limit},
                ).all()
            ]

    # -- internals ---------------------------------------------------------------

    def _require_live_claim(
        self, conn: sa.Connection, id: UUID, token: UUID | None
    ) -> RefreshJob:
        if token is None:
            raise StaleClaimException()
        row = conn.execute(
            text(
                "SELECT * FROM refresh_job"
                " WHERE id = :id AND status = 'RUNNING' AND claim_token = :token"
                " AND lease_until > clock_timestamp()"
                " FOR UPDATE"
            ),
            {"id": id, "token": token},
        ).first()
        if row is None:
            raise StaleClaimException()
        return _job(row)

    def _retry_or_fail(
        self,
        conn: sa.Connection,
        job: RefreshJob,
        diagnostic: str,
        recovering_expired_claim: bool,
    ) -> None:
        status = "FAILED" if job.attempts >= MAX_ATTEMPTS else "QUEUED"
        # Recovery may operate on an expired lease. Other callers already hold
        # a live row lock.
        changed = conn.execute(
            text(
                "UPDATE refresh_job"
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
        self, conn: sa.Connection, job: RefreshJob, status: str, diagnostic: str | None
    ) -> None:
        changed = conn.execute(
            text(
                "UPDATE refresh_job"
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
        # The transaction owns the advisory lock until commit or rollback.
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
                "INSERT INTO refresh_job_event(job_id, actor, action, diagnostic)"
                " VALUES (:job, :actor, :action, :diag)"
            ),
            {"job": id, "actor": actor, "action": action, "diag": diagnostic},
        )


_ONE_DAY = timedelta(days=1)
