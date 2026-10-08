"""Scratch-DB fixtures plus an enabled ``TestClient`` for the HTTP tests.

``db_fixture`` is uniquely named precisely so it can be imported across test
dirs without colliding with either package's ``conftest``.
"""

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

sys.path.insert(
    0, str(Path(__file__).resolve().parents[2] / "infrastructure" / "tests")
)

from db_fixture import apply_admin_schema, apply_grid_schema, apply_schema, scratch_db

from nemlab_api.app import create_app
from nemlab_api.settings import ApiSettings
from nemlab_infrastructure.settings import DatabaseSettings

__all__ = ["apply_admin_schema", "apply_grid_schema", "apply_schema", "scratch_db"]

TOKEN = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG"

TRUNCATE = (
    "TRUNCATE admin_session, admin_token, admin_viewer_grant,"
    " admin_access_request, admin_email_outbox, admin_access_audit,"
    " admin_rate_limit, admin_user,"
    " grid_detection_run, grid_catalogue_current,"
    " grid_publication_event, grid_publication, grid_replay, grid_event,"
    " grid_import_job_event, grid_import_request, grid_import_job,"
    " grid_import_attempt, grid_current, grid_revision,"
    " simulation_result, simulation_job, simulation_input,"
    " refresh_job_event, refresh_request, refresh_job,"
    " price_snapshot, price_current, price_import_attempt,"
    " price_revision, price_backfill"
)


@pytest.fixture(autouse=True)
def clean(scratch_db: sa.Engine) -> None:
    apply_admin_schema(scratch_db)
    with scratch_db.begin() as conn:
        conn.execute(sa.text(TRUNCATE))


@pytest.fixture
def settings(scratch_db: sa.Engine, clean: None) -> ApiSettings:
    base = DatabaseSettings()
    url = (
        f"jdbc:postgresql://{scratch_db.url.host}:{scratch_db.url.port}"
        f"/{scratch_db.url.database}"
    )
    return ApiSettings(
        db_url=url,
        db_user=base.db_user,
        db_password=base.db_password,
        data_enabled=True,
        admin_enabled=True,
        admin_operator="alice",
        admin_token=TOKEN,
        admin_base_url="http://testserver/admin",
        environment="development",
        insecure_cookies=True,
        simulation_api_enabled=True,
    )


@pytest.fixture
def client(settings: ApiSettings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client
