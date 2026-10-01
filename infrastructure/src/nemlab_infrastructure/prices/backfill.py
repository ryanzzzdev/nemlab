"""``PriceBackfill`` — one-day synchronous steps.

Scheduling, authentication and distributed leases belong to the worker
layer. Ports the Java class exactly: a finished backfill is a no-op, a
fetch/storage failure records a safe diagnostic and pauses the task.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from nemlab_infrastructure.prices.source import Failure, PriceSource
from nemlab_infrastructure.prices.store import PriceStore


def _utc_now() -> datetime:
    return datetime.now(UTC)


class PriceBackfill:
    def __init__(
        self,
        store: PriceStore,
        source: PriceSource,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._store = store
        self._source = source
        self._clock = clock or _utc_now

    def step(self, id: UUID) -> bool:
        task = self._store.backfill(id)
        if task.status == "COMPLETE":
            return False
        try:
            return self._store.commit_day(
                id, task.next, self._source.fetch(task.region, task.next)
            )
        except KeyboardInterrupt:
            self._store.record_failure(task, self._clock(), "INTERRUPTED")
            return False
        except Failure as ex:
            self._store.record_failure(task, self._clock(), ex.code)
            return False
        except Exception as ex:
            self._store.record_failure(
                task, self._clock(), f"FETCH_OR_STORAGE_FAILED:{type(ex).__name__}"
            )
            return False
