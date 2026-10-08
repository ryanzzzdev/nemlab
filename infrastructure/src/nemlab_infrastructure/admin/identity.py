"""``AdminIdentity`` — owner bootstrap and recovery over the V8 schema.

Only the owner lifecycle lives here for NEM-095; sessions, tokens, access
requests, grants and the email outbox are written by later M6 tasks onto
the same tables. Bootstrap is CLI-only by design — no public route exists.
"""

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa

_EMAIL = re.compile(r"[^@\s]+@[^@\s]+")


class OwnerExists(RuntimeError):
    """An enabled owner already exists under a different email."""


@dataclass(frozen=True)
class AdminUser:
    id: UUID
    role: str
    display_name: str
    email: str
    created_at: datetime
    disabled_at: datetime | None


def _validate_name(name: str) -> None:
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
        raise ValueError("Owner name must be 1-100 non-blank characters")


def _validate_email(email: str) -> None:
    if (
        not isinstance(email, str)
        or len(email) > 254
        or _EMAIL.fullmatch(email) is None
    ):
        raise ValueError("Invalid email address")


def _validate_reason(reason: str) -> None:
    if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 500:
        raise ValueError("Recovery reason must be 1-500 non-blank characters")


class AdminIdentity:
    def __init__(self, engine: sa.engine.Engine) -> None:
        self.engine = engine

    def owner(self) -> AdminUser | None:
        """The enabled owner, or ``None`` before bootstrap."""
        with self.engine.connect() as conn:
            return self._enabled_owner(conn)

    def bootstrap_owner(self, name: str, email: str) -> tuple[AdminUser, bool]:
        """Create the single enabled owner. Idempotent: a repeated or
        concurrently-losing run for the same email returns the existing
        row; a different email requires the audited recovery path."""
        _validate_name(name)
        _validate_email(email)
        try:
            with self.engine.begin() as conn:
                existing = self._enabled_owner(conn)
                if existing is not None:
                    if existing.email.lower() == email.lower():
                        return existing, False
                    raise OwnerExists(
                        "an enabled owner already exists; use recover-owner"
                    )
                return (
                    self._insert_owner(
                        conn, name, email, action="OWNER_BOOTSTRAPPED", detail=None
                    ),
                    True,
                )
        except sa.exc.IntegrityError:
            # A concurrent bootstrap won the single-owner index; the
            # winner's row decides whether this was an idempotent replay.
            existing = self.owner()
            if existing is None:
                raise
            if existing.email.lower() == email.lower():
                return existing, False
            raise OwnerExists(
                "an enabled owner already exists; use recover-owner"
            ) from None

    def recover_owner(self, name: str, email: str, reason: str) -> AdminUser:
        """Audited server-side recovery: disables any enabled owner and
        revokes its sessions, then creates the replacement owner."""
        _validate_name(name)
        _validate_email(email)
        _validate_reason(reason)
        with self.engine.begin() as conn:
            previous = self._enabled_owner(conn)
            if previous is not None:
                conn.execute(
                    sa.text("UPDATE admin_user SET disabled_at = now() WHERE id = :id"),
                    {"id": previous.id},
                )
                revoked = conn.execute(
                    sa.text(
                        "UPDATE admin_session SET revoked_at = now()"
                        " WHERE user_id = :id AND revoked_at IS NULL"
                    ),
                    {"id": previous.id},
                ).rowcount
                self._audit(
                    conn,
                    actor_user_id=None,
                    actor_label="recovery",
                    action="OWNER_DISABLED",
                    subject=f"user:{previous.id}",
                    result="applied",
                    detail={"reason": reason.strip(), "sessionsRevoked": revoked},
                )
            return self._insert_owner(
                conn,
                name,
                email,
                action="OWNER_RECOVERED",
                detail={
                    "reason": reason.strip(),
                    "replaces": str(previous.id) if previous is not None else None,
                },
            )

    # -- internals ----------------------------------------------------------

    def _enabled_owner(self, conn: sa.Connection) -> AdminUser | None:
        row = conn.execute(
            sa.text(
                "SELECT id, role, display_name, email, created_at, disabled_at"
                " FROM admin_user"
                " WHERE role = 'owner' AND disabled_at IS NULL"
            )
        ).first()
        return self._user(row) if row is not None else None

    @staticmethod
    def _user(row: sa.engine.Row[Any]) -> AdminUser:
        return AdminUser(
            row.id,
            row.role,
            row.display_name,
            row.email,
            row.created_at,
            row.disabled_at,
        )

    def _insert_owner(
        self,
        conn: sa.Connection,
        name: str,
        email: str,
        *,
        action: str,
        detail: dict[str, Any] | None,
    ) -> AdminUser:
        id = uuid.uuid4()
        created: datetime = conn.execute(
            sa.text(
                "INSERT INTO admin_user (id, role, display_name, email)"
                " VALUES (:id, 'owner', :name, :email) RETURNING created_at"
            ),
            {"id": id, "name": name.strip(), "email": email},
        ).scalar_one()
        self._audit(
            conn,
            actor_user_id=id,
            actor_label="owner",
            action=action,
            subject=f"user:{id}",
            result="applied",
            detail=detail,
        )
        return AdminUser(id, "owner", name.strip(), email, created, None)

    def _audit(
        self,
        conn: sa.Connection,
        *,
        actor_user_id: UUID | None,
        actor_label: str,
        action: str,
        subject: str,
        result: str,
        detail: dict[str, Any] | None,
    ) -> None:
        conn.execute(
            sa.text(
                "INSERT INTO admin_access_audit"
                " (actor_user_id, actor_label, action, subject, result, detail)"
                " VALUES (:actor, :label, :action, :subject, :result,"
                " CAST(:detail AS jsonb))"
            ),
            {
                "actor": actor_user_id,
                "label": actor_label,
                "action": action,
                "subject": subject,
                "result": result,
                "detail": json.dumps(detail) if detail is not None else None,
            },
        )
