"""Admin email outbox poller (NEM-096).

The spec assigns outbox draining to the existing worker poll cycle — no
new scheduler or process. ``MailWorker`` is a fixed-delay thread like the
other pollers; each tick delivers a bounded batch through the configured
transport (``LocalMailbox`` in M6 — delivery can never reach a live
recipient from this build).
"""

import logging
import threading
import time
from collections.abc import Callable

from nemlab_infrastructure.admin.mail import OutboxMailer

LOG = logging.getLogger(__name__)

RETENTION_SECONDS = 3600


class MailWorker:
    def __init__(
        self,
        mailer: OutboxMailer,
        poll_interval: float,
        *,
        retention: Callable[[], object] | None = None,
    ) -> None:
        self._mailer = mailer
        self._poll = poll_interval
        self._retention = retention
        # Negative offset so the first tick always runs retention once.
        self._retention_at = float(-RETENTION_SECONDS)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        LOG.info("Admin mail polling started (%d ms interval)", int(self._poll * 1000))
        self._thread = threading.Thread(
            target=self._loop, name="admin-mail-worker", daemon=True
        )
        self._thread.start()

    @property
    def running(self) -> bool:
        return self._running

    def _loop(self) -> None:
        while self._running:
            self.tick()
            self._stop.wait(self._poll)

    def tick(self) -> None:
        if not self._running:
            return
        try:
            self._mailer.send_pending()
        except Exception:
            LOG.warning("mail outbox drain failed; retrying on next poll")
        if (
            self._retention is not None
            and time.monotonic() - self._retention_at >= RETENTION_SECONDS
        ):
            try:
                self._retention()
            except Exception:
                LOG.warning("access retention cleanup failed; retrying later")
            else:
                self._retention_at = time.monotonic()

    def stop(self) -> None:
        self._running = False
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=15)
            if self._thread.is_alive():
                LOG.error("admin-mail-worker did not stop within 15 s")
            self._thread = None
