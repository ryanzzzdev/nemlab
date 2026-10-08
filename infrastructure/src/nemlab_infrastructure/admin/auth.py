"""``AdminAuth`` — sign-in tokens and opaque sessions over the V8 tables.

Raw secrets are minted with ``secrets.token_urlsafe``; only their SHA-256
hash persists (``admin_token``/``admin_session``). A session's CSRF token
is derived as ``sha256("csrf:" + raw)`` — a leaked database hash reveals
neither the session token nor the CSRF secret. Every exchange failure
raises the same ``InvalidToken`` so callers cannot distinguish unknown,
expired, replayed or disabled-subject tokens.
"""

import hashlib
import hmac
import secrets
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import sqlalchemy as sa

TOKEN_TTL = timedelta(minutes=15)
REQUEST_TOKEN_TTL = timedelta(hours=24)
SESSION_IDLE = timedelta(hours=24)
SESSION_LIFE = timedelta(hours=72)
MAX_TOKEN_LENGTH = 128


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def mint() -> str:
    """A 256-bit URL-safe secret (43 characters)."""
    return secrets.token_urlsafe(32)


def csrf_for(raw_session: str) -> str:
    return hashlib.sha256(f"csrf:{raw_session}".encode()).hexdigest()


def csrf_matches(raw_session: str, presented: str) -> bool:
    return hmac.compare_digest(csrf_for(raw_session), presented)


class InvalidToken(Exception):
    """Any token-exchange failure; deliberately reason-free."""


@dataclass(frozen=True)
class Principal:
    session_id: UUID
    user_id: UUID | None
    request_id: UUID | None
    role: str  # owner | viewer | applicant
    name: str
    expires_at: datetime
    authenticated_at: datetime


def create_session(
    conn: sa.Connection,
    *,
    user_id: UUID | None = None,
    request_id: UUID | None = None,
    now: datetime,
) -> str:
    raw = mint()
    conn.execute(
        sa.text(
            "INSERT INTO admin_session"
            " (id, user_id, request_id, token_hash, expires_at)"
            " VALUES (:id, :user, :request, :hash, :expires)"
        ),
        {
            "id": uuid.uuid4(),
            "user": user_id,
            "request": request_id,
            "hash": _hash(raw),
            "expires": now + SESSION_LIFE,
        },
    )
    return raw


def queue_mail(
    conn: sa.Connection,
    *,
    recipient: str,
    kind: str,
    subject: str,
    body: str,
    dedupe_key: str,
) -> None:
    conn.execute(
        sa.text(
            "INSERT INTO admin_email_outbox"
            " (id, recipient, kind, subject, body, dedupe_key)"
            " VALUES (:id, :recipient, :kind, :subject, :body, :dedupe)"
        ),
        {
            "id": uuid.uuid4(),
            "recipient": recipient,
            "kind": kind,
            "subject": subject,
            "body": body,
            "dedupe": dedupe_key,
        },
    )


def audit_event(
    conn: sa.Connection,
    *,
    actor_user_id: UUID | None,
    actor_label: str,
    action: str,
    subject: str | None,
) -> None:
    conn.execute(
        sa.text(
            "INSERT INTO admin_access_audit"
            " (actor_user_id, actor_label, action, subject, result)"
            " VALUES (:actor, :label, :action, :subject, 'applied')"
        ),
        {
            "actor": actor_user_id,
            "label": actor_label,
            "action": action,
            "subject": subject,
        },
    )


class AdminAuth:
    def __init__(
        self,
        engine: sa.engine.Engine,
        *,
        base_url: str,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.engine = engine
        self.base_url = base_url.rstrip("/")
        self._now = now

    # -- sign-in tokens -----------------------------------------------------

    def request_sign_in(self, email: str) -> bool:
        """Queue a sign-in email iff the address belongs to an enabled,
        grant-active account; ``False`` is silent — the HTTP layer always
        answers the same generic acceptance."""
        now = self._now()
        with self.engine.begin() as conn:
            row = conn.execute(
                sa.text(
                    "SELECT id, role, email FROM admin_user"
                    " WHERE lower(email) = lower(:email)"
                    " AND disabled_at IS NULL"
                ),
                {"email": email},
            ).first()
            if row is None or not self._grant_active(conn, row.id, row.role, now):
                return False
            self.queue_sign_in(conn, user_id=row.id, email=row.email, now=now)
            return True

    def queue_sign_in(
        self,
        conn: sa.Connection,
        *,
        user_id: UUID,
        email: str,
        now: datetime,
        dedupe_key: str | None = None,
    ) -> None:
        """Mint a 15-minute sign-in token and queue its email inside the
        caller's transaction — used by both sign-in requests and viewer
        approval so grant/token/outbox land atomically (NEM-098)."""
        token_id = uuid.uuid4()
        raw = mint()
        conn.execute(
            sa.text(
                "INSERT INTO admin_token"
                " (id, purpose, user_id, token_hash, expires_at)"
                " VALUES (:id, 'sign_in', :user, :hash, :expires)"
            ),
            {
                "id": token_id,
                "user": user_id,
                "hash": _hash(raw),
                "expires": now + TOKEN_TTL,
            },
        )
        link = f"{self.base_url}/sign-in#token={raw}"
        queue_mail(
            conn,
            recipient=email,
            kind="sign_in",
            subject="NEMLab Admin sign-in",
            body=(
                f"Sign in to NEMLab Admin:\n\n{link}\n\n"
                "This link expires in 15 minutes and can be used once."
                " If you did not request it, ignore this message.\n"
            ),
            dedupe_key=dedupe_key or f"sign_in:{token_id}",
        )

    def exchange(self, raw_token: str) -> tuple[str, Principal]:
        """Consume a sign-in token and open a session; returns the raw
        session secret and its principal."""
        if not raw_token or len(raw_token) > MAX_TOKEN_LENGTH:
            raise InvalidToken
        now = self._now()
        with self.engine.begin() as conn:
            row = conn.execute(
                sa.text(
                    "SELECT t.id, t.consumed_at, t.expires_at,"
                    " u.id AS user_id, u.role, u.display_name, u.disabled_at"
                    " FROM admin_token t JOIN admin_user u ON u.id = t.user_id"
                    " WHERE t.token_hash = :hash AND t.purpose = 'sign_in'"
                    " FOR UPDATE OF t"
                ),
                {"hash": _hash(raw_token)},
            ).first()
            if (
                row is None
                or row.consumed_at is not None
                or row.expires_at <= now
                or row.disabled_at is not None
                or not self._grant_active(conn, row.user_id, row.role, now)
            ):
                raise InvalidToken
            conn.execute(
                sa.text("UPDATE admin_token SET consumed_at = :now WHERE id = :id"),
                {"now": now, "id": row.id},
            )
            raw_session = create_session(conn, user_id=row.user_id, now=now)
            principal = Principal(
                session_id=self._session_id(conn, raw_session),
                user_id=row.user_id,
                request_id=None,
                role=row.role,
                name=row.display_name,
                expires_at=now + SESSION_LIFE,
                authenticated_at=now,
            )
            audit_event(
                conn,
                actor_user_id=row.user_id,
                actor_label=row.role,
                action="SESSION_STARTED",
                subject=f"user:{row.user_id}",
            )
            return raw_session, principal

    # -- sessions -----------------------------------------------------------

    def resolve(self, raw_session: str) -> Principal | None:
        """The live principal for a session cookie, or ``None``. Slides
        idle expiry forward; revocation, absolute/idle expiry, a disabled
        user and a lapsed viewer grant all deny — immediately."""
        if not raw_session or len(raw_session) > MAX_TOKEN_LENGTH:
            return None
        now = self._now()
        with self.engine.begin() as conn:
            row = conn.execute(
                sa.text(
                    "SELECT s.id, s.user_id, s.request_id, s.last_seen_at,"
                    " s.created_at, s.expires_at, s.revoked_at,"
                    " u.role, u.display_name, u.disabled_at"
                    " FROM admin_session s"
                    " LEFT JOIN admin_user u ON u.id = s.user_id"
                    " WHERE s.token_hash = :hash FOR UPDATE OF s"
                ),
                {"hash": _hash(raw_session)},
            ).first()
            if (
                row is None
                or row.revoked_at is not None
                or row.expires_at <= now
                or row.last_seen_at <= now - SESSION_IDLE
            ):
                return None
            if row.user_id is not None:
                if row.disabled_at is not None or not self._grant_active(
                    conn, row.user_id, row.role, now
                ):
                    self._revoke(conn, row.id, now)
                    return None
                role, name = row.role, row.display_name
            else:
                if not self._request_exists(conn, row.request_id):
                    return None
                role, name = "applicant", "applicant"
            conn.execute(
                sa.text("UPDATE admin_session SET last_seen_at = :now WHERE id = :id"),
                {"now": now, "id": row.id},
            )
            return Principal(
                row.id,
                row.user_id,
                row.request_id,
                role,
                name,
                row.expires_at,
                row.created_at,
            )

    def logout(self, raw_session: str) -> None:
        now = self._now()
        with self.engine.begin() as conn:
            conn.execute(
                sa.text(
                    "UPDATE admin_session SET revoked_at = :now"
                    " WHERE token_hash = :hash AND revoked_at IS NULL"
                ),
                {"now": now, "hash": _hash(raw_session)},
            )

    def seed_session(self, email: str) -> tuple[str, Principal]:
        """Development-only session creation — the CLI gates this behind
        ``NEMLAB_ENVIRONMENT=development``; never reachable over HTTP."""
        now = self._now()
        with self.engine.begin() as conn:
            row = conn.execute(
                sa.text(
                    "SELECT id, role, display_name FROM admin_user"
                    " WHERE lower(email) = lower(:email)"
                    " AND disabled_at IS NULL"
                ),
                {"email": email},
            ).first()
            if row is None or not self._grant_active(conn, row.id, row.role, now):
                raise ValueError("no enabled account for that email")
            raw = create_session(conn, user_id=row.id, now=now)
            return raw, Principal(
                self._session_id(conn, raw),
                row.id,
                None,
                row.role,
                row.display_name,
                now + SESSION_LIFE,
                now,
            )

    def mint_sign_in_link(self, email: str) -> str:
        """Development-only sign-in link — mints the usual single-use
        15-minute token but returns the URL instead of queueing mail. The
        CLI gates this behind ``NEMLAB_ENVIRONMENT=development``; never
        reachable over HTTP."""
        now = self._now()
        with self.engine.begin() as conn:
            row = conn.execute(
                sa.text(
                    "SELECT id, role FROM admin_user"
                    " WHERE lower(email) = lower(:email)"
                    " AND disabled_at IS NULL"
                ),
                {"email": email},
            ).first()
            if row is None or not self._grant_active(conn, row.id, row.role, now):
                raise ValueError("no enabled account for that email")
            raw = mint()
            conn.execute(
                sa.text(
                    "INSERT INTO admin_token"
                    " (id, purpose, user_id, token_hash, expires_at)"
                    " VALUES (:id, 'sign_in', :user, :hash, :expires)"
                ),
                {
                    "id": uuid.uuid4(),
                    "user": row.id,
                    "hash": _hash(raw),
                    "expires": now + TOKEN_TTL,
                },
            )
            return f"{self.base_url}/sign-in#token={raw}"

    def prune_expired(self, before: timedelta = timedelta(days=1)) -> int:
        """Retention housekeeping: drop tokens/sessions long past expiry."""
        cutoff = self._now() - before
        with self.engine.begin() as conn:
            removed = conn.execute(
                sa.text("DELETE FROM admin_token WHERE expires_at < :cutoff"),
                {"cutoff": cutoff},
            ).rowcount
            removed += conn.execute(
                sa.text(
                    "DELETE FROM admin_session WHERE expires_at < :cutoff"
                    " OR (revoked_at IS NOT NULL AND revoked_at < :cutoff)"
                ),
                {"cutoff": cutoff},
            ).rowcount
        return removed

    # -- internals ----------------------------------------------------------

    @staticmethod
    def _session_id(conn: sa.Connection, raw: str) -> UUID:
        return conn.execute(
            sa.text("SELECT id FROM admin_session WHERE token_hash = :hash"),
            {"hash": _hash(raw)},
        ).scalar_one()

    @staticmethod
    def _revoke(conn: sa.Connection, session_id: UUID, now: datetime) -> None:
        conn.execute(
            sa.text(
                "UPDATE admin_session SET revoked_at = :now"
                " WHERE id = :id AND revoked_at IS NULL"
            ),
            {"now": now, "id": session_id},
        )

    @staticmethod
    def _grant_active(
        conn: sa.Connection, user_id: UUID, role: str, now: datetime
    ) -> bool:
        if role != "viewer":
            return True
        return bool(
            conn.execute(
                sa.text(
                    "SELECT count(*) FROM admin_viewer_grant"
                    " WHERE user_id = :user AND revoked_at IS NULL"
                    " AND expires_at > :now"
                ),
                {"user": user_id, "now": now},
            ).scalar_one()
        )

    @staticmethod
    def _request_exists(conn: sa.Connection, request_id: UUID | None) -> bool:
        if request_id is None:
            return False
        return bool(
            conn.execute(
                sa.text("SELECT count(*) FROM admin_access_request WHERE id = :id"),
                {"id": request_id},
            ).scalar_one()
        )
