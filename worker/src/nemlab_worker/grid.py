"""Grid import execution: bounded fetch children, per-day commit loop.

Mirrors ``refresh.py``: the parent owns one child process per provider
request (two per market day — market then power), hands it only the OE
credential on a cleared environment, and bounds runtime/output. The child
mode (``--fetch-grid market|power REGION DAY OUTPUT``) never sees database
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
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from nemlab_core.prices import Region
from nemlab_infrastructure.grid.batch import GridBatch, Metric, Slot
from nemlab_infrastructure.grid.imports import (
    DayOutcome,
    GridImportJob,
    GridImportJobs,
    StaleClaimException,
)
from nemlab_infrastructure.grid.source import GridFetch, OeGridSource
from nemlab_infrastructure.prices.batch import Kind
from nemlab_infrastructure.prices.source import Failure
from nemlab_worker.refresh import (
    MAX_OUTPUT_BYTES,
    TERMINATE_SECONDS,
    TIMEOUT_SECONDS,
    TerminationFailure,
    _start_watchdog,
)

LOG = logging.getLogger(__name__)

MODE = "--fetch-grid"
GROUPS = ("market", "power")
_FAILURE_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,79}")


# -- outcome contract -----------------------------------------------------------


def _fetch_json(fetch: GridFetch) -> str:
    series = []
    for batch in fetch.series:
        slots = []
        for slot in batch.slots:
            value = "null" if slot.value is None else str(slot.value)
            slots.append(f'{{"kind":"{slot.kind.name}","value":{value}}}')
        series.append(
            '{"metric":'
            + json.dumps(batch.metric.value)
            + ',"series":'
            + json.dumps(batch.series)
            + ',"slots":['
            + ",".join(slots)
            + "]}"
        )
    return (
        '{"series":['
        + ",".join(series)
        + '],"retrieved_at":'
        + json.dumps(fetch.retrieved_at.isoformat())
        + ',"response_hash":'
        + json.dumps(fetch.response_hash)
        + ',"source_version":'
        + json.dumps(fetch.source_version)
        + "}"
    )


def _read_fetch(region: Region, day: date, data: object) -> GridFetch:
    if not isinstance(data, dict):
        raise ValueError("fetch result must be an object")
    batches = []
    for entry in data["series"]:
        slots = tuple(
            Slot(
                Kind[s["kind"]],
                None if s["value"] is None else Decimal(str(s["value"])),
            )
            for s in entry["slots"]
        )
        batches.append(
            GridBatch(region, Metric(entry["metric"]), entry["series"], day, slots)
        )
    return GridFetch(
        tuple(batches),
        datetime.fromisoformat(data["retrieved_at"]),
        data["response_hash"],
        data["source_version"],
    )


@dataclass(frozen=True)
class GridOutcome:
    """Credential-free child result for one provider request."""

    fetch: GridFetch | None
    failure: str | None
    retryable: bool

    def __post_init__(self) -> None:
        if (self.fetch is None) == (self.failure is None):
            raise ValueError("Exactly one result or failure is required")
        if self.failure is not None and not _FAILURE_CODE.fullmatch(self.failure):
            raise ValueError("Invalid failure code")

    @staticmethod
    def success(fetch: GridFetch) -> "GridOutcome":
        return GridOutcome(fetch, None, False)

    @staticmethod
    def failed(code: str, retryable: bool) -> "GridOutcome":
        return GridOutcome(None, code, retryable)

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
    def from_json(region: Region, day: date, text: str) -> "GridOutcome":
        data = json.loads(text, parse_float=Decimal, parse_int=Decimal)
        fetch = data.get("fetch")
        failure = data.get("failure")
        return GridOutcome(
            _read_fetch(region, day, fetch) if fetch is not None else None,
            failure,
            bool(data["retryable"]),
        )


# -- child mode ------------------------------------------------------------------


def run_grid_fetch_command(arguments: list[str]) -> int:
    """``--fetch-grid market|power REGION DAY OUTPUT`` — fetch one group."""
    if len(arguments) != 5:
        return 2
    _start_watchdog()
    try:
        group, region, day = arguments[1], Region[arguments[2]], arguments[3]
        if group not in GROUPS:
            return 2
        source = OeGridSource(os.environ.get("OPEN_ELECTRICITY_API_KEY", ""))
        fetch = (
            source.fetch_market(region, date.fromisoformat(day))
            if group == "market"
            else source.fetch_power(region, date.fromisoformat(day))
        )
        outcome = GridOutcome.success(fetch)
    except Failure as failure:
        code = failure.code
        retryable = (not code.startswith("HTTP_4") or code == "HTTP_429") and (
            code != "RETRY_AFTER_EXCEEDS_BUDGET"
        )
        outcome = GridOutcome.failed(code, retryable)
    except (KeyError, ValueError):
        outcome = GridOutcome.failed("INVALID_SOURCE_DATA_OR_CONFIGURATION", False)
    except KeyboardInterrupt:
        outcome = GridOutcome.failed("FETCH_INTERRUPTED", True)
    except Exception:
        outcome = GridOutcome.failed("FETCH_FAILED", True)
    try:
        Path(arguments[4]).write_text(outcome.to_json())
        return 0
    except Exception:
        return 3


# -- parent process control ------------------------------------------------------


class GridFetchProcess:
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

    def fetch(self, group: str, job: GridImportJob, day: date) -> GridOutcome:
        output: Path | None = None
        process: subprocess.Popen[bytes] | None = None
        try:
            fd, name = tempfile.mkstemp(prefix="nemlab-grid-", suffix=".json")
            os.close(fd)
            output = Path(name)
            with self._lock:
                if self._closed:
                    raise InterruptedError("Worker is stopping")
                if self._active is not None:
                    raise RuntimeError("A fetch is already running")
                process = subprocess.Popen(  # noqa: S603 -- fixed interpreter/module
                    [
                        *self._command,
                        MODE,
                        group,
                        job.region.name,
                        str(day),
                        str(output),
                    ],
                    env=dict(self._environment),
                )
                self._active = process
            try:
                process.wait(timeout=self._timeout)
            except subprocess.TimeoutExpired:
                return GridOutcome.failed("FETCH_DEADLINE_EXCEEDED", True)
            if process.returncode != 0:
                return GridOutcome.failed("FETCH_PROCESS_FAILED", True)
            if output.stat().st_size > MAX_OUTPUT_BYTES * 8:
                return GridOutcome.failed("INVALID_CHILD_RESULT", False)
            return GridOutcome.from_json(job.region, day, output.read_text())
        except InterruptedError:
            raise
        except (OSError, ValueError, RuntimeError):
            return GridOutcome.failed("FETCH_PROCESS_FAILED", True)
        finally:
            if process is not None:
                self._terminate(process)
                with self._lock:
                    if self._active is process:
                        self._active = None
            if output is not None:
                with contextlib.suppress(OSError):
                    output.unlink(missing_ok=True)

    def close(self) -> None:
        with self._lock:
            self._closed = True
            process = self._active
        if process is not None:
            self._terminate(process)

    def __enter__(self) -> "GridFetchProcess":
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


# -- worker ------------------------------------------------------------------------


class GridImportWorker:
    """Fixed-delay polling: claim a fenced import, then commit market days
    one at a time — each ``complete_day`` renews the lease and advances the
    durable ``next_day`` checkpoint."""

    def __init__(
        self,
        jobs: GridImportJobs,
        fetcher: GridFetchProcess,
        poll_interval: float,
    ) -> None:
        self._jobs = jobs
        self._fetcher = fetcher
        self._poll = poll_interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        LOG.info("Grid import polling started (%d ms interval)", int(self._poll * 1000))
        self._thread = threading.Thread(
            target=self._loop, name="grid-import-worker", daemon=True
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

    def _execute(self, job: GridImportJob) -> None:
        LOG.info(
            "Claimed grid import %s (%s %s..%s, attempt %d)",
            job.id,
            job.region.name,
            job.start,
            job.end,
            job.attempts,
        )
        token = job.claim_token
        day = job.next_day
        while day < job.end and self._running:
            if not self._import_day(job, token, day):
                return
            day = day + timedelta(days=1)
        if not self._running:
            with contextlib.suppress(StaleClaimException):
                self._jobs.fail(job.id, _token(job), "WORKER_STOPPED")

    def _import_day(self, job: GridImportJob, token: UUID | None, day: date) -> bool:
        """One day: market fetch is core; power is optional. Returns False
        when the job can no longer progress (retry/failed/cancelled/stale)."""
        started = time.monotonic()
        try:
            market = self._fetcher.fetch("market", job, day)
            if market.fetch is None:
                self._settle_failure(job, token, market)
                return False
            power = self._fetcher.fetch("power", job, day)
            outcome = DayOutcome(
                day,
                market.fetch,
                power.fetch,
                None if power.fetch is not None else power.failure,
            )
            done = self._jobs.complete_day(job.id, token, outcome)
            elapsed = int((time.monotonic() - started) * 1000)
            if done:
                LOG.info(
                    "Grid import %s finished %s..%s (%d ms)",
                    job.id,
                    job.start,
                    job.end,
                    elapsed,
                )
            else:
                LOG.info(
                    "Grid import %s committed %s (%d ms)%s",
                    job.id,
                    day,
                    elapsed,
                    ""
                    if power.fetch is not None
                    else f"; optional power failed: {power.failure}",
                )
            return not done
        except StaleClaimException:
            LOG.info("Discarded stale grid import result: job=%s", job.id)
            return False
        except InterruptedError:
            with contextlib.suppress(StaleClaimException):
                self._jobs.fail(job.id, _token(job), "WORKER_STOPPED")
            return False

    def _settle_failure(
        self, job: GridImportJob, token: UUID | None, outcome: GridOutcome
    ) -> None:
        if outcome.retryable:
            self._jobs.fail(job.id, _token(job), outcome.failure or "")
            LOG.info(
                "Grid import %s failed: %s; bounded retry scheduled",
                job.id,
                outcome.failure,
            )
        else:
            self._jobs.fail_permanently(job.id, _token(job), outcome.failure or "")
            LOG.info("Grid import %s failed permanently: %s", job.id, outcome.failure)

    def stop(self) -> None:
        self._running = False
        self._stop.set()
        self._fetcher.close()
        if self._thread is not None:
            self._thread.join(timeout=15)
            if self._thread.is_alive():
                LOG.warning("Worker shutdown timed out; unfinished claim will expire")
            self._thread = None


def _token(job: GridImportJob) -> UUID:
    if job.claim_token is None:
        raise StaleClaimException()
    return job.claim_token
