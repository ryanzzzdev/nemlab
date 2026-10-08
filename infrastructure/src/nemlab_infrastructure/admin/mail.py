"""Provider-neutral transactional mail over the durable ``admin_email_outbox``.

The only M6 transport is ``LocalMailbox`` — a captured mailbox that writes
one file per message, so development and tests never reach live recipients.
A real SMTP/provider transport is an M7 deployment input behind the same
``MailTransport`` protocol. ``OutboxMailer`` drains pending rows inside a
transaction with ``SKIP LOCKED`` so concurrent pollers cannot double-send;
failures retry with linear backoff and go terminally ``failed`` (with a
sanitised diagnostic — the exception class name, never the message).
"""

import logging
import re
import unicodedata
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

import sqlalchemy as sa

LOG = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
RETRY_SECONDS = 60
BATCH_LIMIT = 50


def _utc_now() -> datetime:
    return datetime.now(UTC)


class MailTransport(Protocol):
    def send(self, recipient: str, subject: str, body: str) -> None: ...


class LocalMailbox:
    """Captured-mail transport: one ``.eml``-style file per message."""

    def __init__(self, directory: str) -> None:
        self.directory = Path(directory)

    def send(self, recipient: str, subject: str, body: str) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
        slug = re.sub(
            r"[^A-Za-z0-9_.-]+",
            "_",
            unicodedata.normalize("NFKD", recipient)[:64],
        )
        path = self.directory / f"{stamp}-{slug}.eml"
        path.write_text(
            f"To: {recipient}\nSubject: {subject}\n\n{body}", encoding="utf-8"
        )


class OutboxMailer:
    """Polls ``admin_email_outbox`` and delivers through a transport."""

    def __init__(
        self,
        engine: sa.engine.Engine,
        transport: MailTransport,
        *,
        now: Callable[[], datetime] = _utc_now,
        max_attempts: int = MAX_ATTEMPTS,
    ) -> None:
        self.engine = engine
        self.transport = transport
        self._now = now
        self._max_attempts = max_attempts

    def send_pending(self, limit: int = BATCH_LIMIT) -> int:
        """Attempt up to ``limit`` due messages; returns the count tried."""
        now = self._now()
        with self.engine.begin() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT id, recipient, subject, body, attempts"
                    " FROM admin_email_outbox"
                    " WHERE status = 'pending' AND available_at <= :now"
                    " ORDER BY available_at, id"
                    " FOR UPDATE SKIP LOCKED LIMIT :limit"
                ),
                {"now": now, "limit": limit},
            ).all()
            for row in rows:
                self._deliver(conn, row, now)
        return len(rows)

    def _deliver(
        self, conn: sa.Connection, row: sa.engine.Row[Any], now: datetime
    ) -> None:
        attempts = row.attempts + 1
        try:
            self.transport.send(row.recipient, row.subject, row.body)
        except Exception as ex:
            LOG.warning("outbox %s delivery failed (%s)", row.id, type(ex).__name__)
            if attempts >= self._max_attempts:
                conn.execute(
                    sa.text(
                        "UPDATE admin_email_outbox"
                        " SET attempts = :attempts, status = 'failed',"
                        " diagnostic = :diag WHERE id = :id"
                    ),
                    {
                        "attempts": attempts,
                        "diag": type(ex).__name__[:120],
                        "id": row.id,
                    },
                )
            else:
                conn.execute(
                    sa.text(
                        "UPDATE admin_email_outbox"
                        " SET attempts = :attempts, available_at = :next"
                        " WHERE id = :id"
                    ),
                    {
                        "attempts": attempts,
                        "next": now + timedelta(seconds=RETRY_SECONDS * attempts),
                        "id": row.id,
                    },
                )
        else:
            conn.execute(
                sa.text(
                    "UPDATE admin_email_outbox"
                    " SET attempts = :attempts, status = 'sent', sent_at = :now"
                    " WHERE id = :id"
                ),
                {"attempts": attempts, "now": now, "id": row.id},
            )
