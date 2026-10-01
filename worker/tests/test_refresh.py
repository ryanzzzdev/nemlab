"""``RefreshWorker``/``PriceFetchProcess`` tests ported from the Java worker
suite — real child processes and real PostgreSQL, no live OE traffic."""

import os
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
import sqlalchemy as sa
from pydantic import ValidationError

from nemlab_core.prices import Region
from nemlab_infrastructure.jobs import RefreshJob, RefreshJobService, Status
from nemlab_infrastructure.prices.store import PriceStore
from nemlab_worker.main import run
from nemlab_worker.refresh import (
    MODE,
    FetchOutcome,
    PriceFetchProcess,
    RefreshSchedule,
    RefreshWorker,
)
from nemlab_worker.settings import WorkerSettings

DAY = date(2023, 9, 11)
REGION = Region.NSW1
FIXTURE = Path(__file__).resolve().parent / "fetch_fixture.py"


def job() -> RefreshJob:
    return RefreshJob(
        uuid.uuid4(),
        uuid.uuid4(),
        REGION,
        DAY,
        Status.RUNNING,
        1,
        uuid.uuid4(),
        datetime.now(UTC) + timedelta(seconds=300),
        datetime.now(UTC),
        None,
    )


def fixture_fetcher(
    scenario: str, marker: Path, timeout: float = 10
) -> PriceFetchProcess:
    return PriceFetchProcess(
        "test-only",
        command=[sys.executable, str(FIXTURE), scenario, str(marker)],
        timeout=timeout,
    )


def await_marker(marker: Path) -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if marker.exists() and marker.stat().st_size > 0:
            return
        time.sleep(0.02)
    pytest.fail(f"marker {marker} was not written")


def assert_child_stopped(marker: Path) -> None:
    pid = int(marker.read_text().splitlines()[0])
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            return
        time.sleep(0.02)
    pytest.fail(f"child {pid} still running")


def await_condition(condition: Callable[[], bool]) -> None:
    deadline = time.monotonic() + 15
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert condition(), "worker did not reach expected state before deadline"


def job_status(jobs: RefreshJobService, id: UUID) -> Status | None:
    found = jobs.find(id)
    return found.status if found is not None else None


def worker_for(jobs: RefreshJobService, scenario: str, marker: Path) -> RefreshWorker:
    fetcher = fixture_fetcher(scenario, marker)
    schedule = RefreshSchedule(jobs, lambda: datetime.now(UTC), [])
    return RefreshWorker(jobs, schedule, fetcher, 0.02)


# -- PriceFetchProcess -----------------------------------------------------------


def test_round_trips_validated_prices_and_deletes_temporary_output(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "child"
    with fixture_fetcher("success", marker) as fetcher:
        result = fetcher.fetch(job())
        assert result.failure is None
        assert result.fetch is not None
        assert len(result.fetch.batch.slots) == 288
        output_path = Path(marker.read_text().splitlines()[1])
        assert not output_path.exists()


def test_kills_a_stalled_child_before_returning_a_timeout(tmp_path: Path) -> None:
    marker = tmp_path / "child"
    with fixture_fetcher("hang", marker, timeout=1) as fetcher:
        result = fetcher.fetch(job())
        assert result.failure == "FETCH_DEADLINE_EXCEEDED"
        assert result.retryable
        assert_child_stopped(marker)


def test_shutdown_kills_active_child_and_disallows_another_fetch(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "child"
    with fixture_fetcher("hang", marker, timeout=30) as fetcher:
        with ThreadPoolExecutor(1) as executor:
            future = executor.submit(fetcher.fetch, job())
            await_marker(marker)
            fetcher.close()
            assert future.result(timeout=5).failure is not None
        assert_child_stopped(marker)
        with pytest.raises(InterruptedError):
            fetcher.fetch(job())


@pytest.mark.parametrize("scenario", ["crash", "malformed", "huge"])
def test_failed_children_produce_safe_diagnostic_codes(
    scenario: str, tmp_path: Path
) -> None:
    marker = tmp_path / scenario
    with fixture_fetcher(scenario, marker) as fetcher:
        result = fetcher.fetch(job())
    expected = "INVALID_CHILD_RESULT" if scenario == "huge" else "FETCH_PROCESS_FAILED"
    assert result.failure == expected


def test_child_never_inherits_database_credentials(tmp_path: Path) -> None:
    """The fixture aborts if ``NEMLAB_DB_PASSWORD`` leaks into the child env."""
    marker = tmp_path / "child"
    with fixture_fetcher("success", marker) as fetcher:
        assert fetcher.fetch(job()).failure is None


# -- RefreshWorker over the real queue ---------------------------------------------


def test_executes_a_manually_submitted_job_through_the_real_queue(
    jobs: RefreshJobService,
    store: PriceStore,
    tmp_path: Path,
) -> None:
    id = jobs.submit("manual", REGION, DAY, "test-operator")
    worker = worker_for(jobs, "success", tmp_path / "success")
    try:
        worker.start()
        await_condition(lambda: job_status(jobs, id) is Status.SUCCEEDED)
        coverage = store.coverage(REGION, DAY)
        assert coverage is not None
        assert coverage.valid == 288
    finally:
        worker.stop()
    assert not worker.running


def test_restart_recovers_an_expired_claim_and_does_not_reuse_its_token(
    jobs: RefreshJobService, scratch_db: sa.Engine, tmp_path: Path
) -> None:
    id = jobs.submit("manual", REGION, DAY, "test-operator")
    abandoned = jobs.claim()
    assert abandoned is not None
    with scratch_db.begin() as conn:
        conn.execute(
            sa.text(
                "UPDATE refresh_job"
                " SET lease_until = clock_timestamp() - interval '1 second'"
                " WHERE id = :id"
            ),
            {"id": id},
        )
    restarted = worker_for(jobs, "success", tmp_path / "success")
    try:
        restarted.start()
        await_condition(lambda: job_status(jobs, id) is Status.QUEUED)
        with scratch_db.begin() as conn:
            conn.execute(
                sa.text(
                    "UPDATE refresh_job SET available_at = clock_timestamp()"
                    " WHERE id = :id"
                ),
                {"id": id},
            )
        await_condition(lambda: job_status(jobs, id) is Status.SUCCEEDED)
        assert jobs.find(id).attempts == 2  # type: ignore[union-attr]
        from nemlab_infrastructure.jobs import StaleClaimException

        with pytest.raises(StaleClaimException):
            jobs.fail(id, abandoned.claim_token, "OLD_WORKER")
    finally:
        restarted.stop()


def test_credential_failure_is_terminal_after_one_attempt(
    jobs: RefreshJobService, tmp_path: Path
) -> None:
    id = jobs.submit("manual", REGION, DAY, "test-operator")
    worker = worker_for(jobs, "unauthorised", tmp_path / "unauthorised")
    try:
        worker.start()
        await_condition(lambda: job_status(jobs, id) is Status.FAILED)
        failed = jobs.find(id)
        assert failed is not None
        assert failed.attempts == 1
        assert failed.diagnostic == "HTTP_401"
    finally:
        worker.stop()


def test_shutdown_kills_fetch_and_leaves_job_recoverable(
    jobs: RefreshJobService, store: PriceStore, tmp_path: Path
) -> None:
    id = jobs.submit("manual", REGION, DAY, "test-operator")
    worker = worker_for(jobs, "hang", tmp_path / "hang")
    try:
        worker.start()
        await_marker(tmp_path / "hang")
    finally:
        worker.stop()
    assert_child_stopped(tmp_path / "hang")
    assert jobs.find(id).status is Status.QUEUED  # type: ignore[union-attr]
    assert (
        sum(1 for attempt in store.history(REGION, DAY) if attempt.status == "COMPLETE")
        == 0
    )


def test_daily_schedule_uses_fixed_nem_time_and_deduplicates_across_restarts(
    jobs: RefreshJobService, scratch_db: sa.Engine
) -> None:
    regions = [Region.NSW1, Region.VIC1]
    before = datetime(2023, 9, 12, 14, 14, 59, tzinfo=UTC)
    after = datetime(2023, 9, 12, 14, 15, 0, tzinfo=UTC)
    schedule = RefreshSchedule(jobs, lambda: before, regions)
    schedule.submit_due()
    schedule.submit_due()
    RefreshSchedule(jobs, lambda: before, regions).submit_due()
    with scratch_db.connect() as conn:
        assert (
            conn.execute(sa.text("SELECT count(*) FROM refresh_job")).scalar_one() == 2
        )
        assert (
            conn.execute(
                sa.text("SELECT min(market_day) FROM refresh_job")
            ).scalar_one()
            == DAY
        )
    RefreshSchedule(jobs, lambda: after, regions).submit_due()
    with scratch_db.connect() as conn:
        assert (
            conn.execute(sa.text("SELECT count(*) FROM refresh_job")).scalar_one() == 4
        )
        assert conn.execute(
            sa.text("SELECT max(market_day) FROM refresh_job")
        ).scalar_one() == DAY + timedelta(days=1)


def test_packaged_worker_launches_its_fetch_child_without_live_oe(
    jobs: RefreshJobService, scratch_db: sa.Engine
) -> None:
    id = jobs.submit("packaged", REGION, DAY, "test-operator")
    # Deliberately corrupt this test job to force source validation before any
    # network call.
    with scratch_db.begin() as conn:
        conn.execute(
            sa.text(
                "UPDATE refresh_job SET market_day = DATE '2200-01-01' WHERE id = :id"
            ),
            {"id": id},
        )
    url = scratch_db.url
    env = {
        "NEMLAB_WORKER_ENABLED": "true",
        "NEMLAB_WORKER_SCHEDULE_ENABLED": "false",
        "NEMLAB_WORKER_POLL_MS": "1000",
        "NEMLAB_DB_URL": f"jdbc:postgresql://{url.host}:{url.port}/{url.database}",
        "NEMLAB_DB_USER": url.username or "",
        "NEMLAB_DB_PASSWORD": url.password or "",
        "OPEN_ELECTRICITY_API_KEY": "test-only",
    }
    process = subprocess.Popen(
        [sys.executable, "-m", "nemlab_worker"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        await_condition(lambda: job_status(jobs, id) is Status.FAILED)
        failed = jobs.find(id)
        assert failed is not None
        assert failed.diagnostic == "INVALID_SOURCE_DATA_OR_CONFIGURATION"
        assert failed.attempts == 1
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


# -- configuration -----------------------------------------------------------------


def test_enabled_run_starts_and_stops_cleanly(
    scratch_db: sa.Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = scratch_db.url
    monkeypatch.setenv(
        "NEMLAB_DB_URL",
        f"jdbc:postgresql://{url.host}:{url.port}/{url.database}",
    )
    monkeypatch.setenv("NEMLAB_DB_USER", url.username or "")
    monkeypatch.setenv("NEMLAB_DB_PASSWORD", url.password or "")
    monkeypatch.setenv("OPEN_ELECTRICITY_API_KEY", "test-only")
    settings = WorkerSettings(worker_enabled=True, worker_poll_ms=1000)
    stop = threading.Event()
    finished = threading.Event()

    def target() -> None:
        run(settings, stop)
        finished.set()

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    time.sleep(0.3)
    assert thread.is_alive()
    stop.set()
    assert finished.wait(timeout=15)


def test_invalid_configuration_fails_before_polling() -> None:
    with pytest.raises(ValidationError):
        WorkerSettings(worker_enabled=True, worker_poll_ms=0)
    with pytest.raises(ValidationError):
        WorkerSettings(worker_enabled=True, worker_poll_ms=500)
    with pytest.raises(ValidationError):
        WorkerSettings(
            worker_enabled=True,
            worker_schedule_enabled=True,
            worker_regions="BOGUS",
            open_electricity_api_key="test-only",
        )
    with pytest.raises(ValidationError):
        WorkerSettings(worker_enabled=True, open_electricity_api_key="")
    with pytest.raises(ValidationError):
        WorkerSettings(worker_enabled=True)


# -- outcome contract ----------------------------------------------------------------


def test_outcome_requires_exactly_one_result() -> None:
    with pytest.raises(ValueError):
        FetchOutcome(None, None, False)
    with pytest.raises(ValueError):
        FetchOutcome.failed("lowercase", True)


def test_fetch_command_writes_bounded_outcome(tmp_path: Path) -> None:
    output = tmp_path / "out.json"
    rc = subprocess.run(  # noqa: S603 -- fixed interpreter/module
        [
            sys.executable,
            "-m",
            "nemlab_worker",
            MODE,
            "NSW1",
            "2200-01-01",
            str(output),
        ],
        env={"OPEN_ELECTRICITY_API_KEY": "test-only"},
        capture_output=True,
        timeout=60,
    ).returncode
    assert rc == 0
    outcome = FetchOutcome.from_json(output.read_text())
    assert outcome.failure == "INVALID_SOURCE_DATA_OR_CONFIGURATION"
    assert not outcome.retryable
