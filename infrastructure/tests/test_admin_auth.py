"""NEM-096 service tests: sign-in tokens, sessions, mail outbox, limits.

Runs against a throwaway ``nemlab_test_*`` database like the rest of the
infrastructure suite; the only transport is the captured ``LocalMailbox``.
"""

import threading
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import sqlalchemy as sa
from db_fixture import apply_admin_schema

from nemlab_infrastructure.admin.auth import (
    AdminAuth,
    InvalidToken,
    csrf_for,
)
from nemlab_infrastructure.admin.identity import AdminIdentity
from nemlab_infrastructure.admin.mail import LocalMailbox, OutboxMailer
from nemlab_infrastructure.admin.rate_limit import RateLimiter

EMAIL = "owner@example.test"
BASE_URL = "http://localhost:5173/admin"


@pytest.fixture
def services(scratch_db: sa.Engine) -> tuple[AdminAuth, AdminIdentity, RateLimiter]:
    apply_admin_schema(scratch_db)
    identity = AdminIdentity(scratch_db)
    identity.bootstrap_owner("Owner", EMAIL)
    return (
        AdminAuth(scratch_db, base_url=BASE_URL),
        identity,
        RateLimiter(scratch_db),
    )


def _outbox(engine: sa.Engine) -> list[sa.engine.Row]:
    with engine.connect() as conn:
        return list(
            conn.execute(
                sa.text("SELECT recipient, kind, status, body FROM admin_email_outbox")
            )
        )


def _raw_sign_in_token(auth: AdminAuth, email: str = EMAIL) -> str:
    """Mint a token via the outbox body — the only place the raw lives."""
    assert auth.request_sign_in(email)
    body = _outbox(auth.engine)[-1].body
    return body.split("#token=")[1].split("\n")[0]


def test_sign_in_mail_queued_for_owner(
    services: tuple[AdminAuth, AdminIdentity, RateLimiter],
) -> None:
    auth, _, _ = services
    assert auth.request_sign_in(EMAIL)
    rows = _outbox(auth.engine)
    assert len(rows) == 1 and rows[0].kind == "sign_in"
    assert rows[0].status == "pending" and rows[0].recipient == EMAIL
    assert "#token=" in rows[0].body


def test_sign_in_silent_for_unknown_or_disabled(
    services: tuple[AdminAuth, AdminIdentity, RateLimiter], scratch_db: sa.Engine
) -> None:
    auth, identity, _ = services
    assert not auth.request_sign_in("nobody@example.test")
    identity.recover_owner("New", "new@example.test", "test recovery")
    assert not auth.request_sign_in(EMAIL)  # replaced owner is disabled
    assert _outbox(auth.engine) == []


def test_exchange_then_replay_and_logout(
    services: tuple[AdminAuth, AdminIdentity, RateLimiter],
) -> None:
    auth, _, _ = services
    raw = _raw_sign_in_token(auth)
    session, principal = auth.exchange(raw)
    assert principal.role == "owner" and principal.name == "Owner"
    assert len(session) == 43
    with pytest.raises(InvalidToken):  # single-use: replay fails
        auth.exchange(raw)
    resolved = auth.resolve(session)
    assert resolved is not None and resolved.user_id == principal.user_id
    assert csrf_for(session) == csrf_for(session)
    auth.logout(session)
    assert auth.resolve(session) is None


def test_exchange_rejects_garbage_and_expired(
    services: tuple[AdminAuth, AdminIdentity, RateLimiter], scratch_db: sa.Engine
) -> None:
    auth, _, _ = services
    for bad in ("", "not-a-token", "x" * 200):
        with pytest.raises(InvalidToken):
            auth.exchange(bad)
    raw = _raw_sign_in_token(auth)
    with scratch_db.begin() as conn:
        conn.execute(
            sa.text(
                "UPDATE admin_token"
                " SET created_at = now() - interval '1h',"
                "     expires_at = now() - interval '1s'"
            )
        )
    with pytest.raises(InvalidToken):
        auth.exchange(raw)


def test_concurrent_exchange_consumes_once(
    services: tuple[AdminAuth, AdminIdentity, RateLimiter],
) -> None:
    auth, _, _ = services
    raw = _raw_sign_in_token(auth)
    barrier = threading.Barrier(2)
    results: list[object] = []

    def run() -> None:
        barrier.wait()
        try:
            results.append(auth.exchange(raw)[0])
        except InvalidToken:
            results.append(None)

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    sessions = [r for r in results if r is not None]
    assert len(sessions) == 1
    assert auth.resolve(sessions[0]) is not None


def test_session_idle_and_absolute_expiry(scratch_db: sa.Engine) -> None:
    apply_admin_schema(scratch_db)
    AdminIdentity(scratch_db).bootstrap_owner("Owner", EMAIL)
    clock = datetime.now(UTC)
    auth = AdminAuth(scratch_db, base_url=BASE_URL, now=lambda: clock)
    raw = _raw_sign_in_token(auth)
    session, _ = auth.exchange(raw)
    assert auth.resolve(session) is not None
    clock += timedelta(minutes=31)  # past 30-minute idle window
    assert auth.resolve(session) is None
    # Fresh session also dies at the 8-hour absolute boundary.
    clock = datetime.now(UTC)
    raw2 = _raw_sign_in_token(auth)
    session2, _ = auth.exchange(raw2)
    clock += timedelta(hours=8, seconds=1)
    assert auth.resolve(session2) is None


def test_viewer_session_denied_after_grant_revoked(
    scratch_db: sa.Engine,
) -> None:
    apply_admin_schema(scratch_db)
    identity = AdminIdentity(scratch_db)
    identity.bootstrap_owner("Owner", EMAIL)
    auth = AdminAuth(scratch_db, base_url=BASE_URL)
    with scratch_db.begin() as conn:
        owner_id = conn.execute(
            sa.text("SELECT id FROM admin_user WHERE role = 'owner'")
        ).scalar_one()
        viewer_id = uuid.uuid4()
        request_id = uuid.uuid4()
        conn.execute(
            sa.text(
                "INSERT INTO admin_access_request"
                " (id, display_name, email, status, verified_at,"
                "  decided_at, decided_by)"
                " VALUES (:id, 'Viewer', 'v@example.test', 'approved',"
                "  now(), now(), :owner)"
            ),
            {"id": request_id, "owner": owner_id},
        )
        conn.execute(
            sa.text(
                "INSERT INTO admin_user (id, role, display_name, email)"
                " VALUES (:id, 'viewer', 'Viewer', 'v@example.test')"
            ),
            {"id": viewer_id},
        )
        grant_id = uuid.uuid4()
        conn.execute(
            sa.text(
                "INSERT INTO admin_viewer_grant"
                " (id, request_id, user_id, granted_by, expires_at)"
                " VALUES (:id, :request, :user, :owner,"
                "  now() + interval '30 days')"
            ),
            {
                "id": grant_id,
                "request": request_id,
                "user": viewer_id,
                "owner": owner_id,
            },
        )
    raw = _raw_sign_in_token(auth, "v@example.test")
    session, principal = auth.exchange(raw)
    assert principal.role == "viewer"
    assert auth.resolve(session) is not None
    with scratch_db.begin() as conn:
        conn.execute(
            sa.text(
                "UPDATE admin_viewer_grant SET revoked_at = now(),"
                " revoked_by = :owner WHERE id = :id"
            ),
            {"owner": owner_id, "id": grant_id},
        )
    # Revocation applies to the very next request.
    assert auth.resolve(session) is None


def test_prune_expired(
    services: tuple[AdminAuth, AdminIdentity, RateLimiter],
) -> None:
    auth, _, _ = services
    raw = _raw_sign_in_token(auth)
    auth.exchange(raw)
    assert auth.prune_expired() == 0
    with auth.engine.begin() as conn:
        conn.execute(
            sa.text(
                "UPDATE admin_token SET created_at = now() - interval '3 days',"
                " expires_at = now() - interval '2 days'"
            )
        )
        conn.execute(
            sa.text(
                "UPDATE admin_session SET created_at = now() - interval '3 days',"
                " last_seen_at = now() - interval '3 days',"
                " expires_at = now() - interval '2 days'"
            )
        )
    assert auth.prune_expired() == 2


def test_local_mailbox_and_outbox_drain(
    services: tuple[AdminAuth, AdminIdentity, RateLimiter], tmp_path: Path
) -> None:
    auth, _, _ = services
    auth.request_sign_in(EMAIL)
    mailbox = LocalMailbox(str(tmp_path / "mail"))
    mailer = OutboxMailer(auth.engine, mailbox)
    assert mailer.send_pending() == 1
    files = list(tmp_path.glob("mail/*.eml"))
    assert len(files) == 1
    assert EMAIL in files[0].read_text()
    rows = _outbox(auth.engine)
    assert rows[0].status == "sent" and mailer.send_pending() == 0


def test_outbox_retry_then_terminal_failure(
    services: tuple[AdminAuth, AdminIdentity, RateLimiter],
) -> None:
    auth, _, _ = services
    auth.request_sign_in(EMAIL)

    class Broken:
        def send(self, *_args: str) -> None:
            raise OSError("smtp down")

    mailer = OutboxMailer(auth.engine, Broken(), max_attempts=2)
    mailer.send_pending()
    with auth.engine.connect() as conn:
        row = conn.execute(
            sa.text("SELECT status, attempts, available_at FROM admin_email_outbox")
        ).one()
    assert row.status == "pending" and row.attempts == 1
    assert row.available_at > datetime.now(UTC)
    # Force the retry to be due, then it terminally fails.
    with auth.engine.begin() as conn:
        conn.execute(
            sa.text(
                "UPDATE admin_email_outbox SET available_at = now() - interval '1s'"
            )
        )
    mailer.send_pending()
    with auth.engine.connect() as conn:
        row = conn.execute(
            sa.text("SELECT status, attempts, diagnostic FROM admin_email_outbox")
        ).one()
    assert row.status == "failed" and row.attempts == 2
    assert row.diagnostic == "OSError"


def test_rate_limiter_window_and_prune(
    services: tuple[AdminAuth, AdminIdentity, RateLimiter],
) -> None:
    _, _, limits = services
    assert all(limits.hit("b", "s", 3, 3600) for _ in range(3))
    assert not limits.hit("b", "s", 3, 3600)
    assert limits.hit("b", "other", 3, 3600)
    with limits.engine.begin() as conn:
        conn.execute(
            sa.text(
                "UPDATE admin_rate_limit SET window_start = now() - interval '3 days'"
            )
        )
    # Two (bucket, subject, window) rows exist; both are past the cutoff.
    assert limits.prune() == 2


def test_seed_session_dev_only(
    scratch_db: sa.Engine,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from nemlab_infrastructure.admin.__main__ import main

    apply_admin_schema(scratch_db)
    AdminIdentity(scratch_db).bootstrap_owner("Owner", EMAIL)
    db_name = scratch_db.url.database
    assert db_name is not None
    from nemlab_infrastructure.settings import DatabaseSettings

    base = DatabaseSettings()
    monkeypatch.setenv("NEMLAB_DB_URL", base.db_url.rsplit("/", 1)[0] + "/" + db_name)
    monkeypatch.setenv("NEMLAB_DB_USER", base.db_user)
    monkeypatch.setenv("NEMLAB_DB_PASSWORD", base.db_password)
    monkeypatch.delenv("NEMLAB_ENVIRONMENT", raising=False)
    assert main(["seed-session", "--email", EMAIL]) == 2
    assert "development" in capsys.readouterr().err
    monkeypatch.setenv("NEMLAB_ENVIRONMENT", "development")
    assert main(["seed-session", "--email", EMAIL]) == 0
    out = capsys.readouterr().out
    assert "token:" in out and "csrf:" in out
    assert main(["seed-session", "--email", "nobody@example.test"]) == 2
