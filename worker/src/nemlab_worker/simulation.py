"""Simulation queue execution: isolated compute child, poll loop.

Ports the Java ``au.nemlab.worker.simulation`` package. The parent owns one
child process at a time, hands it the captured ``Input`` on a cleared
environment, bounds its runtime, and only publishes results that re-validate
in the parent. The child mode (``--simulate``) needs no database credentials;
a self-watchdog bounds it even if the worker dies.
"""

import contextlib
import logging
import os
import resource
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from nemlab_core import comparison
from nemlab_core.comparison import SimulationComparison
from nemlab_infrastructure import simulations
from nemlab_infrastructure.simulations import (
    Input,
    SimulationJobs,
    StaleClaim,
    UnsupportedVersion,
)

LOG = logging.getLogger(__name__)

SIMULATE_MODE = "--simulate"
DEADLINE_SECONDS = 15
MAX_INPUT_BYTES = 512_000
MAX_OUTPUT_BYTES = 1_000_000
TERMINATE_SECONDS = 5
# Enforceable Linux bound on the child's total address space — the Java
# equivalent is ``-Xmx512m``; measured peak VmSize for a real comparison run
# is ~1.9 GiB (mostly reservations), so 4 GiB bounds leaks without clipping
# normal imports.
ADDRESS_LIMIT_BYTES = 4 << 30


class TerminationFailure(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "Simulation process did not terminate; worker polling must stop"
        )


# -- child mode ------------------------------------------------------------------


def run_simulation_command(arguments: list[str]) -> int:
    """``--simulate INPUT OUTPUT`` — Java ``SimulationCommand.run``."""
    if len(arguments) != 3:
        return 2
    with contextlib.suppress(OSError, ValueError):
        resource.setrlimit(
            resource.RLIMIT_AS, (ADDRESS_LIMIT_BYTES, ADDRESS_LIMIT_BYTES)
        )
    _start_watchdog()
    try:
        input_file = Path(arguments[1])
        if input_file.stat().st_size > MAX_INPUT_BYTES:
            return 2
        input = simulations.read_input(input_file.read_text())
        result = comparison.run(input.parameters(), input.prices, input.versions.limits)
        Path(arguments[2]).write_text(simulations.output_json(input.key, result))
        return 0
    except Exception:
        return 3


def _start_watchdog() -> None:
    def expire() -> None:
        time.sleep(DEADLINE_SECONDS)
        # Also bounds orphaned children if the worker parent crashes.
        os._exit(124)

    threading.Thread(target=expire, name="simulation-deadline", daemon=True).start()


# -- parent process control ------------------------------------------------------


@dataclass(frozen=True)
class Outcome:
    """Exactly one of a validated comparison or a classified failure."""

    result: SimulationComparison | None
    failure: str | None
    retryable: bool

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("Exactly one result or failure is required")

    @staticmethod
    def failed(code: str, retryable: bool) -> "Outcome":
        return Outcome(None, code, retryable)


class SimulationProcess:
    """One owned child at a time; termination precedes result publication."""

    def __init__(
        self,
        command: list[str] | None = None,
        timeout: float = DEADLINE_SECONDS,
    ) -> None:
        self._command = command or [sys.executable, "-m", "nemlab_worker"]
        self._timeout = timeout
        self._active: subprocess.Popen[bytes] | None = None
        self._closed = False
        self._lock = threading.Lock()

    def execute(self, input: Input) -> Outcome:
        try:
            input.parameters()  # unsupported stored versions never launch
        except UnsupportedVersion:
            return Outcome.failed("UNSUPPORTED_SIMULATION_VERSION", False)
        input_file: Path | None = None
        output: Path | None = None
        process: subprocess.Popen[bytes] | None = None
        try:
            fd, name = tempfile.mkstemp(
                prefix="nemlab-simulation-input-", suffix=".json"
            )
            os.close(fd)
            input_file = Path(name)
            input_file.write_text(simulations.input_json(input))
            fd, name = tempfile.mkstemp(
                prefix="nemlab-simulation-result-", suffix=".json"
            )
            os.close(fd)
            output = Path(name)
            with self._lock:
                if self._closed:
                    raise InterruptedError("Worker is stopping")
                if self._active is not None:
                    raise RuntimeError("A simulation is already running")
                process = subprocess.Popen(  # noqa: S603 -- fixed interpreter/module
                    [*self._command, SIMULATE_MODE, str(input_file), str(output)],
                    env={},
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._active = process
            try:
                process.wait(timeout=self._timeout)
            except subprocess.TimeoutExpired:
                return Outcome.failed("SIMULATION_DEADLINE_EXCEEDED", True)
            if self._closed:
                # ``stop()`` killed the child — mirror Java's interrupted
                # waitFor so the claim is released as WORKER_STOPPED.
                raise InterruptedError("Worker is stopping")
            if process.returncode == 124:
                return Outcome.failed("SIMULATION_DEADLINE_EXCEEDED", True)
            if process.returncode != 0:
                return Outcome.failed("SIMULATION_PROCESS_FAILED", True)
            if output.stat().st_size > MAX_OUTPUT_BYTES:
                return Outcome.failed("INVALID_CHILD_RESULT", False)
            try:
                key, result = simulations.read_output(output.read_text())
                if key != input.key or result is None:
                    return Outcome.failed("INVALID_CHILD_RESULT", False)
                comparison.validate(
                    result, input.parameters(), input.prices, input.versions.limits
                )
                return Outcome(result, None, False)
            except Exception:
                return Outcome.failed("INVALID_CHILD_RESULT", False)
        except InterruptedError:
            raise
        except (OSError, ValueError, RuntimeError):
            return Outcome.failed("SIMULATION_PROCESS_FAILED", True)
        finally:
            if process is not None:
                self._terminate(process)
                with self._lock:
                    if self._active is process:
                        self._active = None
            if input_file is not None:
                with contextlib.suppress(OSError):
                    input_file.unlink(missing_ok=True)
            if output is not None:
                # No credentials or raw responses are written to these files.
                with contextlib.suppress(OSError):
                    output.unlink(missing_ok=True)

    def close(self) -> None:
        with self._lock:
            self._closed = True
            process = self._active
        if process is not None:
            self._terminate(process)

    def __enter__(self) -> "SimulationProcess":
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


class SimulationWorker:
    """Fixed-delay polling: claim a fenced job, run the isolated comparison,
    then settle the claim."""

    def __init__(
        self,
        jobs: SimulationJobs,
        process: SimulationProcess,
        poll_interval: float,
    ) -> None:
        self._jobs = jobs
        self._process = process
        self._poll = poll_interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        LOG.info("Simulation polling started (%d ms interval)", int(self._poll * 1000))
        self._thread = threading.Thread(
            target=self._loop, name="simulation-worker", daemon=True
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
            LOG.error("Simulation process could not terminate; polling stopped")
        except Exception:
            LOG.warning(
                "Simulation queue operation failed; lease recovery remains"
                " available (details omitted)"
            )

    def _execute(self, job: simulations.Job) -> None:
        LOG.info(
            "Claimed simulation job %s; running comparison in child process",
            job.id,
        )
        try:
            outcome = self._process.execute(self._jobs.input(job.id))
            if outcome.result is not None:
                self._jobs.complete(job.id, _token(job), outcome.result)
                LOG.info("Simulation job %s succeeded; comparison stored", job.id)
            else:
                self._jobs.fail(
                    job.id, _token(job), outcome.failure or "", outcome.retryable
                )
                LOG.info(
                    "Simulation job %s failed: %s (retryable=%s)",
                    job.id,
                    outcome.failure,
                    outcome.retryable,
                )
        except StaleClaim:
            LOG.info("Discarded stale simulation result: job=%s", job.id)
        except InterruptedError:
            with contextlib.suppress(StaleClaim):
                self._jobs.fail(job.id, _token(job), "WORKER_STOPPED", True)

    def stop(self) -> None:
        self._running = False
        self._stop.set()
        self._process.close()
        if self._thread is not None:
            self._thread.join(timeout=15)
            if self._thread.is_alive():
                LOG.warning("Simulation shutdown timed out; claim will expire")


def _token(job: simulations.Job) -> UUID:
    if job.token is None:
        raise StaleClaim()
    return job.token
