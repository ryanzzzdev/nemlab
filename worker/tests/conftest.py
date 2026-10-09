"""Reuse the infrastructure scratch-database fixtures without duplicating the
scratch-DB lifecycle, and expose the store/jobs/clean fixtures the refresh
tests share."""

import sys
from pathlib import Path

import pytest
import sqlalchemy as sa

# ``db_fixture`` is uniquely named precisely so it can be imported across
# test dirs without colliding with either package's ``conftest``.
sys.path.insert(
    0, str(Path(__file__).resolve().parents[2] / "infrastructure" / "tests")
)

from db_fixture import apply_schema, apply_simulation_events, scratch_db

from nemlab_infrastructure.jobs import RefreshJobService
from nemlab_infrastructure.prices.store import PriceStore

__all__ = ["apply_schema", "scratch_db"]

TRUNCATE = (
    "TRUNCATE simulation_result, simulation_event, simulation_job,"
    " simulation_input,"
    " refresh_job_event, refresh_request, refresh_job,"
    " price_snapshot, price_current, price_import_attempt,"
    " price_revision, price_backfill"
)


@pytest.fixture
def store(scratch_db: sa.Engine) -> PriceStore:
    apply_schema(scratch_db)
    apply_simulation_events(scratch_db)
    return PriceStore(scratch_db)


@pytest.fixture
def jobs(scratch_db: sa.Engine, store: PriceStore) -> RefreshJobService:
    return RefreshJobService(scratch_db, store)


@pytest.fixture(autouse=True)
def clean(store: PriceStore, scratch_db: sa.Engine) -> None:
    with scratch_db.begin() as conn:
        conn.execute(sa.text(TRUNCATE))
