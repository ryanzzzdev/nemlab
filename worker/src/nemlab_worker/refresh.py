"""Refresh queue execution: child fetch process, schedule and poll loop.

Ports the Java ``au.nemlab.worker.refresh`` package. The parent owns one
child process at a time, hands it only the OE credential on a cleared
environment, bounds its runtime and output, and classifies the result back
onto the job claim. The child mode (``--fetch-price``) needs no database
credentials; a watchdog bounds it even if the worker dies.
"""

import contextlib
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from nemlab_core import decimal_text
from nemlab_core.prices import NEM_OFFSET, Region
from nemlab_infrastructure.jobs import (
    RefreshJob,
    RefreshJobService,
    StaleClaimException,
)
from nemlab_infrastructure.prices.batch import Kind, PriceBatch, Slot
from nemlab_infrastructure.prices.source import Failure, Fetch, OePriceSource

LOG = logging.getLogger(__name__)

MODE = "--fetch-price"
TIMEOUT_SECONDS = 240
MAX_OUTPUT_BYTES = 256_000
TERMINATE_SECONDS = 5
_FAILURE_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,79}")


class TerminationFailure(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Fetch process did not terminate; worker polling must stop")


# -- outcome contract -----------------------------------------------------------


def _fetch_json(fetch: Fetch) -> str:
    """Slot prices stay plain decimal text, exactly like the JSONB store."""
    batch = fetch.batch
    prices = []
    for slot in batch.slots:
        price = "null" if slot.price is None else _plain(slot.price)
        prices.append(f'{{"kind":"{slot.kind.name}","price":{price}}}')

    return (
        '{"batch":{"region":'
        + json.dumps(batch.region.name)
        + ',"day":'
        + json.dumps(str(batch.day))
        + ',"slots":['
        + ",".join(prices)
        + ']},"retrieved_at":'
        + json.dumps(fetch.retrieved_at.isoformat())
        + ',"response_hash":'
        + json.dumps(fetch.response_hash)
        + ',"source_version":'
        + json.dumps(fetch.source_version)
        + "}"
    )


def _plain(value: Decimal) -> str:
    return decimal_text.to_plain_string(value)


def _read_fetch(data: object) -> Fetch:
    if not isinstance(data, dict):
        raise ValueError("fetch result must be an object")
    batch_data = data["batch"]
    slots = tuple(
        Slot(
            Kind[entry["kind"]],
            None if entry["price"] is None else Decimal(str(entry["price"])),
        )
        for entry in batch_data["slots"]
    )
    return Fetch(
        PriceBatch(
            Region[batch_data["region"]], date.fromisoformat(batch_data["day"]), slots
        ),
        datetime.fromisoformat(data["retrieved_at"]),
        data["response_hash"],
        data["source_version"],
    )


@dataclass(frozen=True)
class FetchOutcome:
    """Small, credential-free result exchanged with the isolated fetch child."""

    fetch: Fetch | None
    failure: str | None
    retryable: bool

    def __post_init__(self) -> None:
        if (self.fetch is None) == (self.failure is None):
            raise ValueError("Exactly one result or failure is required")
        if self.failure is not None and not _FAILURE_CODE.fullmatch(self.failure):
            raise ValueError("Invalid failure code")

    @staticmethod
    def success(fetch: Fetch) -> "FetchOutcome":
        return FetchOutcome(fetch, None, False)

    @staticmethod
    def failed(code: str, retryable: bool) -> "FetchOutcome":
        return FetchOutcome(None, code, retryable)

    def to_json(self) -> str:
        return (
            '{"fetch":'
            + (_fetch_json(self.fetch) if self.fetch is not None else "null")
            + ',"failure":'
            + json.dumps(self.failure)
            + ',"retryable":'
            + ("true" if self.retryable else "false")
            + "}"
        )

    @staticmethod
    def from_json(text: str) -> "FetchOutcome":
        data = json.loads(text, parse_float=Decimal, parse_int=Decimal)
        fetch = data.get("fetch")
        failure = data.get("failure")
        return FetchOutcome(
            _read_fetch(fetch) if fetch is not None else None,
            failure,
            bool(data["retryable"]),
        )


# -- child mode ------------------------------------------------------------------


def run_fetch_command(arguments: list[str]) -> int:
    """``--fetch-price REGION DAY OUTPUT`` — Java ``FetchCommand.run``."""
    if len(arguments) != 4:
        return 2
    _start_watchdog()
    try:
        region = Region[arguments[1]]
        day = date.fromisoformat(arguments[2])
        source = OePriceSource(os.environ.get("OPEN_ELECTRICITY_API_KEY", ""))
        outcome = FetchOutcome.success(source.fetch(region, day))
    except Failure as failure:
        code = failure.code
        retryable = (not code.startswith("HTTP_4") or code == "HTTP_429") and (
            code != "RETRY_AFTER_EXCEEDS_BUDGET"
        )
        outcome = FetchOutcome.failed(code, retryable)
    except (KeyError, ValueError):
        outcome = FetchOutcome.failed("INVALID_SOURCE_DATA_OR_CONFIGURATION", False)
    except KeyboardInterrupt:
        outcome = FetchOutcome.failed("FETCH_INTERRUPTED", True)
    except Exception:
        outcome = FetchOutcome.failed("FETCH_FAILED", True)
    try:
        Path(arguments[3]).write_text(outcome.to_json())
        return 0
    except Exception:
        return 3


def _start_watchdog() -> None:
    def expire() -> None:
        time.sleep(TIMEOUT_SECONDS)
        # Also bounds orphaned children if the worker parent crashes.
        os._exit(124)

    threading.Thread(target=expire, name="fetch-deadline", daemon=True).start()


# -- parent process control ------------------------------------------------------


class PriceFetchProcess:
    """One owned child at a time; termination precedes result publication."""

    def __init__(
        self,
        api_key: str,
        command: list[str] | None = None,
        timeout: float = TIMEOUT_SECONDS,
    ) -> None:
        self._command = command or [sys.executable, "-m", "nemlab_worker"]
        self._environment = {"OPEN_ELECTRICITY_API_KEY": api_key}
        self._timeout = timeout
        self._active: subprocess.Popen[bytes] | None = None
        self._closed = False
        self._lock = threading.Lock()

    def fetch(self, job: RefreshJob) -> FetchOutcome:
        output: Path | None = None
        process: subprocess.Popen[bytes] | None = None
        try:
            fd, name = tempfile.mkstemp(prefix="nemlab-fetch-", suffix=".json")
            os.close(fd)
            output = Path(name)
            with self._lock:
                if self._closed:
                    raise InterruptedError("Worker is stopping")
                if self._active is not None:
                    raise RuntimeError("A fetch is already running")
                # The child logs each OE request/response on its console; never
                # credentials or raw bodies. Inherit so those lines reach the
                # worker log.
                process = subprocess.Popen(  # noqa: S603 -- fixed interpreter/module
                    [
                        *self._command,
                        MODE,
                        job.region.name,
                        str(job.day),
                        str(output),
                    ],
                    env=dict(self._environment),
                )
                self._active = process
            try:
                process.wait(timeout=self._timeout)
            except subprocess.TimeoutExpired:
                return FetchOutcome.failed("FETCH_DEADLINE_EXCEEDED", True)
            if process.returncode != 0:
                return FetchOutcome.failed("FETCH_PROCESS_FAILED", True)
            if output.stat().st_size > MAX_OUTPUT_BYTES:
                return FetchOutcome.failed("INVALID_CHILD_RESULT", False)
            return FetchOutcome.from_json(output.read_text())
        except InterruptedError:
            raise
        except (OSError, ValueError, RuntimeError):
            return FetchOutcome.failed("FETCH_PROCESS_FAILED", True)
        finally:
            if process is not None:
                self._terminate(process)
                with self._lock:
                    if self._active is process:
                        self._active = None
            if output is not None:
                # No credentials or raw responses are written to this
                # temporary file.
                with contextlib.suppress(OSError):
                    output.unlink(missing_ok=True)

    def close(self) -> None:
        with self._lock:
            self._closed = True
            process = self._active
        if process is not None:
            self._terminate(process)

    def __enter__(self) -> "PriceFetchProcess":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    @staticmethod
    def _terminate(process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        process.kill()
        try:
            process.wait(timeout=TERMINATE_SECONDS)
        except subprocess.TimeoutExpired:
            raise TerminationFailure() from None


# -- schedule ---------------------------------------------------------------------


class RefreshSchedule:
    """Once per region/day, with persistent keys protecting restarts and
    multiple workers."""

    def __init__(
        self,
        jobs: RefreshJobService,
        clock: Callable[[], datetime],
        regions: list[Region],
    ) -> None:
        self._jobs = jobs
        self._clock = clock
        self._regions = list(dict.fromkeys(regions))
        self._submitted: dict[Region, date] = {}

    def submit_due(self) -> None:
        day = (self._clock().astimezone(NEM_OFFSET) - timedelta(minutes=15)).date()
        day = day - timedelta(days=1)
        for region in self._regions:
            if self._submitted.get(region) != day:
                job = self._jobs.submit(
                    f"daily-price-v1:{region.name}:{day}", region, day, "scheduler"
                )
                LOG.info(
                    "Scheduled daily price refresh %s %s -> job %s",
                    region.name,
                    day,
                    job,
                )
                self._submitted[region] = day


# -- worker ------------------------------------------------------------------------


def _utc_now() -> datetime:
    return datetime.now(UTC)


class RefreshWorker:
    """Fixed-delay polling: schedule due days, claim a fenced job, run the
    isolated fetch, then settle the claim."""

    def __init__(
        self,
        jobs: RefreshJobService,
        schedule: RefreshSchedule,
        fetcher: PriceFetchProcess,
        poll_interval: float,
    ) -> None:
        self._jobs = jobs
        self._schedule = schedule
        self._fetcher = fetcher
        self._poll = poll_interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        LOG.info(
            "Price refresh polling started (%d ms interval)",
            int(self._poll * 1000),
        )
        self._thread = threading.Thread(
            target=self._loop, name="price-refresh-worker", daemon=True
        )
        self._thread.start()

    @property
    def running(self) -> bool:
        return self._running

    def _loop(self) -> None:
        while self._running:
            self.tick()
            self._stop.wait(self._poll)

    def tick(self) -> None:
        if not self._running:
            return
        try:
            self._schedule.submit_due()
        except Exception:
            LOG.warning(
                "Scheduled submission failed; retrying on next poll (details omitted)"
            )
        if not self._running:
            return
        try:
            job = self._jobs.claim()
            if job is not None:
                self._execute(job)
        except TerminationFailure:
            self._running = False
            LOG.error(
                "Worker stopped: fetch process could not be terminated;"
                " operator intervention required"
            )
        except Exception:
            LOG.warning(
                "Queue operation failed; lease recovery remains available"
                " (details omitted)"
            )

    def _execute(self, job: RefreshJob) -> None:
        LOG.info(
            "Claimed refresh job %s (%s %s, attempt %d); fetching OE prices",
            job.id,
            job.region.name,
            job.day,
            job.attempts,
        )
        started = time.monotonic()
        try:
            outcome = self._fetcher.fetch(job)
            elapsed = int((time.monotonic() - started) * 1000)
            if outcome.fetch is not None:
                self._jobs.complete(job.id, _token(job), outcome.fetch)
                LOG.info(
                    "Refresh job %s committed stored prices for %s %s (%d ms)",
                    job.id,
                    job.region.name,
                    job.day,
                    elapsed,
                )
            elif outcome.retryable:
                self._jobs.fail(job.id, _token(job), outcome.failure or "")
                LOG.info(
                    "Refresh job %s failed: %s; bounded retry scheduled (%d ms)",
                    job.id,
                    outcome.failure,
                    elapsed,
                )
            else:
                self._jobs.fail_permanently(job.id, _token(job), outcome.failure or "")
                LOG.info(
                    "Refresh job %s failed permanently: %s (%d ms)",
                    job.id,
                    outcome.failure,
                    elapsed,
                )
        except StaleClaimException:
            LOG.info("Discarded stale refresh result: job=%s", job.id)
        except InterruptedError:
            with contextlib.suppress(StaleClaimException):
                self._jobs.fail(job.id, _token(job), "WORKER_STOPPED")

    def stop(self) -> None:
        self._running = False
        self._stop.set()
        self._fetcher.close()
        if self._thread is not None:
            self._thread.join(timeout=15)
            if self._thread.is_alive():
                LOG.warning("Worker shutdown timed out; unfinished claim will expire")
            self._thread = None


def _token(job: RefreshJob) -> UUID:
    if job.claim_token is None:
        raise StaleClaimException()
    return job.claim_token
