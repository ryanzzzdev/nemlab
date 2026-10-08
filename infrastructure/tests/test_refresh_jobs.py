"""RefreshJobService tests ported from ``RefreshJobServiceTest`` — real
PostgreSQL concurrency, claim fencing, lease recovery, atomic rollbacks."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
import sqlalchemy as sa
from db_fixture import apply_schema

from nemlab_core.prices import Region
from nemlab_infrastructure import jobs as jobs_module
from nemlab_infrastructure.jobs import (
    MAX_VISITOR_PENDING,
    RefreshJobService,
    StaleClaimException,
    Status,
)
from nemlab_infrastructure.prices.batch import Kind, PriceBatch, Slot
from nemlab_infrastructure.prices.batch import hash as batch_hash
from nemlab_infrastructure.prices.source import Fetch
from nemlab_infrastructure.prices.store import PriceStore

DAY = date(2023, 9, 11)
REGION = Region.NSW1

TRUNCATE = (
    "TRUNCATE simulation_result, simulation_job, simulation_input,"
    " refresh_job_event, refresh_request, refresh_job,"
    " price_snapshot, price_current, price_import_attempt,"
    " price_revision, price_backfill"
)


@pytest.fixture
def store(scratch_db: sa.Engine) -> PriceStore:
    apply_schema(scratch_db)
    return PriceStore(scratch_db)


@pytest.fixture
def jobs(scratch_db: sa.Engine, store: PriceStore) -> RefreshJobService:
    return RefreshJobService(scratch_db, store)


@pytest.fixture(autouse=True)
def clean(store: PriceStore, scratch_db: sa.Engine) -> None:
    with scratch_db.begin() as conn:
        conn.execute(sa.text(TRUNCATE))


def sample(incomplete: bool) -> Fetch:
    slots = [Slot(Kind.VALUE, Decimal("42.5"))] * 288
    if incomplete:
        slots[0] = Slot(Kind.MISSING, None)
    return Fetch(
        PriceBatch(REGION, DAY, tuple(slots)),
        datetime.now(UTC),
        batch_hash(f"fixture-{incomplete}"),
        "test-1",
    )


def count(engine: sa.Engine, table: str) -> int:
    with engine.connect() as conn:
        return conn.execute(
            sa.text(f"SELECT count(*) FROM {table}")  # noqa: S608 -- literals only
        ).scalar_one()


def make_ready(engine: sa.Engine, id: UUID) -> None:
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "UPDATE refresh_job SET available_at = clock_timestamp() WHERE id = :id"
            ),
            {"id": id},
        )


def test_deduplicates_concurrent_submissions_and_retains_aliases(
    jobs: RefreshJobService, store: PriceStore, scratch_db: sa.Engine
) -> None:
    with ThreadPoolExecutor(4) as executor:
        results = list(
            executor.map(
                lambda i: jobs.submit(f"request-{i}", REGION, DAY, "operator"),
                range(4),
            )
        )
    assert len(set(results)) == 1
    id = results[0]
    assert count(scratch_db, "refresh_job") == 1
    assert count(scratch_db, "price_backfill") == 1
    claim = jobs.claim()
    assert claim is not None
    jobs.complete(id, claim.claim_token, sample(False))
    assert jobs.submit("request-3", REGION, DAY, "operator") == id
    assert jobs.submit("new-refresh", REGION, DAY, "operator") != id
    with pytest.raises(ValueError):
        jobs.submit("request-3", REGION, DAY + timedelta(days=1), "operator")


def test_request_key_conflict_is_typed(
    jobs: RefreshJobService,
) -> None:
    jobs.submit("key", REGION, DAY, "operator")
    with pytest.raises(jobs_module.RequestKeyConflict):
        jobs.submit("key", Region.QLD1, DAY, "operator")


def test_only_one_worker_claims_even_when_multiple_days_queued(
    jobs: RefreshJobService,
) -> None:
    jobs.submit("day-1", REGION, DAY, "scheduler")
    jobs.submit("day-2", REGION, DAY + timedelta(days=1), "scheduler")
    with ThreadPoolExecutor(4) as executor:
        claimed = sum(executor.map(lambda _: jobs.claim() is not None, range(4)))
    assert claimed == 1


def test_expired_claim_cannot_write_and_replacement_has_new_token(
    jobs: RefreshJobService, store: PriceStore, scratch_db: sa.Engine
) -> None:
    id = jobs.submit("refresh", REGION, DAY, "operator")
    old_claim = jobs.claim()
    assert old_claim is not None
    with scratch_db.begin() as conn:
        conn.execute(
            sa.text(
                "UPDATE refresh_job"
                " SET lease_until = clock_timestamp() - interval '1 second'"
                " WHERE id = :id"
            ),
            {"id": id},
        )
    with pytest.raises(StaleClaimException):
        jobs.complete(id, old_claim.claim_token, sample(False))
    assert jobs.claim() is None
    found = jobs.find(id)
    assert found is not None
    assert found.diagnostic == "LEASE_EXPIRED"
    make_ready(scratch_db, id)
    replacement = jobs.claim()
    assert replacement is not None
    assert replacement.claim_token != old_claim.claim_token
    with pytest.raises(StaleClaimException):
        jobs.fail(id, old_claim.claim_token, "TRANSPORT_FAILURE")
    assert count(scratch_db, "price_import_attempt") == 0
    jobs.complete(id, replacement.claim_token, sample(False))
    succeeded = jobs.find(id)
    assert succeeded is not None
    assert succeeded.status is Status.SUCCEEDED
    assert store.backfill(replacement.backfill_id).status == "COMPLETE"


def test_exhausted_retries_fail_with_diagnostics_and_do_not_claim_again(
    jobs: RefreshJobService, store: PriceStore, scratch_db: sa.Engine
) -> None:
    id = jobs.submit("refresh", REGION, DAY, "operator")
    for attempt in range(1, 4):
        claim = jobs.claim()
        assert claim is not None
        assert claim.attempts == attempt
        jobs.fail(id, claim.claim_token, "HTTP_503")
        assert jobs.claim() is None
        make_ready(scratch_db, id)
    failed = jobs.find(id)
    assert failed is not None
    assert failed.status is Status.FAILED
    assert failed.diagnostic == "HTTP_503"
    assert len(store.history(REGION, DAY)) == 3
    assert jobs.claim() is None


def test_final_expired_attempt_fails_without_unbounded_crash_loop(
    jobs: RefreshJobService, scratch_db: sa.Engine
) -> None:
    id = jobs.submit("refresh", REGION, DAY, "operator")
    for _ in range(3):
        assert jobs.claim() is not None
        with scratch_db.begin() as conn:
            conn.execute(
                sa.text(
                    "UPDATE refresh_job"
                    " SET lease_until = clock_timestamp() - interval '1 second'"
                    " WHERE id = :id"
                ),
                {"id": id},
            )
        assert jobs.claim() is None
        make_ready(scratch_db, id)
    failed = jobs.find(id)
    assert failed is not None
    assert failed.status is Status.FAILED
    assert jobs.claim() is None


def test_cancellation_revokes_claim_and_records_actor(
    jobs: RefreshJobService, scratch_db: sa.Engine
) -> None:
    id = jobs.submit("refresh", REGION, DAY, "operator-alice")
    claim = jobs.claim()
    assert claim is not None
    assert jobs.cancel(id, "operator-bob") is True
    assert jobs.cancel(id, "operator-bob") is False
    with pytest.raises(StaleClaimException):
        jobs.complete(id, claim.claim_token, sample(False))
    assert count(scratch_db, "price_revision") == 0
    with scratch_db.connect() as conn:
        actor = conn.execute(
            sa.text(
                "SELECT actor FROM refresh_job_event"
                " WHERE job_id = :id AND action = 'CANCELLED'"
            ),
            {"id": id},
        ).scalar_one()
    assert actor == "operator-bob"


def test_failed_job_transition_rolls_back_price_and_checkpoint_writes(
    jobs: RefreshJobService, store: PriceStore, scratch_db: sa.Engine
) -> None:
    id = jobs.submit("refresh", REGION, DAY, "operator")
    claim = jobs.claim()
    assert claim is not None
    with scratch_db.begin() as conn:
        conn.exec_driver_sql(
            "CREATE FUNCTION reject_job_success() RETURNS trigger"
            " LANGUAGE plpgsql AS $$"
            " BEGIN"
            "   IF NEW.status = 'SUCCEEDED' THEN"
            "     RAISE EXCEPTION 'injected completion failure';"
            "   END IF;"
            "   RETURN NEW;"
            " END; $$"
        )
        conn.exec_driver_sql(
            "CREATE TRIGGER reject_job_success BEFORE UPDATE ON refresh_job"
            " FOR EACH ROW EXECUTE FUNCTION reject_job_success()"
        )
    try:
        with pytest.raises(Exception):  # noqa: B017 -- injected SQL failure
            jobs.complete(id, claim.claim_token, sample(False))
        assert count(scratch_db, "price_revision") == 0
        assert count(scratch_db, "price_import_attempt") == 0
        assert store.backfill(claim.backfill_id).next == DAY
        running = jobs.find(id)
        assert running is not None
        assert running.status is Status.RUNNING
    finally:
        with scratch_db.begin() as conn:
            conn.exec_driver_sql("DROP TRIGGER reject_job_success ON refresh_job")
            conn.exec_driver_sql("DROP FUNCTION reject_job_success()")
    jobs.complete(id, claim.claim_token, sample(False))
    assert count(scratch_db, "price_revision") == 1


@pytest.mark.parametrize("incomplete", [False, True])
def test_lease_expiry_during_price_writes_rolls_back(
    incomplete: bool,
    jobs: RefreshJobService,
    store: PriceStore,
    scratch_db: sa.Engine,
) -> None:
    id = jobs.submit("refresh", REGION, DAY, "operator")
    claim = jobs.claim()
    assert claim is not None
    with scratch_db.begin() as conn:
        conn.exec_driver_sql(
            "CREATE FUNCTION expire_job_during_write() RETURNS trigger"
            " LANGUAGE plpgsql AS $$"
            " BEGIN"
            "   UPDATE refresh_job"
            "   SET lease_until = clock_timestamp() - interval '1 second'"
            "   WHERE status = 'RUNNING';"
            "   RETURN NEW;"
            " END; $$"
        )
        conn.exec_driver_sql(
            "CREATE TRIGGER expire_job_during_write"
            " BEFORE INSERT ON price_import_attempt"
            " FOR EACH ROW EXECUTE FUNCTION expire_job_during_write()"
        )
    try:
        with pytest.raises(StaleClaimException):
            jobs.complete(id, claim.claim_token, sample(incomplete))
        assert count(scratch_db, "price_revision") == 0
        assert count(scratch_db, "price_import_attempt") == 0
        assert store.backfill(claim.backfill_id).next == DAY
        running = jobs.find(id)
        assert running is not None
        assert running.status is Status.RUNNING
    finally:
        with scratch_db.begin() as conn:
            conn.exec_driver_sql(
                "DROP TRIGGER expire_job_during_write ON price_import_attempt"
            )
            conn.exec_driver_sql("DROP FUNCTION expire_job_during_write()")


def test_incomplete_day_visible_but_never_successful(
    jobs: RefreshJobService, store: PriceStore, scratch_db: sa.Engine
) -> None:
    id = jobs.submit("refresh", REGION, DAY, "operator")
    claim = jobs.claim()
    assert claim is not None
    jobs.complete(id, claim.claim_token, sample(True))
    job = jobs.find(id)
    assert job is not None
    assert job.status is Status.QUEUED
    assert job.diagnostic == "INCOMPLETE_PRICE_DAY"
    coverage = store.coverage(REGION, DAY)
    assert coverage is not None
    assert coverage.valid == 287
    assert store.backfill(claim.backfill_id).next == DAY
    make_ready(scratch_db, id)
    retry = jobs.claim()
    assert retry is not None
    jobs.complete(id, retry.claim_token, sample(False))
    assert jobs.find(id).status is Status.SUCCEEDED  # type: ignore[union-attr]


def test_validates_inputs_and_bounds_queue_size(
    jobs: RefreshJobService, scratch_db: sa.Engine
) -> None:
    with pytest.raises(ValueError):
        jobs.submit("bad key", REGION, DAY, "operator")
    with pytest.raises(ValueError):
        jobs.submit("future", REGION, date(2200, 1, 1), "operator")
    for index in range(jobs_module.MAX_PENDING_JOBS):
        jobs.submit(f"day-{index}", REGION, DAY + timedelta(days=index), "scheduler")
    with pytest.raises(jobs_module.QueueFull):
        jobs.submit(
            "overflow",
            REGION,
            DAY + timedelta(days=jobs_module.MAX_PENDING_JOBS),
            "scheduler",
        )
    assert count(scratch_db, "refresh_job") == jobs_module.MAX_PENDING_JOBS
    assert count(scratch_db, "price_backfill") == jobs_module.MAX_PENDING_JOBS


def test_visitor_requests_deduplicate_onto_any_active_job_for_the_day(
    jobs: RefreshJobService, scratch_db: sa.Engine
) -> None:
    scheduled = jobs.submit(
        f"daily-price-v1:{REGION.name}:{DAY}", REGION, DAY, "scheduler"
    )
    assert jobs.submit_visitor(REGION, DAY) == scheduled
    assert jobs.submit_visitor(REGION, DAY) == scheduled
    assert count(scratch_db, "refresh_job") == 1
    assert count(scratch_db, "refresh_request") == 2


def test_visitor_requests_retry_terminal_jobs_then_exhaust(
    jobs: RefreshJobService, scratch_db: sa.Engine
) -> None:
    first = jobs.submit_visitor(REGION, DAY)
    first_claim = jobs.claim()
    assert first_claim is not None
    jobs.complete(first, first_claim.claim_token, sample(False))
    assert jobs.find(first).status is Status.SUCCEEDED  # type: ignore[union-attr]
    # A later request for a day whose coverage vanished starts a fresh job
    # under a new key.
    with scratch_db.begin() as conn:
        conn.execute(sa.text("DELETE FROM price_current"))
    second = jobs.submit_visitor(REGION, DAY)
    assert second != first
    second_claim = jobs.claim()
    assert second_claim is not None
    jobs.fail_permanently(second, second_claim.claim_token, "HTTP_401")
    third = jobs.submit_visitor(REGION, DAY)
    assert third != second
    third_claim = jobs.claim()
    assert third_claim is not None
    jobs.fail_permanently(third, third_claim.claim_token, "HTTP_401")
    with pytest.raises(jobs_module.RefreshAttemptsExhausted):
        jobs.submit_visitor(REGION, DAY)
    assert count(scratch_db, "refresh_job") == 3


def test_visitor_pending_cap_is_separate_from_shared_queue(
    jobs: RefreshJobService, scratch_db: sa.Engine
) -> None:
    for index in range(MAX_VISITOR_PENDING):
        jobs.submit_visitor(REGION, DAY + timedelta(days=index))
    with pytest.raises(jobs_module.VisitorLimited):
        jobs.submit_visitor(REGION, DAY + timedelta(days=MAX_VISITOR_PENDING))
    assert count(scratch_db, "refresh_job") == MAX_VISITOR_PENDING
    # Operator and scheduler submissions still share the wider bound.
    operator = jobs.submit(
        "operator-day",
        REGION,
        DAY + timedelta(days=MAX_VISITOR_PENDING + 1),
        "operator-alice",
    )
    assert operator is not None
    assert count(scratch_db, "refresh_job") == MAX_VISITOR_PENDING + 1


def test_preexisting_job_and_audit_rows_remain_readable(
    jobs: RefreshJobService, store: PriceStore, scratch_db: sa.Engine
) -> None:
    """Rows written by the Java service on the adopted schema decode through
    the Python service unchanged."""
    job_id = UUID("00000000-0000-4000-8000-0000000000ee")
    backfill_id = store.create_backfill(REGION, DAY, DAY + timedelta(days=1))
    with scratch_db.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO refresh_job"
                " (id, backfill_id, region, market_day, status, attempts,"
                "  diagnostic)"
                " VALUES (:id, :bf, 'NSW1', :day, 'SUCCEEDED', 1,"
                "         'LEGACY_DIAGNOSTIC')"
            ),
            {"id": job_id, "bf": backfill_id, "day": DAY},
        )
        conn.execute(
            sa.text(
                "INSERT INTO refresh_request(request_key, job_id)"
                " VALUES ('java-scheduler:v1', :job)"
            ),
            {"job": job_id},
        )
        conn.execute(
            sa.text(
                "INSERT INTO refresh_job_event(job_id, actor, action, diagnostic)"
                " VALUES (:job, 'operator-jane', 'SUCCEEDED', 'LEGACY_DIAGNOSTIC')"
            ),
            {"job": job_id},
        )
    found = jobs.find(job_id)
    assert found is not None
    assert found.status is Status.SUCCEEDED
    assert found.attempts == 1
    assert found.diagnostic == "LEGACY_DIAGNOSTIC"
    assert found.claim_token is None and found.lease_until is None
    events = jobs.events(job_id, 0, 10)
    assert [(e.actor, e.action, e.diagnostic) for e in events] == [
        ("operator-jane", "SUCCEEDED", "LEGACY_DIAGNOSTIC")
    ]
    recent = jobs.recent(10)
    assert [j.id for j in recent] == [job_id]


def test_submit_window_creates_one_job_per_day_and_replays(
    jobs: RefreshJobService, scratch_db: sa.Engine
) -> None:
    end = DAY + timedelta(days=5)
    ids = jobs.submit_window("month-nsw1", REGION, DAY, end, "operator")
    assert len(ids) == 5
    assert len(set(ids)) == 5
    assert jobs.find(ids[0]).day == DAY  # type: ignore[union-attr]
    assert jobs.find(ids[4]).day == end - timedelta(days=1)  # type: ignore[union-attr]
    assert count(scratch_db, "refresh_job") == 5
    # 5 derived keys + 1 window marker
    assert count(scratch_db, "refresh_request") == 6
    # Identical resubmission returns the same jobs — nothing new.
    assert jobs.submit_window("month-nsw1", REGION, DAY, end, "operator") == ids
    assert count(scratch_db, "refresh_job") == 5


def test_submit_window_rejects_different_window_under_same_key(
    jobs: RefreshJobService, scratch_db: sa.Engine
) -> None:
    jobs.submit_window("month-nsw1", REGION, DAY, DAY + timedelta(days=5), "op")
    # Same start, wider window.
    with pytest.raises(jobs_module.RequestKeyConflict):
        jobs.submit_window("month-nsw1", REGION, DAY, DAY + timedelta(days=7), "op")
    # Same window, different region.
    with pytest.raises(jobs_module.RequestKeyConflict):
        jobs.submit_window(
            "month-nsw1", Region.QLD1, DAY, DAY + timedelta(days=5), "op"
        )
    # Shifted window.
    with pytest.raises(jobs_module.RequestKeyConflict):
        jobs.submit_window(
            "month-nsw1", REGION, DAY + timedelta(days=1), DAY + timedelta(days=6), "op"
        )
    assert count(scratch_db, "refresh_job") == 5


def test_submit_window_deduplicates_onto_active_day_jobs(
    jobs: RefreshJobService, scratch_db: sa.Engine
) -> None:
    existing = jobs.submit("single", REGION, DAY + timedelta(days=2), "operator")
    ids = jobs.submit_window("month", REGION, DAY, DAY + timedelta(days=4), "op")
    assert ids[2] == existing
    assert count(scratch_db, "refresh_job") == 4


def test_submit_window_validates_bounds(
    jobs: RefreshJobService, scratch_db: sa.Engine
) -> None:
    with pytest.raises(ValueError):
        jobs.submit_window("empty", REGION, DAY, DAY, "op")
    with pytest.raises(ValueError):
        jobs.submit_window("reversed", REGION, DAY, DAY - timedelta(days=1), "op")
    with pytest.raises(ValueError):
        jobs.submit_window("long", REGION, DAY, DAY + timedelta(days=32), "op")
    with pytest.raises(ValueError):
        jobs.submit_window("early", REGION, date(2021, 9, 28), date(2021, 10, 3), "op")
    today = datetime.now(UTC).astimezone().date()
    with pytest.raises(ValueError):
        jobs.submit_window("future", REGION, today, today + timedelta(days=2), "op")
    assert count(scratch_db, "refresh_job") == 0
    assert count(scratch_db, "refresh_request") == 0


def test_submit_window_rolls_back_when_the_queue_fills_mid_window(
    jobs: RefreshJobService, scratch_db: sa.Engine
) -> None:
    for index in range(jobs_module.MAX_PENDING_JOBS - 5):
        jobs.submit(
            f"fill-{index}",
            Region.QLD1,
            date(2023, 1, 1) + timedelta(days=index),
            "scheduler",
        )
    with pytest.raises(jobs_module.QueueFull):
        jobs.submit_window("month", REGION, DAY, DAY + timedelta(days=10), "op")
    assert count(scratch_db, "refresh_job") == jobs_module.MAX_PENDING_JOBS - 5
    with scratch_db.connect() as conn:
        stray: int = conn.execute(
            sa.text(
                "SELECT count(*) FROM refresh_request"
                " WHERE substring(request_key from 1 for 6) = 'month:'"
            )
        ).scalar_one()
    assert stray == 0
