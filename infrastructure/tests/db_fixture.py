"""Shared fixtures: throwaway ``nemlab_test_*`` databases on the server named
by ``NEMLAB_DB_URL`` (developer compose PostgreSQL), skipped when unreachable."""

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
import sqlalchemy as sa

from nemlab_infrastructure.settings import DatabaseSettings

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_db_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Apply repo `.env` database credentials when not already set — tests
    exercise the same NEMLAB_* contract as the CLI. Function-scoped via
    monkeypatch so feature flags never leak to sibling tests."""
    env_file = REPO_ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text().splitlines():
            key, _, value = line.partition("=")
            if key in ("NEMLAB_DB_URL", "NEMLAB_DB_USER", "NEMLAB_DB_PASSWORD") and (
                key not in os.environ
            ):
                monkeypatch.setenv(key, value.strip().strip('"'))


@pytest.fixture
def scratch_db(monkeypatch: pytest.MonkeyPatch) -> Iterator[sa.Engine]:
    """A fresh empty database on the configured server, dropped on teardown."""
    load_db_env(monkeypatch)
    admin = sa.create_engine(
        DatabaseSettings().sqlalchemy_url(), isolation_level="AUTOCOMMIT"
    )
    try:
        admin.connect().close()
    except sa.exc.OperationalError:
        pytest.skip("no PostgreSQL server at NEMLAB_DB_URL")
    name = f"nemlab_test_{uuid.uuid4().hex[:12]}"
    with admin.connect() as conn:
        conn.execute(sa.text(f'CREATE DATABASE "{name}"'))
    url = DatabaseSettings().sqlalchemy_url().rsplit("/", 1)[0] + "/" + name
    engine = sa.create_engine(url)
    yield engine
    engine.dispose()
    with admin.connect() as conn:
        conn.execute(sa.text(f'DROP DATABASE "{name}" WITH (FORCE)'))
    admin.dispose()


def apply_schema(engine: sa.Engine) -> None:
    """Replay the packaged V1-V3 DDL exactly (the same bytes Alembic runs)."""
    from nemlab_infrastructure.schema import EXPECTED_HISTORY, migration_text

    with engine.begin() as conn:
        for _version, _description, script in EXPECTED_HISTORY:
            conn.exec_driver_sql(migration_text(script))


def apply_grid_schema(engine: sa.Engine) -> None:
    """The Java baseline plus the post-baseline migrations (V4-V7)."""
    from nemlab_infrastructure.schema import migration_text

    apply_schema(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql(migration_text("V4__grid_observations.sql"))
        conn.exec_driver_sql(migration_text("V5__grid_import_jobs.sql"))
        conn.exec_driver_sql(migration_text("V6__grid_events.sql"))
        conn.exec_driver_sql(migration_text("V7__detector_v2.sql"))


def apply_admin_schema(engine: sa.Engine) -> None:
    """The grid schema plus the V8 admin-identity tables."""
    from nemlab_infrastructure.schema import migration_text

    apply_grid_schema(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql(migration_text("V8__admin_identity.sql"))
