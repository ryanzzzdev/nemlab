"""NEM-102 load-operation tests — bounded chunk dispatch, deterministic
request keys for crash/reload reconciliation, backpressure, pause vs
cancel, explicit resume and remaining-window resubmission."""

from datetime import date, timedelta
from uuid import uuid4

import pytest
import sqlalchemy as sa
from db_fixture import apply_admin_schema

from nemlab_core.prices import Region
from nemlab_infrastructure.grid.imports import GridImportJobs
from nemlab_infrastructure.grid.store import GridStore
from nemlab_infrastructure.jobs import RefreshJobService
from nemlab_infrastructure.load_operations import (
    LoadConflict,
    LoadNotFound,
    LoadOperations,
)
from nemlab_infrastructure.prices.store import PriceStore

START = date(2023, 9, 4)
REGION = Region.NSW1


@pytest.fixture
def grid_jobs(scratch_db: sa.Engine) -> GridImportJobs:
    apply_admin_schema(scratch_db)
    return GridImportJobs(scratch_db, GridStore(scratch_db))


@pytest.fixture
def operations(scratch_db: sa.Engine, grid_jobs: GridImportJobs) -> LoadOperations:
    return LoadOperations(
        scratch_db,
        grid_jobs,
        RefreshJobService(scratch_db, PriceStore(scratch_db)),
    )


def test_begin_persists_scope_and_rejects_out_of_bounds(
    operations: LoadOperations,
) -> None:
    op = operations.begin(REGION, START, START + timedelta(days=40), "owner")
    assert op.status == "dispatching"
    assert op.phase == "grid"
    assert op.next_day == START
    assert operations.get(op.id) is not None

    for start, end in [
        (START, START),  # empty
        (START, START + timedelta(days=367)),  # over cap
        (date(2000, 1, 1), date(2000, 2, 1)),  # before earliest data
        (date.today() + timedelta(days=1), date.today() + timedelta(days=2)),
    ]:
        with pytest.raises(ValueError, match="1-366 day"):
            operations.begin(REGION, start, end, "owner")


def test_dispatch_chunks_grid_then_price_until_dispatched(
    operations: LoadOperations,
) -> None:
    end = START + timedelta(days=70)
    op = operations.begin(REGION, START, end, "owner")

    first = operations.dispatch(op.id, "owner")
    assert first.kind == "submitted"
    child = first.child
    assert child is not None
    assert child.phase == "grid"
    assert child.start == START
    assert child.end == START + timedelta(days=31)
    assert len(child.job_ids) == 1
    assert child.request_key == f"load:{op.id}:grid:{START}"

    for _ in range(5):
        operations.dispatch(op.id, "owner")

    done = operations.get(op.id)
    assert done is not None and done.status == "dispatched"
    children = operations.children(op.id)
    # Grid: 31+31+8 = three children; price: 31+31+8 = three children.
    assert [(c.phase, c.start) for c in children] == [
        ("grid", START),
        ("grid", START + timedelta(days=31)),
        ("grid", START + timedelta(days=62)),
        ("price", START),
        ("price", START + timedelta(days=31)),
        ("price", START + timedelta(days=62)),
    ]
    # Price children fan out per day; the last (8-day) chunk holds 8 jobs.
    price_last = children[-1]
    assert price_last.phase == "price"
    assert len(price_last.job_ids) == 8
    # No further dispatch.
    assert operations.dispatch(op.id, "owner").kind == "dispatched"


def test_queue_full_backpressures_without_moving_cursor(
    scratch_db: sa.Engine, grid_jobs: GridImportJobs, operations: LoadOperations
) -> None:
    for i in range(20):  # grid queue cap
        grid_jobs.submit(
            f"fill:{i}",
            REGION,
            START + timedelta(days=100 + i),
            START + timedelta(days=101 + i),
            "operator",
        )

    op = operations.begin(REGION, START, START + timedelta(days=10), "owner")
    outcome = operations.dispatch(op.id, "owner")
    assert outcome.kind == "backpressured"
    after = operations.get(op.id)
    assert after is not None
    assert after.next_day == START  # cursor unmoved
    assert operations.children(op.id) == []


def test_crash_between_submission_and_link_reconciles(
    operations: LoadOperations, grid_jobs: GridImportJobs
) -> None:
    """A queue submission whose link recording was lost re-binds via the
    deterministic request key — same job, never a duplicate."""
    op = operations.begin(REGION, START, START + timedelta(days=10), "owner")
    key = f"load:{op.id}:grid:{START}"
    job_id = grid_jobs.submit(key, REGION, START, START + timedelta(days=10), "owner")

    outcome = operations.dispatch(op.id, "owner")
    assert outcome.kind == "submitted"
    child = outcome.child
    assert child is not None
    assert child.job_ids == (job_id,)  # bound to the orphaned job

    # Continuing dispatch cannot duplicate the submitted chunk — the
    # grid phase is complete, so the next chunk is the price phase.
    second = operations.dispatch(op.id, "owner")
    assert second.child is not None
    assert (second.child.phase, second.child.start) == ("price", START)
    assert len(operations.children(op.id)) == 2


def test_pause_stops_dispatch_not_queued_children(
    scratch_db: sa.Engine, operations: LoadOperations
) -> None:
    op = operations.begin(REGION, START, START + timedelta(days=70), "owner")
    outcome = operations.dispatch(op.id, "owner")
    operations.pause(op.id)

    paused = operations.get(op.id)
    assert paused is not None and paused.status == "paused"
    with pytest.raises(LoadConflict, match="paused"):
        operations.dispatch(op.id, "owner")

    # Queued child jobs keep running — pause is dispatch-only.
    states = operations.job_states(op.id)
    assert outcome.child is not None
    assert states[outcome.child.job_ids[0]]["status"] == "QUEUED"

    # Resume and continue — remaining window resubmits, nothing duplicates.
    operations.resume(op.id)
    again = operations.dispatch(op.id, "owner")
    assert again.child is not None
    assert again.child.start == START + timedelta(days=31)
    assert len(operations.children(op.id)) == 2


def test_pause_and_resume_are_explicit_and_idempotent_guards(
    operations: LoadOperations,
) -> None:
    op = operations.begin(REGION, START, START + timedelta(days=10), "owner")
    with pytest.raises(LoadConflict):
        operations.resume(op.id)  # not paused
    operations.pause(op.id)
    with pytest.raises(LoadConflict):
        operations.pause(op.id)  # already paused
    operations.resume(op.id)
    with pytest.raises(LoadConflict):
        operations.resume(op.id)  # duplicate resume
    assert operations.get(op.id) is not None
    with pytest.raises(LoadNotFound):
        operations.pause(uuid4())


def test_job_states_joins_queue_tables(
    operations: LoadOperations,
) -> None:
    op = operations.begin(REGION, START, START + timedelta(days=5), "owner")
    operations.dispatch(op.id, "owner")
    states = operations.job_states(op.id)
    assert len(states) == 1
    state = next(iter(states.values()))
    assert state["status"] == "QUEUED"
    assert state["nextDay"] == str(START)


def test_recent_lists_newest_first(operations: LoadOperations) -> None:
    a = operations.begin(REGION, START, START + timedelta(days=5), "owner")
    b = operations.begin(REGION, START, START + timedelta(days=5), "owner")
    recent = operations.recent()
    assert [op.id for op in recent][:2] == [b.id, a.id]
