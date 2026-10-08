"""NEM-095 admin identity storage and owner bootstrap tests.

Integration tests run against a throwaway ``nemlab_test_*`` database per
test on the server named by ``NEMLAB_DB_URL`` and skip when unreachable.
"""

import threading
import uuid

import pytest
import sqlalchemy as sa
from db_fixture import REPO_ROOT, apply_admin_schema, apply_grid_schema

from nemlab_infrastructure.admin.identity import AdminIdentity, OwnerExists
from nemlab_infrastructure.schema import migration_text
from nemlab_infrastructure.settings import DatabaseSettings

NAME = "Test Owner"
EMAIL = "owner@example.test"


@pytest.fixture
def identity(scratch_db: sa.Engine) -> AdminIdentity:
    apply_admin_schema(scratch_db)
    return AdminIdentity(scratch_db)


def _count(engine: sa.Engine, sql: str, **params: object) -> int:
    with engine.connect() as conn:
        return conn.execute(sa.text(sql), params).scalar_one()


def _actions(engine: sa.Engine) -> list[str]:
    with engine.connect() as conn:
        return [
            row[0]
            for row in conn.execute(
                sa.text("SELECT action FROM admin_access_audit ORDER BY id")
            )
        ]


def test_bootstrap_creates_single_owner(identity: AdminIdentity) -> None:
    owner, created = identity.bootstrap_owner(NAME, EMAIL)
    assert created
    assert owner.role == "owner" and owner.email == EMAIL
    assert identity.owner() == owner
    assert _actions(identity.engine) == ["OWNER_BOOTSTRAPPED"]


def test_bootstrap_is_idempotent(identity: AdminIdentity) -> None:
    first, _ = identity.bootstrap_owner(NAME, EMAIL)
    second, created = identity.bootstrap_owner(NAME, EMAIL)
    assert not created and second.id == first.id
    assert _count(identity.engine, "SELECT count(*) FROM admin_user") == 1


def test_bootstrap_refuses_a_different_email(identity: AdminIdentity) -> None:
    identity.bootstrap_owner(NAME, EMAIL)
    with pytest.raises(OwnerExists):
        identity.bootstrap_owner(NAME, "other@example.test")
    assert _count(identity.engine, "SELECT count(*) FROM admin_user") == 1


def test_bootstrap_validates_identity(identity: AdminIdentity) -> None:
    for name in ("", "   ", "x" * 101):
        with pytest.raises(ValueError):
            identity.bootstrap_owner(name, EMAIL)
    for email in ("", "no-at-sign", "a @@b", "still-bad@", "x" * 255):
        with pytest.raises(ValueError):
            identity.bootstrap_owner(NAME, email)
    assert _count(identity.engine, "SELECT count(*) FROM admin_user") == 0


def test_concurrent_bootstrap_creates_one_owner(
    identity: AdminIdentity,
) -> None:
    barrier = threading.Barrier(2)
    results: list[tuple[object, bool] | Exception] = []

    def run() -> None:
        barrier.wait()
        try:
            results.append(identity.bootstrap_owner(NAME, EMAIL))
        except Exception as ex:
            results.append(ex)

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert _count(identity.engine, "SELECT count(*) FROM admin_user") == 1
    owner = identity.owner()
    assert owner is not None
    for result in results:
        assert not isinstance(result, Exception)
        assert result[0].id == owner.id


def test_single_owner_constraint_is_enforced(identity: AdminIdentity) -> None:
    identity.bootstrap_owner(NAME, EMAIL)
    with pytest.raises(sa.exc.IntegrityError), identity.engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO admin_user (id, role, display_name, email)"
                " VALUES (:id, 'owner', 'Second', 'second@example.test')"
            ),
            {"id": uuid.uuid4()},
        )
    # A disabled former owner does not count.
    with identity.engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO admin_user"
                " (id, role, display_name, email, disabled_at)"
                " VALUES (:id, 'owner', 'Old', 'old@example.test', now())"
            ),
            {"id": uuid.uuid4()},
        )


def test_email_uniqueness_is_case_insensitive(identity: AdminIdentity) -> None:
    identity.bootstrap_owner(NAME, EMAIL)
    with pytest.raises(sa.exc.IntegrityError), identity.engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO admin_user (id, role, display_name, email)"
                " VALUES (:id, 'viewer', 'Viewer', 'OWNER@example.test')"
            ),
            {"id": uuid.uuid4()},
        )


def _insert_request(conn: sa.Connection, email: str, status: str) -> uuid.UUID:
    return conn.execute(
        sa.text(
            "INSERT INTO admin_access_request (id, display_name, email, status)"
            " VALUES (:id, 'V', :email, :status) RETURNING id"
        ),
        {"id": uuid.uuid4(), "email": email, "status": status},
    ).scalar_one()


def _insert_decided(
    conn: sa.Connection, email: str, status: str, decided_by: uuid.UUID
) -> uuid.UUID:
    return conn.execute(
        sa.text(
            "INSERT INTO admin_access_request"
            " (id, display_name, email, status, verified_at,"
            "  decided_at, decided_by)"
            " VALUES (:id, 'V', :email, :status, now(), now(), :by)"
            " RETURNING id"
        ),
        {"id": uuid.uuid4(), "email": email, "status": status, "by": decided_by},
    ).scalar_one()


def test_request_token_session_invariants(identity: AdminIdentity) -> None:
    owner, _ = identity.bootstrap_owner(NAME, EMAIL)
    with identity.engine.begin() as conn:
        _insert_request(conn, "v@example.test", "unverified")
        # Pending requires verified_at; decided states require a decider.
        with pytest.raises(sa.exc.IntegrityError), conn.begin_nested():
            _insert_request(conn, "v2@example.test", "pending")
        with pytest.raises(sa.exc.IntegrityError), conn.begin_nested():
            _insert_request(conn, "v3@example.test", "approved")
        request_id = _insert_decided(conn, "v4@example.test", "approved", owner.id)
        # A token binds exactly one subject matching its purpose.
        with pytest.raises(sa.exc.IntegrityError), conn.begin_nested():
            conn.execute(
                sa.text(
                    "INSERT INTO admin_token"
                    " (id, purpose, user_id, request_id, token_hash, expires_at)"
                    " VALUES (:id, 'sign_in', :user, :request, :hash,"
                    "  now() + interval '15 minutes')"
                ),
                {
                    "id": uuid.uuid4(),
                    "user": owner.id,
                    "request": request_id,
                    "hash": "a" * 64,
                },
            )
        with pytest.raises(sa.exc.IntegrityError), conn.begin_nested():
            conn.execute(
                sa.text(
                    "INSERT INTO admin_token"
                    " (id, purpose, request_id, token_hash, expires_at)"
                    " VALUES (:id, 'sign_in', :request, :hash,"
                    "  now() + interval '15 minutes')"
                ),
                {"id": uuid.uuid4(), "request": request_id, "hash": "b" * 64},
            )
        # A session binds exactly one subject.
        with pytest.raises(sa.exc.IntegrityError), conn.begin_nested():
            conn.execute(
                sa.text(
                    "INSERT INTO admin_session (id, token_hash, expires_at)"
                    " VALUES (:id, :hash, now() + interval '8 hours')"
                ),
                {"id": uuid.uuid4(), "hash": "c" * 64},
            )


def test_active_request_uniqueness_per_email(identity: AdminIdentity) -> None:
    owner, _ = identity.bootstrap_owner(NAME, EMAIL)
    with identity.engine.begin() as conn:
        _insert_request(conn, "v@example.test", "unverified")
        # A second undecided request for the same normalised email
        # conflicts, but a decided request frees the email.
        with pytest.raises(sa.exc.IntegrityError), conn.begin_nested():
            _insert_request(conn, "V@example.test", "unverified")
        _insert_decided(conn, "v@example.test", "rejected", owner.id)


def test_recovery_replaces_owner_and_revokes_sessions(
    identity: AdminIdentity,
) -> None:
    previous, _ = identity.bootstrap_owner(NAME, EMAIL)
    with identity.engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO admin_session (id, user_id, token_hash, expires_at)"
                " VALUES (:id, :user, :hash, now() + interval '8 hours')"
            ),
            {"id": uuid.uuid4(), "user": previous.id, "hash": "d" * 64},
        )
    replacement = identity.recover_owner(
        "New Owner", "new@example.test", "lost mailbox"
    )
    assert identity.owner() == replacement
    with identity.engine.connect() as conn:
        old = conn.execute(
            sa.text("SELECT disabled_at FROM admin_user WHERE id = :id"),
            {"id": previous.id},
        ).scalar_one()
        assert old is not None
        revoked = conn.execute(
            sa.text("SELECT revoked_at FROM admin_session WHERE user_id = :id"),
            {"id": previous.id},
        ).scalar_one()
        assert revoked is not None
    assert _actions(identity.engine) == [
        "OWNER_BOOTSTRAPPED",
        "OWNER_DISABLED",
        "OWNER_RECOVERED",
    ]


def test_recovery_without_existing_owner(identity: AdminIdentity) -> None:
    owner = identity.recover_owner(NAME, EMAIL, "first setup")
    assert identity.owner() == owner
    assert _actions(identity.engine) == ["OWNER_RECOVERED"]


def test_cli_bootstrap_and_recovery(
    scratch_db: sa.Engine,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from nemlab_infrastructure.admin.__main__ import main

    apply_admin_schema(scratch_db)
    db_name = scratch_db.url.database
    assert db_name is not None
    base = DatabaseSettings()
    monkeypatch.setenv("NEMLAB_DB_URL", base.db_url.rsplit("/", 1)[0] + "/" + db_name)
    monkeypatch.setenv("NEMLAB_DB_USER", base.db_user)
    monkeypatch.setenv("NEMLAB_DB_PASSWORD", base.db_password)

    argv = ["bootstrap-owner", "--name", NAME, "--email", EMAIL]
    assert main(argv) == 2  # no --confirm
    assert "refused" in capsys.readouterr().err
    assert main([*argv, "--confirm"]) == 0
    assert "created" in capsys.readouterr().out
    assert main([*argv, "--confirm"]) == 0
    assert "unchanged" in capsys.readouterr().out
    different = [
        "bootstrap-owner",
        "--name",
        NAME,
        "--email",
        "other@example.test",
        "--confirm",
    ]
    assert main(different) == 1
    assert "recover-owner" in capsys.readouterr().err
    recovered = [
        "recover-owner",
        "--name",
        "New Owner",
        "--email",
        "new@example.test",
        "--reason",
        "lost mailbox",
        "--confirm",
    ]
    assert main(recovered) == 0
    assert "recovered" in capsys.readouterr().out
    assert _count(scratch_db, "SELECT count(*) FROM admin_user") == 2


def test_alembic_upgrade_and_downgrade(
    scratch_db: sa.Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real Alembic chain applies V8 and rolls it back cleanly."""
    from alembic import command
    from alembic.config import Config

    db_name = scratch_db.url.database
    assert db_name is not None
    base = DatabaseSettings()
    monkeypatch.setenv("NEMLAB_DB_URL", base.db_url.rsplit("/", 1)[0] + "/" + db_name)
    monkeypatch.setenv("NEMLAB_DB_USER", base.db_user)
    monkeypatch.setenv("NEMLAB_DB_PASSWORD", base.db_password)
    cfg = Config()
    cfg.set_main_option("script_location", str(REPO_ROOT / "migrations"))

    def admin_tables() -> set[str]:
        with scratch_db.connect() as conn:
            return {
                row[0]
                for row in conn.execute(
                    sa.text(
                        "SELECT table_name FROM information_schema.tables"
                        " WHERE table_schema = 'public' AND table_name"
                        " LIKE 'admin_%'"
                    )
                )
            }

    def revision() -> str:
        with scratch_db.connect() as conn:
            return conn.execute(
                sa.text("SELECT version_num FROM alembic_version")
            ).scalar_one()

    command.upgrade(cfg, "head")
    assert revision() == "nemlab_v8_admin_identity"
    assert "admin_user" in admin_tables()
    command.downgrade(cfg, "nemlab_v7_detector_v2")
    assert revision() == "nemlab_v7_detector_v2"
    assert admin_tables() == set()


def test_migration_preserves_existing_data(scratch_db: sa.Engine) -> None:
    """V8 leaves market/job data untouched on a populated schema."""
    apply_grid_schema(scratch_db)
    with scratch_db.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO price_revision"
                " (id, region, market_day, content_hash, slots,"
                "  valid_count, missing_count, null_count)"
                " VALUES ('11111111-1111-1111-1111-111111111111', 'NSW1',"
                "  '2025-01-15', repeat('a', 64),"
                "  (SELECT jsonb_agg(to_jsonb(0))"
                "   FROM generate_series(1, 288)), 288, 0, 0)"
            )
        )
        conn.exec_driver_sql(migration_text("V8__admin_identity.sql"))
        assert (
            conn.execute(sa.text("SELECT count(*) FROM price_revision")).scalar_one()
            == 1
        )
        tables = {
            row[0]
            for row in conn.execute(
                sa.text(
                    "SELECT table_name FROM information_schema.tables"
                    " WHERE table_schema = 'public'"
                )
            )
        }
    assert {
        "admin_user",
        "admin_access_request",
        "admin_viewer_grant",
        "admin_token",
        "admin_session",
        "admin_email_outbox",
        "admin_access_audit",
        "admin_rate_limit",
    } <= tables
