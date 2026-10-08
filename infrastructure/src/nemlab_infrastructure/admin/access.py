"""``AccessRequests`` — request/verification/grant lifecycle (NEM-098).

Submission stays deliberately generic: an existing undecided request for
the normalised email resends its verification mail instead of creating a
second row, and every response shape is the same whether the address is
new, pending, approved or rejected. Verification consumes a single-use
24-hour ``request_verification`` token, flips the request to ``pending``
and opens an applicant session — verification never grants operational
access. Owner decisions lock the request row, check its optimistic
``version`` and write grant/user/outbox/audit in one transaction, so a
lost response or racing second decision surfaces as a conflict rather
than a duplicate grant. Grants live on ``admin_viewer_grant`` (no
version column): stale extend/revoke attempts lose to the atomic
``revoked_at IS NULL`` guard.

Retention follows the accepted defaults — unverified requests 7 days,
rejected requests 30 days, decision messages scrubbed after 30 days,
lapsed visitor contact data pseudonymised after 90 days, access audit
180 days — applied destructively only where the spec says data is
removed; approved requests and their grants are referential evidence and
keep their rows.
"""

import hashlib
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast
from uuid import UUID

import sqlalchemy as sa

from nemlab_infrastructure.admin.auth import (
    REQUEST_TOKEN_TTL,
    SESSION_LIFE,
    AdminAuth,
    InvalidToken,
    Principal,
    audit_event,
    create_session,
    mint,
    queue_mail,
)

DURATION_DAYS = (7, 30, 90)
UNVERIFIED_KEEP = timedelta(days=7)
REJECTED_KEEP = timedelta(days=30)
MESSAGE_KEEP = timedelta(days=30)
LAPSED_CONTACT_KEEP = timedelta(days=90)
AUDIT_KEEP = timedelta(days=180)

_EMAIL = re.compile(r"[^@\s]+@[^@\s]+")
_PAGE = 100


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


class AccessNotFound(Exception):
    pass


class AccessConflict(Exception):
    """Stale version, already-decided request or lapsed grant — map to 409."""


@dataclass(frozen=True)
class AccessRequest:
    id: UUID
    name: str
    email: str
    message: str | None
    status: str
    submitted_at: datetime
    verified_at: datetime | None
    decided_at: datetime | None
    version: int


@dataclass(frozen=True)
class ViewerGrant:
    id: UUID
    request_id: UUID
    user_id: UUID
    email: str
    granted_at: datetime
    expires_at: datetime
    revoked_at: datetime | None


def _request(row: sa.engine.Row[Any]) -> AccessRequest:
    return AccessRequest(
        row.id,
        row.display_name,
        row.email,
        row.message,
        row.status,
        row.submitted_at,
        row.verified_at,
        row.decided_at,
        row.version,
    )


_REQUEST_SELECT = (
    "SELECT id, display_name, email, message, status, submitted_at,"
    " verified_at, decided_at, version FROM admin_access_request"
)


def validate_fields(name: str, email: str, message: str | None) -> None:
    if not 1 <= len(name.strip()) <= 100:
        raise ValueError("Name must be 1-100 non-blank characters")
    if len(email) > 254 or _EMAIL.fullmatch(email) is None:
        raise ValueError("Invalid email address")
    if message is not None and len(message) > 1000:
        raise ValueError("Message must be at most 1000 characters")


class AccessRequests:
    def __init__(
        self,
        engine: sa.engine.Engine,
        auth: AdminAuth | None = None,
        *,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.engine = engine
        self.auth = auth
        self._now = now

    # -- visitor submission and verification --------------------------------

    def submit(self, name: str, email: str, message: str | None) -> None:
        """Create an unverified request + verification mail, or resend the
        verification for an existing unverified request. Decided and
        pending submissions are silently accepted (generic response)."""
        try:
            with self.engine.begin() as conn:
                self._submit(conn, name, email, message)
        except sa.exc.IntegrityError:
            # A concurrent submission won the undecided-email index; treat
            # it exactly like a duplicate submission.
            with self.engine.begin() as conn:
                existing = self._undecided(conn, email)
                if existing is not None and existing.status == "unverified":
                    self._send_verification(conn, existing, self._now())

    def _submit(
        self, conn: sa.Connection, name: str, email: str, message: str | None
    ) -> None:
        existing = self._undecided(conn, email)
        if existing is not None:
            if existing.status == "unverified":
                self._send_verification(conn, existing, self._now())
            return
        request_id = uuid.uuid4()
        conn.execute(
            sa.text(
                "INSERT INTO admin_access_request"
                " (id, display_name, email, message, status)"
                " VALUES (:id, :name, :email, :message, 'unverified')"
            ),
            {
                "id": request_id,
                "name": name.strip(),
                "email": email,
                "message": message,
            },
        )
        request = self._find(conn, request_id)
        if request is None:
            raise RuntimeError("inserted access request missing")
        self._send_verification(conn, request, self._now())

    def _undecided(self, conn: sa.Connection, email: str) -> AccessRequest | None:
        row = conn.execute(
            sa.text(
                _REQUEST_SELECT
                + " WHERE lower(email) = lower(:email)"
                + " AND status IN ('unverified', 'pending') FOR UPDATE"
            ),
            {"email": email},
        ).first()
        return _request(row) if row is not None else None

    def _send_verification(
        self, conn: sa.Connection, request: AccessRequest, now: datetime
    ) -> None:
        if self.auth is None:
            raise RuntimeError("verification links need an AdminAuth")
        token_id = uuid.uuid4()
        raw = mint()
        conn.execute(
            sa.text(
                "INSERT INTO admin_token"
                " (id, purpose, request_id, token_hash, expires_at)"
                " VALUES (:id, 'request_verification', :request, :hash, :expires)"
            ),
            {
                "id": token_id,
                "request": request.id,
                "hash": _hash(raw),
                "expires": now + REQUEST_TOKEN_TTL,
            },
        )
        link = f"{self.auth.base_url}/verify#token={raw}"
        queue_mail(
            conn,
            recipient=request.email,
            kind="request_verification",
            subject="Verify your NEMLab Admin access request",
            body=(
                "Confirm your access request for NEMLab Admin:\n\n"
                f"{link}\n\n"
                "This link expires in 24 hours and can be used once."
                " If you did not request access, ignore this message.\n"
            ),
            dedupe_key=f"{request.id}:verify:{token_id}",
        )

    def verify(self, raw_token: str) -> tuple[str, Principal]:
        """Consume a verification token: request becomes ``pending`` and an
        applicant session opens. All failure reasons raise ``InvalidToken``."""
        now = self._now()
        with self.engine.begin() as conn:
            row = conn.execute(
                sa.text(
                    "SELECT t.id, t.consumed_at, t.expires_at,"
                    " r.id AS request_id, r.status"
                    " FROM admin_token t"
                    " JOIN admin_access_request r ON r.id = t.request_id"
                    " WHERE t.token_hash = :hash"
                    " AND t.purpose = 'request_verification'"
                    " FOR UPDATE OF t, r"
                ),
                {"hash": _hash(raw_token)},
            ).first()
            if (
                row is None
                or row.consumed_at is not None
                or row.expires_at <= now
                or row.status != "unverified"
            ):
                raise InvalidToken
            conn.execute(
                sa.text("UPDATE admin_token SET consumed_at = :now WHERE id = :id"),
                {"now": now, "id": row.id},
            )
            conn.execute(
                sa.text(
                    "UPDATE admin_access_request SET status = 'pending',"
                    " verified_at = :now, version = version + 1 WHERE id = :id"
                ),
                {"now": now, "id": row.request_id},
            )
            raw_session = create_session(conn, request_id=row.request_id, now=now)
            session_id: UUID = conn.execute(
                sa.text("SELECT id FROM admin_session WHERE token_hash = :hash"),
                {"hash": _hash(raw_session)},
            ).scalar_one()
            audit_event(
                conn,
                actor_user_id=None,
                actor_label="applicant",
                action="REQUEST_VERIFIED",
                subject=f"request:{row.request_id}",
            )
            principal = Principal(
                session_id=session_id,
                user_id=None,
                request_id=row.request_id,
                role="applicant",
                name="applicant",
                expires_at=now + SESSION_LIFE,
                authenticated_at=now,
            )
            return raw_session, principal

    def status(self, request_id: UUID) -> dict[str, Any] | None:
        """Applicant-only view of their own request."""
        with self.engine.connect() as conn:
            request = self._find(conn, request_id)
            if request is None:
                return None
            body: dict[str, Any] = {
                "status": request.status,
                "submittedAt": request.submitted_at,
                "verifiedAt": request.verified_at,
                "decidedAt": request.decided_at,
            }
            grant = conn.execute(
                sa.text(
                    "SELECT expires_at FROM admin_viewer_grant"
                    " WHERE request_id = :id AND revoked_at IS NULL"
                    " AND expires_at > now()"
                ),
                {"id": request_id},
            ).first()
            body["grantExpiresAt"] = grant.expires_at if grant else None
            return body

    # -- owner queue and decisions -------------------------------------------

    def queue(self, limit: int = _PAGE) -> list[AccessRequest]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.text(
                    _REQUEST_SELECT
                    + " WHERE status = 'pending' ORDER BY submitted_at, id"
                    + " LIMIT :limit"
                ),
                {"limit": min(limit, _PAGE)},
            ).all()
            return [_request(row) for row in rows]

    def find(self, request_id: UUID) -> AccessRequest | None:
        with self.engine.connect() as conn:
            return self._find(conn, request_id)

    def _find(self, conn: sa.Connection, request_id: UUID) -> AccessRequest | None:
        row = conn.execute(
            sa.text(_REQUEST_SELECT + " WHERE id = :id"),
            {"id": request_id},
        ).first()
        return _request(row) if row is not None else None

    def deliveries(self, request_id: UUID) -> list[dict[str, Any]]:
        """Outbox rows linked to a request via its dedupe-key prefix — the
        owner's visibility into delivery state and failures."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT kind, status, attempts, sent_at, diagnostic, created_at"
                    " FROM admin_email_outbox WHERE dedupe_key LIKE :prefix"
                    " ORDER BY created_at, id"
                ),
                {"prefix": f"{request_id}:%"},
            ).all()
            return [
                {
                    "kind": row.kind,
                    "status": row.status,
                    "attempts": row.attempts,
                    "sentAt": row.sent_at,
                    "diagnostic": row.diagnostic,
                    "createdAt": row.created_at,
                }
                for row in rows
            ]

    def decide(
        self,
        request_id: UUID,
        action: Literal["approve", "reject"],
        days: int | None,
        version: int,
        owner_id: UUID,
    ) -> AccessRequest:
        """Atomic decision: pending -> approved (viewer user + grant +
        sign-in invite) or rejected. ``version`` is the optimistic check —
        concurrent or replayed decisions conflict instead of duplicating."""
        if action == "approve" and days not in DURATION_DAYS:
            raise ValueError("Approval duration must be 7, 30 or 90 days")
        now = self._now()
        with self.engine.begin() as conn:
            row = conn.execute(
                sa.text(_REQUEST_SELECT + " WHERE id = :id FOR UPDATE"),
                {"id": request_id},
            ).first()
            if row is None:
                raise AccessNotFound
            request = _request(row)
            if request.status != "pending" or request.version != version:
                raise AccessConflict
            if action == "reject":
                self._decided(conn, request_id, "rejected", owner_id, now)
                audit_event(
                    conn,
                    actor_user_id=owner_id,
                    actor_label="owner",
                    action="REQUEST_REJECTED",
                    subject=f"request:{request_id}",
                )
            else:
                if days is None:
                    raise ValueError("Approval duration must be 7, 30 or 90 days")
                user_id = self._viewer_user(conn, request, now)
                grant_id = uuid.uuid4()
                conn.execute(
                    sa.text(
                        "INSERT INTO admin_viewer_grant"
                        " (id, request_id, user_id, granted_by, expires_at)"
                        " VALUES (:id, :request, :user, :owner,"
                        " now() + make_interval(days => :days))"
                    ),
                    {
                        "id": grant_id,
                        "request": request_id,
                        "user": user_id,
                        "owner": owner_id,
                        "days": days,
                    },
                )
                self._decided(conn, request_id, "approved", owner_id, now)
                if self.auth is None:
                    raise RuntimeError("sign-in invites need an AdminAuth")
                self.auth.queue_sign_in(
                    conn,
                    user_id=user_id,
                    email=request.email,
                    now=now,
                    # Request-linked dedupe key makes the invite's delivery
                    # state visible on the owner request detail.
                    dedupe_key=f"{request_id}:invite:{uuid.uuid4()}",
                )
                audit_event(
                    conn,
                    actor_user_id=owner_id,
                    actor_label="owner",
                    action="REQUEST_APPROVED",
                    subject=f"request:{request_id}",
                )
                audit_event(
                    conn,
                    actor_user_id=owner_id,
                    actor_label="owner",
                    action="GRANT_CREATED",
                    subject=f"grant:{grant_id}",
                )
            decided = self._find(conn, request_id)
            if decided is None:
                raise RuntimeError("decided request missing")
            return decided

    @staticmethod
    def _decided(
        conn: sa.Connection,
        request_id: UUID,
        status: str,
        owner_id: UUID,
        now: datetime,
    ) -> None:
        conn.execute(
            sa.text(
                "UPDATE admin_access_request SET status = :status,"
                " decided_at = :now, decided_by = :owner,"
                " version = version + 1 WHERE id = :id"
            ),
            {"status": status, "now": now, "owner": owner_id, "id": request_id},
        )

    @staticmethod
    def _viewer_user(
        conn: sa.Connection, request: AccessRequest, now: datetime
    ) -> UUID:
        """Find-or-create the viewer account for an approved email. The
        global case-insensitive unique index means a disabled row must be
        re-enabled rather than duplicated."""
        row = conn.execute(
            sa.text(
                "SELECT id, role, disabled_at FROM admin_user"
                " WHERE lower(email) = lower(:email)"
            ),
            {"email": request.email},
        ).first()
        if row is not None:
            if row.disabled_at is not None:
                conn.execute(
                    sa.text("UPDATE admin_user SET disabled_at = NULL WHERE id = :id"),
                    {"id": row.id},
                )
            return cast(UUID, row.id)
        user_id = uuid.uuid4()
        conn.execute(
            sa.text(
                "INSERT INTO admin_user (id, role, display_name, email)"
                " VALUES (:id, 'viewer', :name, :email)"
            ),
            {"id": user_id, "name": request.name, "email": request.email},
        )
        return user_id

    # -- grants ---------------------------------------------------------------

    def grants(
        self, state: Literal["active", "expired", "revoked"] | None, limit: int = _PAGE
    ) -> list[ViewerGrant]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT g.id, g.request_id, g.user_id, u.email,"
                    " g.granted_at, g.expires_at, g.revoked_at"
                    " FROM admin_viewer_grant g"
                    " JOIN admin_user u ON u.id = g.user_id"
                    " WHERE CAST(:state AS text) IS NULL"
                    " OR (:state = 'active' AND g.revoked_at IS NULL"
                    "     AND g.expires_at > now())"
                    " OR (:state = 'expired' AND g.revoked_at IS NULL"
                    "     AND g.expires_at <= now())"
                    " OR (:state = 'revoked' AND g.revoked_at IS NOT NULL)"
                    " ORDER BY g.granted_at DESC, g.id LIMIT :limit"
                ),
                {"state": state, "limit": min(limit, _PAGE)},
            ).all()
            return [
                ViewerGrant(
                    row.id,
                    row.request_id,
                    row.user_id,
                    row.email,
                    row.granted_at,
                    row.expires_at,
                    row.revoked_at,
                )
                for row in rows
            ]

    def audit(self, limit: int = _PAGE) -> list[dict[str, Any]]:
        """Recent access-audit rows for the owner's audit view — newest
        first, bounded. Retention deletes beyond the kept window."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT occurred_at, actor_label, action, subject, result"
                    " FROM admin_access_audit"
                    " ORDER BY occurred_at DESC, id LIMIT :limit"
                ),
                {"limit": min(limit, _PAGE)},
            ).all()
            return [
                {
                    "occurredAt": row.occurred_at,
                    "actor": row.actor_label,
                    "action": row.action,
                    "subject": row.subject,
                    "result": row.result,
                }
                for row in rows
            ]

    def extend(self, grant_id: UUID, days: int, owner_id: UUID) -> ViewerGrant:
        if days not in DURATION_DAYS:
            raise ValueError("Extension must be 7, 30 or 90 days")
        with self.engine.begin() as conn:
            updated = conn.execute(
                sa.text(
                    "UPDATE admin_viewer_grant"
                    " SET expires_at = greatest(expires_at, now())"
                    " + make_interval(days => :days)"
                    " WHERE id = :id AND revoked_at IS NULL"
                    " RETURNING id, request_id, user_id, granted_at, expires_at,"
                    " revoked_at"
                ),
                {"days": days, "id": grant_id},
            ).first()
            if updated is None:
                if not self._grant_exists(conn, grant_id):
                    raise AccessNotFound
                raise AccessConflict
            email = self._user_email(conn, updated.user_id)
            audit_event(
                conn,
                actor_user_id=owner_id,
                actor_label="owner",
                action="GRANT_EXTENDED",
                subject=f"grant:{grant_id}",
            )
            return ViewerGrant(
                updated.id,
                updated.request_id,
                updated.user_id,
                email,
                updated.granted_at,
                updated.expires_at,
                updated.revoked_at,
            )

    def revoke(self, grant_id: UUID, owner_id: UUID, reason: str | None) -> ViewerGrant:
        now = self._now()
        with self.engine.begin() as conn:
            updated = conn.execute(
                sa.text(
                    "UPDATE admin_viewer_grant"
                    " SET revoked_at = :now, revoked_by = :owner"
                    " WHERE id = :id AND revoked_at IS NULL"
                    " RETURNING id, request_id, user_id, granted_at, expires_at,"
                    " revoked_at"
                ),
                {"now": now, "owner": owner_id, "id": grant_id},
            ).first()
            if updated is None:
                if not self._grant_exists(conn, grant_id):
                    raise AccessNotFound
                raise AccessConflict
            conn.execute(
                sa.text(
                    "UPDATE admin_session SET revoked_at = :now"
                    " WHERE user_id = :user AND revoked_at IS NULL"
                ),
                {"now": now, "user": updated.user_id},
            )
            audit_event(
                conn,
                actor_user_id=owner_id,
                actor_label="owner",
                action="GRANT_REVOKED",
                subject=f"grant:{grant_id}",
            )
            email = self._user_email(conn, updated.user_id)
            return ViewerGrant(
                updated.id,
                updated.request_id,
                updated.user_id,
                email,
                updated.granted_at,
                updated.expires_at,
                updated.revoked_at,
            )

    def resend_own(self, request_id: UUID) -> None:
        """Applicant self-service resend — only while still unverified;
        any other state is a silent no-op (the route answers 202 anyway)."""
        now = self._now()
        with self.engine.begin() as conn:
            request = self._find(conn, request_id)
            if request is not None and request.status == "unverified":
                self._send_verification(conn, request, now)

    def resend(self, request_id: UUID, owner_id: UUID) -> None:
        """Re-queue the delivery for an unverified request (verification)
        or an approved one (sign-in invite); pending/rejected conflict."""
        now = self._now()
        with self.engine.begin() as conn:
            request = self._find(conn, request_id)
            if request is None:
                raise AccessNotFound
            if request.status == "unverified":
                self._send_verification(conn, request, now)
            elif request.status == "approved":
                row = conn.execute(
                    sa.text(
                        "SELECT u.id, u.email FROM admin_viewer_grant g"
                        " JOIN admin_user u ON u.id = g.user_id"
                        " WHERE g.request_id = :id"
                    ),
                    {"id": request_id},
                ).first()
                if row is None:
                    raise AccessConflict
                if self.auth is None:
                    raise RuntimeError("invite resends need an AdminAuth")
                self.auth.queue_sign_in(
                    conn,
                    user_id=row.id,
                    email=row.email,
                    now=now,
                    dedupe_key=f"{request_id}:invite:{uuid.uuid4()}",
                )
            else:
                raise AccessConflict
            audit_event(
                conn,
                actor_user_id=owner_id,
                actor_label="owner",
                action="DELIVERY_RESENT",
                subject=f"request:{request_id}",
            )

    @staticmethod
    def _grant_exists(conn: sa.Connection, grant_id: UUID) -> bool:
        return bool(
            conn.execute(
                sa.text("SELECT count(*) FROM admin_viewer_grant WHERE id = :id"),
                {"id": grant_id},
            ).scalar_one()
        )

    @staticmethod
    def _user_email(conn: sa.Connection, user_id: UUID) -> str:
        return str(
            conn.execute(
                sa.text("SELECT email FROM admin_user WHERE id = :id"),
                {"id": user_id},
            ).scalar_one()
        )

    # -- retention ------------------------------------------------------------

    def prune(self) -> dict[str, int]:
        """Retention cleanup per the accepted defaults. Removes rows the
        spec says to delete and pseudonymises lapsed visitor contact data;
        approved requests and grant rows stay as referential evidence."""
        now = self._now()
        counts = {"requests": 0, "messages": 0, "contacts": 0, "audit": 0}
        with self.engine.begin() as conn:
            stale = conn.execute(
                sa.text(
                    "SELECT id FROM admin_access_request"
                    " WHERE (status = 'unverified' AND submitted_at < :unverified)"
                    " OR (status = 'rejected' AND decided_at < :rejected)"
                ),
                {
                    "unverified": now - UNVERIFIED_KEEP,
                    "rejected": now - REJECTED_KEEP,
                },
            ).all()
            for row in stale:
                conn.execute(
                    sa.text("DELETE FROM admin_token WHERE request_id = :id"),
                    {"id": row.id},
                )
                conn.execute(
                    sa.text("DELETE FROM admin_session WHERE request_id = :id"),
                    {"id": row.id},
                )
                conn.execute(
                    sa.text("DELETE FROM admin_access_request WHERE id = :id"),
                    {"id": row.id},
                )
                counts["requests"] += 1
            counts["messages"] = conn.execute(
                sa.text(
                    "UPDATE admin_access_request SET message = NULL"
                    " WHERE message IS NOT NULL AND decided_at < :cutoff"
                ),
                {"cutoff": now - MESSAGE_KEEP},
            ).rowcount
            # Lapsed-visitor contact data: viewers with no active grant and
            # no grant that ended within the 90-day window are disabled and
            # pseudonymised (account + request emails), preserving rows for
            # referential integrity while removing contact details.
            lapsed = now - LAPSED_CONTACT_KEEP
            counts["contacts"] = conn.execute(
                sa.text(
                    "UPDATE admin_user SET"
                    " email = 'removed-' || id || '@removed.invalid',"
                    " disabled_at = coalesce(disabled_at, now())"
                    " WHERE role = 'viewer'"
                    " AND email NOT LIKE 'removed-%@removed.invalid'"
                    " AND NOT EXISTS ("
                    "  SELECT 1 FROM admin_viewer_grant g"
                    "  WHERE g.user_id = admin_user.id AND g.revoked_at IS NULL"
                    "  AND g.expires_at > now())"
                    " AND NOT EXISTS ("
                    "  SELECT 1 FROM admin_viewer_grant g"
                    "  WHERE g.user_id = admin_user.id"
                    "  AND coalesce(g.revoked_at, g.expires_at) > :lapsed)"
                ),
                {"lapsed": lapsed},
            ).rowcount
            counts["contacts"] += conn.execute(
                sa.text(
                    "UPDATE admin_access_request r SET"
                    " email = 'removed-' || r.id || '@removed.invalid',"
                    " display_name = 'Removed visitor', message = NULL"
                    " WHERE r.status = 'approved'"
                    " AND r.email NOT LIKE 'removed-%@removed.invalid'"
                    " AND NOT EXISTS ("
                    "  SELECT 1 FROM admin_viewer_grant g"
                    "  WHERE g.request_id = r.id"
                    "  AND coalesce(g.revoked_at, g.expires_at) > :lapsed)"
                ),
                {"lapsed": lapsed},
            ).rowcount
            counts["audit"] = conn.execute(
                sa.text("DELETE FROM admin_access_audit WHERE occurred_at < :cutoff"),
                {"cutoff": now - AUDIT_KEEP},
            ).rowcount
        return counts
