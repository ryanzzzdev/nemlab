"""NEM-070 schema adoption tests.

Unit tests cover the Flyway checksum reproduction and history validation.
Integration tests run against a throwaway database on the server named by
``NEMLAB_DB_URL`` (the developer compose PostgreSQL); they create and drop a
``nemlab_test_*`` database per test and skip when the server is unreachable.
"""

import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from db_fixture import apply_schema

from nemlab_infrastructure.schema import (
    EXPECTED_HISTORY,
    AdoptionError,
    State,
    _check_history,
    _check_schema,
    flyway_checksum,
    inspect_state,
    migration_text,
    validate_java_database,
)
from nemlab_infrastructure.settings import DatabaseSettings

REPO_ROOT = Path(__file__).resolve().parents[2]

# Captured from flyway_schema_history produced by Flyway 12.4.0 (Java migrate).
AUTHORITATIVE_CHECKSUMS = {
    "V1__price_foundation.sql": -1351753437,
    "V2__refresh_jobs.sql": 581062717,
    "V3__simulation_jobs.sql": -144120848,
}

FLYWAY_HISTORY_DDL = """
CREATE TABLE flyway_schema_history (
    installed_rank integer NOT NULL,
    version varchar(50),
    description varchar(200) NOT NULL,
    type varchar(20) NOT NULL,
    script varchar(1000) NOT NULL,
    checksum integer,
    installed_by varchar(100) NOT NULL,
    installed_on timestamp NOT NULL DEFAULT now(),
    execution_time integer NOT NULL,
    success boolean NOT NULL,
    CONSTRAINT flyway_schema_history_pk PRIMARY KEY (installed_rank)
);
CREATE INDEX flyway_schema_history_s_idx ON flyway_schema_history (success);
"""


def _alembic_config(monkeypatch: pytest.MonkeyPatch, engine: sa.Engine) -> Config:
    db_name = engine.url.database
    assert db_name is not None
    base = DatabaseSettings()
    url = base.db_url.rsplit("/", 1)[0] + "/" + db_name
    monkeypatch.setenv("NEMLAB_DB_URL", url)
    cfg = Config()
    cfg.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    return cfg


def _apply_java_schema(engine: sa.Engine) -> None:
    """Replay the Flyway DDL and history exactly as the Java migrate leaves it."""
    apply_schema(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql(FLYWAY_HISTORY_DDL)
        for rank, (version, description, script) in enumerate(EXPECTED_HISTORY, 1):
            conn.execute(
                sa.text(
                    "INSERT INTO flyway_schema_history"
                    " (installed_rank, version, description, type, script,"
                    "  checksum, installed_by, execution_time, success)"
                    " VALUES (:rank, :version, :description, 'SQL', :script,"
                    "  :checksum, 'test', 0, true)"
                ),
                {
                    "rank": rank,
                    "version": version,
                    "description": description,
                    "script": script,
                    "checksum": flyway_checksum(migration_text(script)),
                },
            )


# -- checksum reproduction (no database) ------------------------------------


def test_packaged_scripts_match_authoritative_flyway_checksums() -> None:
    for script, checksum in AUTHORITATIVE_CHECKSUMS.items():
        assert flyway_checksum(migration_text(script)) == checksum


def test_checksum_matches_reference_tree_scripts() -> None:
    reference = (
        REPO_ROOT / "reference/java/infrastructure/src/main/resources/db/migration"
    )
    for script, checksum in AUTHORITATIVE_CHECKSUMS.items():
        assert flyway_checksum((reference / script).read_text()) == checksum


def test_checksum_handles_crlf_and_bom() -> None:
    plain = "a\nb\n"
    crlf = "a\r\nb\r\n"
    bommed = "\ufeffa\nb\n"
    assert flyway_checksum(plain) == flyway_checksum(crlf) == flyway_checksum(bommed)


def test_checksum_unicode_line_separators_do_not_split() -> None:
    # Java readLine does not split on U+2028 — the line is hashed whole.
    joined = flyway_checksum("a\u2028b")
    split = flyway_checksum("a\nb")
    assert joined != split


# -- history validation (no database) ---------------------------------------


def _history_row(
    rank: int, version: str, description: str, script: str, checksum: int
) -> SimpleNamespace:
    return SimpleNamespace(
        installed_rank=rank,
        version=version,
        description=description,
        type="SQL",
        script=script,
        checksum=checksum,
        success=True,
    )


def _good_history() -> list[SimpleNamespace]:
    return [
        _history_row(
            rank,
            version,
            description,
            script,
            flyway_checksum(migration_text(script)),
        )
        for rank, (version, description, script) in enumerate(EXPECTED_HISTORY, 1)
    ]


def test_history_accepts_exact_v1_v3() -> None:
    _check_history(_good_history())


@pytest.mark.parametrize("row_index", [0, 1, 2])
def test_history_rejects_checksum_mismatch(row_index: int) -> None:
    rows = _good_history()
    rows[row_index].checksum += 1
    with pytest.raises(AdoptionError, match="drifted"):
        _check_history(rows)


def test_history_rejects_failed_migration() -> None:
    rows = _good_history()
    rows[0].success = False
    with pytest.raises(AdoptionError, match="drifted"):
        _check_history(rows)


def test_history_rejects_missing_migration() -> None:
    with pytest.raises(AdoptionError, match="2 rows"):
        _check_history(_good_history()[:2])


def test_history_rejects_extra_migration() -> None:
    rows = _good_history()
    rows.append(_history_row(4, "4", "unexpected", "V4__other.sql", 0))
    with pytest.raises(AdoptionError, match="4 rows"):
        _check_history(rows)


# -- integration: state inspection, migrate, adopt --------------------------


def test_empty_database(scratch_db: sa.Engine) -> None:
    assert inspect_state(scratch_db) is State.EMPTY
    with pytest.raises(AdoptionError, match="no schema objects"):
        validate_java_database(scratch_db)


def test_unknown_database_refused(scratch_db: sa.Engine) -> None:
    with scratch_db.begin() as conn:
        conn.execute(sa.text("CREATE TABLE stray (id int)"))
    assert inspect_state(scratch_db) is State.UNKNOWN
    with pytest.raises(AdoptionError, match="unknown provenance"):
        validate_java_database(scratch_db)


def test_migrate_creates_full_schema(
    scratch_db: sa.Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = _alembic_config(monkeypatch, scratch_db)
    command.upgrade(cfg, "head")
    assert inspect_state(scratch_db) is State.ALEMBIC_MANAGED
    # The fresh schema satisfies the same manifest adoption validates against.
    with scratch_db.connect() as conn:
        _check_schema(conn)
    # Repeated upgrade is a no-op.
    command.upgrade(cfg, "head")


def test_adopt_java_managed_database(
    scratch_db: sa.Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    _apply_java_schema(scratch_db)
    assert inspect_state(scratch_db) is State.JAVA_MANAGED
    validate_java_database(scratch_db)
    cfg = _alembic_config(monkeypatch, scratch_db)
    command.stamp(cfg, "head")
    assert inspect_state(scratch_db) is State.ALEMBIC_MANAGED
    with scratch_db.connect() as conn:
        count = conn.execute(
            sa.text("SELECT count(*) FROM flyway_schema_history")
        ).scalar()
    assert count == 3


def test_adopt_preserves_existing_rows(
    scratch_db: sa.Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    _apply_java_schema(scratch_db)
    with scratch_db.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO price_revision"
                " (id, region, market_day, content_hash, slots,"
                "  valid_count, missing_count, null_count)"
                " SELECT '11111111-1111-1111-1111-111111111111', 'NSW1',"
                "  '2025-01-15', repeat('a', 64),"
                "  (SELECT jsonb_agg(to_jsonb(0)) FROM generate_series(1, 288)),"
                "  288, 0, 0"
            )
        )
    validate_java_database(scratch_db)
    command.stamp(_alembic_config(monkeypatch, scratch_db), "head")
    with scratch_db.connect() as conn:
        row = conn.execute(
            sa.text("SELECT region, market_day FROM price_revision")
        ).one()
    assert row == ("NSW1", datetime.date(2025, 1, 15))


def test_adopt_refuses_drifted_schema(scratch_db: sa.Engine) -> None:
    _apply_java_schema(scratch_db)
    with scratch_db.begin() as conn:
        conn.execute(sa.text("DROP TRIGGER immutable_revision ON price_revision"))
    with pytest.raises(AdoptionError, match="missing triggers"):
        validate_java_database(scratch_db)


def test_adopt_refuses_missing_table(scratch_db: sa.Engine) -> None:
    _apply_java_schema(scratch_db)
    with scratch_db.begin() as conn:
        conn.execute(sa.text("DROP TABLE refresh_job_event CASCADE"))
    with pytest.raises(AdoptionError, match="missing tables"):
        validate_java_database(scratch_db)


def test_adopt_refuses_tampered_history_checksum(scratch_db: sa.Engine) -> None:
    _apply_java_schema(scratch_db)
    with scratch_db.begin() as conn:
        conn.execute(
            sa.text(
                "UPDATE flyway_schema_history SET checksum = 0 WHERE installed_rank = 2"
            )
        )
    with pytest.raises(AdoptionError, match="row 2"):
        validate_java_database(scratch_db)


def test_migrate_on_java_managed_rolls_back(
    scratch_db: sa.Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A plain `migrate` on an unadopted Java database fails inside the
    baseline DDL; transactional DDL must leave no partial state behind."""
    _apply_java_schema(scratch_db)
    cfg = _alembic_config(monkeypatch, scratch_db)
    with pytest.raises(sa.exc.ProgrammingError):
        command.upgrade(cfg, "head")
    assert inspect_state(scratch_db) is State.JAVA_MANAGED
    with scratch_db.connect() as conn:
        assert not conn.execute(
            sa.text("SELECT to_regclass('alembic_version')")
        ).scalar()
        assert (
            conn.execute(sa.text("SELECT count(*) FROM flyway_schema_history")).scalar()
            == 3
        )
        assert (
            conn.execute(sa.text("SELECT count(*) FROM price_revision")).scalar() == 0
        )
    # The database is still adoptable after the failed upgrade.
    validate_java_database(scratch_db)


def test_migrate_command_refuses_java_managed(
    scratch_db: sa.Engine,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The `migrate` entry point refuses a Java-managed database with a clear
    message instead of crashing on duplicate-table DDL."""
    from nemlab_infrastructure import migrate

    _apply_java_schema(scratch_db)
    _alembic_config(monkeypatch, scratch_db)
    monkeypatch.chdir(REPO_ROOT)
    assert migrate.main(["migrate"]) == 1
    assert "run `adopt`" in capsys.readouterr().err
    assert inspect_state(scratch_db) is State.JAVA_MANAGED


def test_migrate_command_refuses_unknown_provenance(
    scratch_db: sa.Engine,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from nemlab_infrastructure import migrate

    with scratch_db.begin() as conn:
        conn.execute(sa.text("CREATE TABLE stray (id int)"))
    _alembic_config(monkeypatch, scratch_db)
    monkeypatch.chdir(REPO_ROOT)
    assert migrate.main(["migrate"]) == 1
    assert "unknown provenance" in capsys.readouterr().err
    assert inspect_state(scratch_db) is State.UNKNOWN
