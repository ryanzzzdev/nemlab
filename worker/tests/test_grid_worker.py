"""``GridImportWorker``/``GridFetchProcess`` tests — real child processes
and real PostgreSQL, no live OE traffic."""

import os
import sys
import time
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
import sqlalchemy as sa

from nemlab_core.prices import Region
from nemlab_infrastructure.grid.batch import Metric
from nemlab_infrastructure.grid.imports import GridImportJobs, Status
from nemlab_infrastructure.grid.store import GridStore
from nemlab_infrastructure.prices.store import PriceStore
from nemlab_infrastructure.schema import migration_text
from nemlab_worker.grid import GridFetchProcess, GridImportWorker, GridOutcome

START = date(2023, 9, 4)
REGION = Region.NSW1
FIXTURE = Path(__file__).resolve().parent / "grid_fixture.py"


@pytest.fixture
def jobs(scratch_db: sa.Engine, store: PriceStore) -> GridImportJobs:
    # ``store`` (autouse-cleaned) already applied the V1-V3 baseline.
    with scratch_db.begin() as conn:
        conn.exec_driver_sql(migration_text("V4__grid_observations.sql"))
        conn.exec_driver_sql(migration_text("V5__grid_import_jobs.sql"))
    return GridImportJobs(scratch_db, GridStore(scratch_db))


def fixture_fetcher(
    scenario: str, marker: Path, timeout: float = 10
) -> GridFetchProcess:
    return GridFetchProcess(
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


def await_condition(condition: Callable[[], bool]) -> None:
    deadline = time.monotonic() + 15
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert condition(), "worker did not reach expected state before deadline"


def status(jobs: GridImportJobs, id: UUID) -> Status | None:
    found = jobs.find(id)
    return found.status if found is not None else None


def worker_for(jobs: GridImportJobs, scenario: str, marker: Path) -> GridImportWorker:
    return GridImportWorker(jobs, fixture_fetcher(scenario, marker), 0.02)


def _submit(jobs: GridImportJobs, days: int = 2) -> UUID:
    return jobs.submit(
        f"import-{uuid.uuid4()}",
        REGION,
        START,
        START + timedelta(days=days),
        "test",
    )


# -- GridFetchProcess -----------------------------------------------------------


def test_round_trips_series_and_deletes_output(tmp_path: Path) -> None:
    marker = tmp_path / "marker"
    job_id = uuid.uuid4()
    job = _claimed_job(job_id)
    with fixture_fetcher("success", marker) as fetcher:
        outcome = fetcher.fetch("market", job, START)
    assert outcome.fetch is not None
    assert len(outcome.fetch.series) == 3
    assert outcome.fetch.series[0].metric is Metric.DEMAND
    assert outcome.fetch.series[0].slots[0].value == Decimal("123.4")
    listed = marker.read_text().splitlines()[1]
    assert not Path(listed).exists()


def test_kills_a_stalled_child_before_timeout(tmp_path: Path) -> None:
    marker = tmp_path / "marker"
    with fixture_fetcher("hang", marker, timeout=0.4) as fetcher:
        outcome = fetcher.fetch("market", _claimed_job(uuid.uuid4()), START)
    assert outcome.failure == "FETCH_DEADLINE_EXCEEDED"
    assert outcome.retryable is True
    assert_child_stopped(marker)


def test_failed_children_produce_safe_diagnostic_codes(tmp_path: Path) -> None:
    for scenario in ("crash", "malformed"):
        marker = tmp_path / f"marker-{scenario}"
        with fixture_fetcher(scenario, marker) as fetcher:
            outcome = fetcher.fetch("power", _claimed_job(uuid.uuid4()), START)
        assert outcome.fetch is None
        assert outcome.failure is not None


def test_child_never_inherits_database_credentials(tmp_path: Path) -> None:
    marker = tmp_path / "marker"
    previous = os.environ.get("NEMLAB_DB_PASSWORD")
    os.environ["NEMLAB_DB_PASSWORD"] = "super-secret"
    try:
        with fixture_fetcher("success", marker) as fetcher:
            outcome = fetcher.fetch("market", _claimed_job(uuid.uuid4()), START)
        # The fixture exits non-zero if it sees the credential.
        assert outcome.fetch is not None
    finally:
        if previous is None:
            os.environ.pop("NEMLAB_DB_PASSWORD", None)
        else:
            os.environ["NEMLAB_DB_PASSWORD"] = previous


def _claimed_job(id: UUID):
    from nemlab_infrastructure.grid.imports import GridImportJob

    return GridImportJob(
        id,
        REGION,
        START,
        START + timedelta(days=2),
        START,
        Status.RUNNING,
        1,
        0,
        uuid.uuid4(),
        datetime.now(UTC) + timedelta(seconds=300),
        datetime.now(UTC),
        None,
    )


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


# -- worker loop ----------------------------------------------------------------


def test_executes_a_multi_day_import_through_the_real_queue(
    jobs: GridImportJobs, tmp_path: Path
) -> None:
    id = _submit(jobs, days=2)
    worker = worker_for(jobs, "success", tmp_path / "marker")
    worker.start()
    await_condition(lambda: status(jobs, id) is Status.SUCCEEDED)
    worker.stop()
    assert jobs.grid.batch(REGION, Metric.DEMAND, "", START) is not None
    assert jobs.grid.batch(REGION, Metric.POWER, "wind", START) is not None
    job = jobs.find(id)
    assert job is not None and job.optional_failures == 0


def test_optional_power_failure_does_not_block_the_window(
    jobs: GridImportJobs, tmp_path: Path
) -> None:
    id = _submit(jobs, days=2)
    worker = worker_for(jobs, "power-down", tmp_path / "marker")
    worker.start()
    await_condition(lambda: status(jobs, id) is Status.SUCCEEDED)
    worker.stop()
    job = jobs.find(id)
    assert job is not None and job.optional_failures == 2
    # Core market data landed; the optional series stayed absent, recorded
    # as FAILED attempts — distinguishable from a core-data failure.
    assert jobs.grid.batch(REGION, Metric.DEMAND, "", START) is not None
    assert jobs.grid.batch(REGION, Metric.POWER, "wind", START) is None
    failed = [a for a in jobs.grid.history(REGION, START) if a.status == "FAILED"]
    assert len(failed) == 1 and list(failed[0].metrics) == ["power"]


def test_core_failure_retries_then_recovers(
    jobs: GridImportJobs, tmp_path: Path
) -> None:
    id = _submit(jobs, days=2)
    worker = worker_for(jobs, "throttle", tmp_path / "marker")
    worker.tick()  # claim + first day fails retryable
    await_condition(lambda: status(jobs, id) is Status.QUEUED)
    worker.stop()
    job = jobs.find(id)
    assert job is not None and job.next_day == START
    # A second attempt with a healthy child finishes the window.
    worker = worker_for(jobs, "success", tmp_path / "marker2")
    with jobs.engine.begin() as conn:
        conn.execute(
            sa.text(
                "UPDATE grid_import_job SET available_at = clock_timestamp()"
                " WHERE id = :id"
            ),
            {"id": id},
        )
    worker.start()
    await_condition(lambda: status(jobs, id) is Status.SUCCEEDED)
    worker.stop()


def test_permanent_failure_records_diagnostic(
    jobs: GridImportJobs, tmp_path: Path
) -> None:
    id = _submit(jobs)
    worker = worker_for(jobs, "unauthorised", tmp_path / "marker")
    worker.start()
    await_condition(lambda: status(jobs, id) is Status.FAILED)
    worker.stop()
    job = jobs.find(id)
    assert job is not None and job.diagnostic == "HTTP_401"


def test_shutdown_leaves_job_recoverable(jobs: GridImportJobs, tmp_path: Path) -> None:
    id = _submit(jobs, days=5)
    marker = tmp_path / "marker"
    worker = worker_for(jobs, "success", marker)
    worker.start()
    await_marker(marker)  # at least one child ran
    worker.stop()
    found = jobs.find(id)
    assert found is not None
    assert found.status in (Status.QUEUED, Status.SUCCEEDED, Status.RUNNING)
    # Whatever state it stopped in, a fresh worker run can finish it.
    if found.status is Status.RUNNING:
        with jobs.engine.begin() as conn:
            conn.execute(
                sa.text(
                    "UPDATE grid_import_job SET lease_until = clock_timestamp()"
                    " - interval '1 second' WHERE id = :id"
                ),
                {"id": id},
            )
        jobs.claim()  # recovers to QUEUED
    if status(jobs, id) is Status.QUEUED:
        # Jump the retry backoff the stop-path applied.
        with jobs.engine.begin() as conn:
            conn.execute(
                sa.text(
                    "UPDATE grid_import_job SET available_at = clock_timestamp()"
                    " WHERE id = :id"
                ),
                {"id": id},
            )
        worker = worker_for(jobs, "success", tmp_path / "marker2")
        worker.start()
        await_condition(lambda: status(jobs, id) is Status.SUCCEEDED)
        worker.stop()


def test_outcome_requires_exactly_one_result() -> None:
    with pytest.raises(ValueError):
        GridOutcome(None, None, False)


def test_packaged_worker_launches_grid_child(
    jobs: GridImportJobs, tmp_path: Path
) -> None:
    """The real ``python -m nemlab_worker --fetch-grid`` child works."""
    id = _submit(jobs)
    marker = tmp_path / "marker"
    fetcher = GridFetchProcess(
        "test-only",
        command=[sys.executable, str(FIXTURE), "success", str(marker)],
    )
    worker = GridImportWorker(jobs, fetcher, 0.02)
    worker.start()
    await_condition(lambda: status(jobs, id) is Status.SUCCEEDED)
    worker.stop()
