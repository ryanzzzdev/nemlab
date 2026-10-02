"""NEM-056 grid import job service tests — bounded submissions, fenced
claims, per-day checkpoints, optional-series failures and lease recovery."""

import json
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
import sqlalchemy as sa
from db_fixture import apply_grid_schema

from nemlab_core.prices import NEM_OFFSET, Region
from nemlab_infrastructure.grid.batch import Metric
from nemlab_infrastructure.grid.imports import (
    DayOutcome,
    GridImportJobs,
    QueueFull,
    RequestKeyConflict,
    StaleClaimException,
)
from nemlab_infrastructure.grid.source import GridFetch, parse_market, parse_power
from nemlab_infrastructure.grid.store import GridStore

START = date(2023, 9, 4)
END = START + timedelta(days=3)
AT = datetime(2026, 9, 17, tzinfo=UTC)
REGION = Region.NSW1


@pytest.fixture
def jobs(scratch_db: sa.Engine) -> GridImportJobs:
    apply_grid_schema(scratch_db)
    return GridImportJobs(scratch_db, GridStore(scratch_db))


def _rows(day: date, value: object = 5000.0) -> list[list[object]]:
    start = datetime(day.year, day.month, day.day, tzinfo=NEM_OFFSET)
    return [[(start + timedelta(minutes=5 * i)).isoformat(), value] for i in range(288)]


def _entry(metric: str, rows: list[list[object]], fueltech: str | None = None) -> dict:
    columns = {"region": "NSW1"}
    if fueltech:
        columns["fueltech"] = fueltech
    return {
        "network_code": "NEM",
        "metric": metric,
        "interval": "5m",
        "unit": "MW",
        "results": [{"columns": columns, "data": rows}],
    }


def _market(day: date, at: datetime = AT) -> GridFetch:
    body = json.dumps(
        {
            "success": True,
            "version": "4.0",
            "data": [
                _entry(m, _rows(day))
                for m in ("demand", "flow_imports", "flow_exports")
            ],
        }
    )
    return parse_market(REGION, day, body, at)


def _power(day: date, at: datetime = AT) -> GridFetch:
    body = json.dumps(
        {
            "success": True,
            "version": "4.0",
            "data": [
                {
                    "network_code": "NEM",
                    "metric": "power",
                    "interval": "5m",
                    "unit": "MW",
                    "results": [
                        {
                            "columns": {"region": "NSW1", "fueltech": "wind"},
                            "data": _rows(day, 123.4),
                        }
                    ],
                }
            ],
        }
    )
    return parse_power(REGION, day, body, at)


def _day(jobs: GridImportJobs, id, day: date, power_failure: str | None = None):
    outcome = DayOutcome(
        day,
        _market(day),
        None if power_failure else _power(day),
        power_failure,
    )
    return jobs.complete_day(id, _claim_token(jobs, id), outcome)


def _claim_token(jobs: GridImportJobs, id):
    job = jobs.find(id)
    return job.claim_token if job else None


# -- submissions ----------------------------------------------------------------


def test_submit_dedupes_key_and_window(jobs: GridImportJobs) -> None:
    id = jobs.submit("key-1", REGION, START, END, "operator:test")
    assert jobs.submit("key-1", REGION, START, END, "operator:test") == id
    # Different key, same active window -> deduplicated onto the same job.
    assert jobs.submit("key-2", REGION, START, END, "operator:test") == id
    with jobs.engine.connect() as conn:
        count = conn.execute(
            sa.text("SELECT count(*) FROM grid_import_job")
        ).scalar_one()
    assert count == 1
    events = [e.action for e in jobs.events(id, 0, 50)]
    assert events == ["SUBMITTED", "DUPLICATE_REQUEST", "DEDUPLICATED"]


def test_submit_key_conflict(jobs: GridImportJobs) -> None:
    jobs.submit("key-1", REGION, START, END, "operator:test")
    with pytest.raises(RequestKeyConflict):
        jobs.submit("key-1", REGION, START + timedelta(days=1), END, "op")


def test_submit_bounds(jobs: GridImportJobs) -> None:
    with pytest.raises(ValueError, match=r"1\.\.31"):
        jobs.submit("a", REGION, START, START, "op")
    with pytest.raises(ValueError, match=r"1\.\.31"):
        jobs.submit("b", REGION, START, START + timedelta(days=32), "op")
    with pytest.raises(ValueError, match=r"1\.\.31"):
        jobs.submit("c", REGION, START, date(2100, 1, 1), "op")  # future end
    jobs.submit("d", REGION, START, START + timedelta(days=31), "op")


def test_queue_capacity(jobs: GridImportJobs) -> None:
    for i in range(20):
        jobs.submit(
            f"fill-{i}",
            REGION,
            START + timedelta(days=40 * i),
            START + timedelta(days=40 * i) + timedelta(days=1),
            "test",
        )
    with pytest.raises(QueueFull):
        jobs.submit("overflow", REGION, START, END, "op")


# -- claim / completion ----------------------------------------------------------


def test_claim_commits_days_and_succeeds(jobs: GridImportJobs) -> None:
    id = jobs.submit("key", REGION, START, END, "op")
    job = jobs.claim()
    assert job is not None and job.id == id and job.claim_token is not None
    assert jobs.claim() is None  # one running import globally
    assert _day(jobs, id, START) is False
    assert _day(jobs, id, START + timedelta(days=1)) is False
    assert _day(jobs, id, START + timedelta(days=2)) is True  # SUCCEEDED
    found = jobs.find(id)
    assert found is not None and found.status.name == "SUCCEEDED"
    # All three days x market series + power persisted.
    assert jobs.grid.batch(REGION, Metric.DEMAND, "", START) is not None
    assert (
        jobs.grid.batch(REGION, Metric.POWER, "wind", START + timedelta(days=2))
        is not None
    )


def test_wrong_day_rejected(jobs: GridImportJobs) -> None:
    id = jobs.submit("key", REGION, START, END, "op")
    jobs.claim()
    with pytest.raises(ValueError, match="checkpoint"):
        _day(jobs, id, START + timedelta(days=1))


def test_stale_claim_rejected(jobs: GridImportJobs) -> None:
    id = jobs.submit("key", REGION, START, END, "op")
    jobs.claim()
    with pytest.raises(StaleClaimException):
        jobs.complete_day(id, uuid4(), DayOutcome(START, _market(START), _power(START)))
    with pytest.raises(StaleClaimException):
        jobs.fail(id, uuid4(), "TRANSPORT_RETRIES_EXHAUSTED")


def test_optional_power_failure_still_advances(jobs: GridImportJobs) -> None:
    id = jobs.submit("key", REGION, START, END, "op")
    jobs.claim()
    _day(jobs, id, START, power_failure="HTTP_503")
    job = jobs.find(id)
    assert job is not None and job.optional_failures == 1
    assert job.next_day == START + timedelta(days=1)
    # Market data committed; a FAILED power attempt row records the optional
    # failure distinctly from a core-data failure.
    assert jobs.grid.batch(REGION, Metric.DEMAND, "", START) is not None
    assert jobs.grid.batch(REGION, Metric.POWER, "wind", START) is None
    failed = [a for a in jobs.grid.history(REGION, START) if a.status == "FAILED"]
    assert failed and failed[0].diagnostic == "HTTP_503"
    assert list(failed[0].metrics) == ["power"]


def test_retryable_failure_requeues_at_checkpoint(jobs: GridImportJobs) -> None:
    id = jobs.submit("key", REGION, START, END, "op")
    job = jobs.claim()
    _day(jobs, id, START)
    assert job is not None
    jobs.fail(id, job.claim_token, "TRANSPORT_RETRIES_EXHAUSTED")
    found = jobs.find(id)
    assert found is not None
    assert found.status.name == "QUEUED" and found.next_day == START + timedelta(days=1)


def test_permanent_failure_keeps_checkpoint(jobs: GridImportJobs) -> None:
    id = jobs.submit("key", REGION, START, END, "op")
    job = jobs.claim()
    _day(jobs, id, START)
    assert job is not None
    jobs.fail_permanently(id, job.claim_token, "HTTP_401")
    found = jobs.find(id)
    assert found is not None
    assert found.status.name == "FAILED" and found.next_day == START + timedelta(days=1)


def test_lease_expiry_recovers_to_queued(jobs: GridImportJobs) -> None:
    id = jobs.submit("key", REGION, START, END, "op")
    job = jobs.claim()
    assert job is not None
    with jobs.engine.begin() as conn:
        conn.execute(
            sa.text(
                "UPDATE grid_import_job SET lease_until = clock_timestamp()"
                " - interval '1 second' WHERE id = :id"
            ),
            {"id": id},
        )
    # Recovery requeues with backoff; jump the delay then reclaim.
    assert jobs.claim() is None
    with jobs.engine.begin() as conn:
        conn.execute(
            sa.text(
                "UPDATE grid_import_job SET available_at = clock_timestamp()"
                " - interval '1 second' WHERE id = :id"
            ),
            {"id": id},
        )
    recovered = jobs.claim()
    assert recovered is not None and recovered.id == id
    assert recovered.claim_token != job.claim_token
    actions = [e.action for e in jobs.events(id, 0, 50)]
    assert "RETRY_SCHEDULED" in actions and actions[-1] == "CLAIMED"


def test_attempt_exhaustion_fails(jobs: GridImportJobs) -> None:
    id = jobs.submit("key", REGION, START, END, "op")
    for _ in range(3):
        job = jobs.claim()
        assert job is not None
        jobs.fail(id, job.claim_token, "TRANSPORT_RETRIES_EXHAUSTED")
        with jobs.engine.begin() as conn:
            conn.execute(
                sa.text(
                    "UPDATE grid_import_job SET available_at = clock_timestamp()"
                    " - interval '1 second' WHERE id = :id"
                ),
                {"id": id},
            )
    found = jobs.find(id)
    assert found is not None and found.status.name == "FAILED"


def test_cancel_running_revokes_claim(jobs: GridImportJobs) -> None:
    id = jobs.submit("key", REGION, START, END, "op")
    job = jobs.claim()
    assert jobs.cancel(id, "operator:alice") is True
    assert jobs.cancel(id, "operator:alice") is False  # no-op, audited
    with pytest.raises(StaleClaimException):
        jobs.complete_day(
            id,
            job.claim_token if job else None,
            DayOutcome(START, _market(START), _power(START)),
        )
    found = jobs.find(id)
    assert found is not None and found.status.name == "CANCELLED"


def test_events_cursor(jobs: GridImportJobs) -> None:
    id = jobs.submit("key", REGION, START, END, "op")
    jobs.claim()
    events = jobs.events(id, 0, 50)
    assert [e.action for e in events] == ["SUBMITTED", "CLAIMED"]
    assert jobs.events(id, events[-1].id, 50) == []
    with pytest.raises(ValueError):
        jobs.events(id, -1, 50)
    with pytest.raises(ValueError):
        jobs.events(id, 0, 0)


def test_day_outcome_rejects_mismatched_fetch_day(jobs: GridImportJobs) -> None:
    """Contract: a fetch for another day can never be committed under this
    day's checkpoint — construction rejects it before any write."""
    with pytest.raises(ValueError, match="fetch day"):
        DayOutcome(START, _market(START), _power(START + timedelta(days=1)))
    jobs.submit("key", REGION, START, END, "op")
