"""``SimulationWorker``/``SimulationProcess`` tests ported from the Java
worker suite — real child processes and real PostgreSQL, no live compute."""

import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
import sqlalchemy as sa
from pydantic import ValidationError
from sqlalchemy import text

from nemlab_core.hindsight import Status
from nemlab_core.prices import NEM_OFFSET, Interval, PriceDay, Region
from nemlab_core.request import (
    Costs,
    EfficiencyInput,
    SimulationRequest,
    Site,
    Windows,
)
from nemlab_infrastructure.prices.batch import Kind, PriceBatch, Slot
from nemlab_infrastructure.prices.batch import hash as batch_hash
from nemlab_infrastructure.prices.source import Fetch
from nemlab_infrastructure.prices.store import PriceStore
from nemlab_infrastructure.simulations import (
    Input,
    SimulationJobs,
    StaleClaim,
    Versions,
)
from nemlab_worker.main import run
from nemlab_worker.settings import WorkerSettings
from nemlab_worker.simulation import (
    SimulationProcess,
    SimulationWorker,
)

DAY = date(2023, 9, 11)
FIXTURE = Path(__file__).resolve().parent / "simulation_fixture.py"


def input(key: str = "a" * 64, versions: Versions | None = None) -> Input:
    """``SimulationProcessTest.input`` — one cheap dispatch day."""
    zero, one, power = Decimal(0), Decimal(1), Decimal(12)
    request = SimulationRequest(
        Region.NSW1,
        DAY,
        Site(one, zero, one, zero, power, power, power, power),
        EfficiencyInput(one, one, None),
        Costs(zero, zero, zero),
        Windows(0, 5, 5, 10),
    )
    start = datetime(DAY.year, DAY.month, DAY.day, tzinfo=NEM_OFFSET)
    intervals = tuple(
        Interval.from_end(
            Region.NSW1,
            start + timedelta(seconds=(i + 1) * 300),
            Decimal(-30 if i == 0 else 200),
        )
        for i in range(288)
    )
    return Input(
        key,
        request,
        PriceDay(Region.NSW1, DAY, intervals),
        versions or Versions.current(),
    )


def fixture_process(
    scenario: str, marker: Path, timeout: float = 15
) -> SimulationProcess:
    return SimulationProcess(
        command=[sys.executable, str(FIXTURE), scenario, str(marker)],
        timeout=timeout,
    )


def await_marker(marker: Path) -> None:
    end = time.monotonic() + 5
    while (not marker.exists() or marker.stat().st_size == 0) and (
        time.monotonic() < end
    ):
        time.sleep(0.02)
    assert marker.exists()


def assert_cleaned(marker: Path) -> None:
    lines = marker.read_text().splitlines()
    pid = int(lines[0])
    with pytest.raises((ProcessLookupError, PermissionError, OSError)):
        os.kill(pid, 0)
    assert not Path(lines[1]).exists()
    assert not Path(lines[2]).exists()


def await_condition(condition: Callable[[], bool]) -> None:
    end = time.monotonic() + 20
    while not condition():
        if time.monotonic() >= end:
            pytest.fail("Condition did not become true within 20 seconds")
        time.sleep(0.03)


def seed(store: PriceStore) -> None:
    source = input()
    store.save(
        Fetch(
            PriceBatch(
                source.prices.region,
                source.prices.date,
                tuple(Slot(Kind.VALUE, i.price) for i in source.prices.intervals),
            ),
            datetime.now(UTC),
            batch_hash("fixture"),
            "test",
        )
    )


@pytest.fixture
def jobs(scratch_db: sa.Engine, store: PriceStore) -> SimulationJobs:
    # Seeding here (not in ``store``) keeps it after the autouse ``clean``.
    seed(store)
    return SimulationJobs(scratch_db)


def _ready(scratch_db: sa.Engine, id: UUID) -> None:
    with scratch_db.begin() as conn:
        conn.execute(
            text(
                "UPDATE simulation_job SET available_at = clock_timestamp()"
                " - interval '1 second' WHERE id = :id"
            ),
            {"id": id},
        )


# -- SimulationProcess -----------------------------------------------------------


def test_child_computes_both_strategies_without_credentials_and_cleans(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "success"
    with fixture_process("success", marker) as process:
        outcome = process.execute(input())
        assert outcome.failure is None
        assert outcome.result is not None
        assert outcome.result.hindsight.status is Status.OPTIMAL
        assert outcome.result.fixed_accounting.margin == pytest.approx(230)
        assert_cleaned(marker)


def test_packaged_module_supports_the_same_child_mode(tmp_path: Path) -> None:
    with SimulationProcess(
        command=[sys.executable, "-m", "nemlab_worker"], timeout=15
    ) as process:
        outcome = process.execute(input())
        assert outcome.failure is None
        assert outcome.result is not None
        assert outcome.result.hindsight.accounting is not None
        assert outcome.result.hindsight.accounting.margin == pytest.approx(230)


def test_parent_deadline_kills_stalled_child_before_returning(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "hang"
    with fixture_process("hang", marker, timeout=1) as process:
        outcome = process.execute(input())
        assert outcome.failure == "SIMULATION_DEADLINE_EXCEEDED"
        assert outcome.retryable
        assert_cleaned(marker)


def test_shutdown_kills_child_and_prevents_new_execution(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "stop"
    process = fixture_process("hang", marker, timeout=15)
    outcome_box: list[str | BaseException | None] = []

    def run() -> None:
        try:
            outcome_box.append(process.execute(input()).failure)
        except BaseException as e:
            outcome_box.append(e)

    thread = threading.Thread(target=run)
    try:
        thread.start()
        await_marker(marker)
        process.close()
        thread.join(timeout=5)
        assert not thread.is_alive()
        assert outcome_box
        assert outcome_box[0] is not None
        assert_cleaned(marker)
        with pytest.raises(InterruptedError):
            process.execute(input())
    finally:
        process.close()
        thread.join(timeout=5)


def test_corrupt_results_are_terminal_and_crashes_are_retryable(
    tmp_path: Path,
) -> None:
    for scenario in ("malformed", "oversized", "crash"):
        marker = tmp_path / scenario
        with fixture_process(scenario, marker) as process:
            outcome = process.execute(input())
            expected = (
                "SIMULATION_PROCESS_FAILED"
                if scenario == "crash"
                else "INVALID_CHILD_RESULT"
            )
            assert outcome.failure == expected
            assert outcome.retryable == (scenario == "crash")
            assert_cleaned(marker)


def test_child_watchdog_bounds_an_orphan_without_the_parent_deadline(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "watchdog"
    started = time.monotonic()
    with fixture_process("watchdog", marker, timeout=25) as process:
        outcome = process.execute(input())
        assert outcome.failure == "SIMULATION_DEADLINE_EXCEEDED"
        assert time.monotonic() - started < 23
        assert_cleaned(marker)


def test_unsupported_stored_version_does_not_launch_child(
    tmp_path: Path,
) -> None:
    base = input()
    v = base.versions
    old = Versions(
        v.request,
        "old-model",
        v.fixed,
        v.hindsight,
        v.solver,
        v.execution_profile,
        v.limits,
    )
    marker = tmp_path / "unsupported"
    with fixture_process("success", marker) as process:
        outcome = process.execute(Input(base.key, base.request, base.prices, old))
        assert outcome.failure == "UNSUPPORTED_SIMULATION_VERSION"
        assert not outcome.retryable
        assert not marker.exists()


def test_mismatched_key_is_terminal(tmp_path: Path) -> None:
    """A child that echoes the wrong key is rejected as corrupt."""
    marker = tmp_path / "wrongkey"
    with fixture_process("wrongkey", marker) as process:
        outcome = process.execute(input())
        assert outcome.failure == "INVALID_CHILD_RESULT"
        assert not outcome.retryable
        assert_cleaned(marker)


# -- SimulationWorker -------------------------------------------------------------


def test_restart_recovers_claim_and_persists_actual_child_results(
    jobs: SimulationJobs, scratch_db: sa.Engine, tmp_path: Path
) -> None:
    id = jobs.submit(input().request)
    old = jobs.claim()
    assert old is not None
    with scratch_db.begin() as conn:
        conn.execute(
            text(
                "UPDATE simulation_job SET lease_until = clock_timestamp()"
                " - interval '1 second' WHERE id = :id"
            ),
            {"id": id},
        )
    process = fixture_process("success", tmp_path / "success")
    worker = SimulationWorker(SimulationJobs(scratch_db), process, 0.02)
    try:
        worker.start()
        await_condition(lambda: jobs.find(id).status == "QUEUED")  # type: ignore[union-attr]
        _ready(scratch_db, id)
        await_condition(lambda: jobs.find(id).status == "SUCCEEDED")  # type: ignore[union-attr]
        assert jobs.find(id).attempts == 2  # type: ignore[union-attr]
        result = jobs.result(id)
        assert result is not None
        assert result.fixed_accounting.margin == pytest.approx(230)
        with pytest.raises(StaleClaim):
            jobs.fail(id, old.token, "LATE", True)
    finally:
        worker.stop()


def test_shutdown_leaves_recoverable_work_and_no_live_child(
    jobs: SimulationJobs, scratch_db: sa.Engine, tmp_path: Path
) -> None:
    id = jobs.submit(input().request)
    marker = tmp_path / "stop"
    worker = SimulationWorker(jobs, fixture_process("hang", marker, timeout=15), 0.02)
    try:
        worker.start()
        await_marker(marker)
    finally:
        worker.stop()
    assert not worker.running
    job = jobs.find(id)
    assert job is not None
    assert job.status == "QUEUED"
    assert job.diagnostic == "WORKER_STOPPED"
    assert_cleaned(marker)


def test_deadline_failures_reach_terminal_state_after_bounded_retries(
    jobs: SimulationJobs, scratch_db: sa.Engine, tmp_path: Path
) -> None:
    id = jobs.submit(input().request)
    worker = SimulationWorker(
        jobs, fixture_process("hang", tmp_path / "timeout", timeout=1), 0.02
    )
    try:
        worker.start()
        for attempt in (1, 2):
            await_condition(
                lambda a=attempt: (
                    jobs.find(id).status == "QUEUED"  # type: ignore[union-attr]
                    and jobs.find(id).attempts == a
                )  # type: ignore[union-attr]
            )
            _ready(scratch_db, id)
        await_condition(lambda: jobs.find(id).status == "FAILED")  # type: ignore[union-attr]
        job = jobs.find(id)
        assert job is not None
        assert job.attempts == 3
        assert job.diagnostic == "SIMULATION_DEADLINE_EXCEEDED"
        assert jobs.result(id) is None
    finally:
        worker.stop()


def test_packaged_worker_polls_and_runs_its_own_child(
    jobs: SimulationJobs, scratch_db: sa.Engine
) -> None:
    id = jobs.submit(input().request)
    url = scratch_db.url
    env = {
        "NEMLAB_DB_URL": (f"jdbc:postgresql://{url.host}:{url.port}/{url.database}"),
        "NEMLAB_DB_USER": url.username or "",
        "NEMLAB_DB_PASSWORD": url.password or "",
        "NEMLAB_SIMULATION_ENABLED": "true",
        "NEMLAB_SIMULATION_POLL_MS": "1000",
    }
    process = subprocess.Popen(
        [sys.executable, "-m", "nemlab_worker"],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        await_condition(lambda: jobs.find(id).status == "SUCCEEDED")  # type: ignore[union-attr]
        assert process.poll() is None
        result = jobs.result(id)
        assert result is not None
        assert result.hindsight.accounting is not None
        assert result.hindsight.accounting.margin == pytest.approx(230)
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


# -- settings ---------------------------------------------------------------------


def test_independent_opt_in_needs_no_oe_credential() -> None:
    settings = WorkerSettings(simulation_enabled=True)
    assert settings.simulation_enabled
    assert settings.open_electricity_api_key is None


def test_simulation_poll_interval_is_bounded() -> None:
    with pytest.raises(ValidationError):
        WorkerSettings(simulation_enabled=True, simulation_poll_ms=0)
    with pytest.raises(ValidationError):
        WorkerSettings(simulation_enabled=True, simulation_poll_ms=60_001)
    WorkerSettings(simulation_enabled=True, simulation_poll_ms=1000)


def test_enabled_run_starts_and_stops_cleanly() -> None:
    settings = WorkerSettings(simulation_enabled=True)
    stop = threading.Event()
    finished = threading.Event()

    def target() -> None:
        run(settings, stop)
        finished.set()

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    time.sleep(0.2)
    stop.set()
    assert finished.wait(timeout=10)
