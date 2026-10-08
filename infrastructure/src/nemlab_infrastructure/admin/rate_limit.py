"""Persisted fixed-window rate limits over ``admin_rate_limit``.

Counters live in the database so every API/worker process shares them —
an in-memory limiter would reset per process and per restart. Windows are
fixed (``floor(now / window) * window``), the upsert is atomic under
concurrency, and expired windows are pruned by ``prune`` from the worker's
housekeeping cycle rather than a scheduler of their own.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa


def _utc_now() -> datetime:
    return datetime.now(UTC)


class RateLimiter:
    def __init__(
        self, engine: sa.engine.Engine, *, now: Callable[[], datetime] = _utc_now
    ) -> None:
        self.engine = engine
        self._now = now

    def hit(self, bucket: str, subject: str, limit: int, window_seconds: int) -> bool:
        """Record one attempt; ``True`` while the window count stays within
        ``limit``. Over-limit attempts are still counted."""
        now = self._now()
        start = now - timedelta(seconds=now.timestamp() % window_seconds)
        with self.engine.begin() as conn:
            count: int = conn.execute(
                sa.text(
                    "INSERT INTO admin_rate_limit"
                    " (bucket, subject, window_start, count)"
                    " VALUES (:bucket, :subject, :start, 1)"
                    " ON CONFLICT (bucket, subject, window_start)"
                    " DO UPDATE SET count = admin_rate_limit.count + 1"
                    " RETURNING count"
                ),
                {"bucket": bucket, "subject": subject, "start": start},
            ).scalar_one()
        return count <= limit

    def prune(self, older_than: timedelta = timedelta(days=2)) -> int:
        with self.engine.begin() as conn:
            return conn.execute(
                sa.text("DELETE FROM admin_rate_limit WHERE window_start < :cutoff"),
                {"cutoff": self._now() - older_than},
            ).rowcount
