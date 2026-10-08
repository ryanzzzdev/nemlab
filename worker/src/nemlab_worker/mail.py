"""Admin email outbox poller (NEM-096).

The spec assigns outbox draining to the existing worker poll cycle — no
new scheduler or process. ``MailWorker`` is a fixed-delay thread like the
other pollers; each tick delivers a bounded batch through the configured
transport (``LocalMailbox`` in M6 — delivery can never reach a live
recipient from this build).
"""

import logging
import threading

from nemlab_infrastructure.admin.mail import OutboxMailer

LOG = logging.getLogger(__name__)


class MailWorker:
    def __init__(self, mailer: OutboxMailer, poll_interval: float) -> None:
        self._mailer = mailer
        self._poll = poll_interval
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

    def stop(self) -> None:
        self._running = False
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=15)
            if self._thread.is_alive():
                LOG.error("admin-mail-worker did not stop within 15 s")
            self._thread = None
