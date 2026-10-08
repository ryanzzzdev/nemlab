"""NEM-096 mail outbox drain — the captured-mailbox worker path."""

import sys
import threading
import time
from pathlib import Path

import pytest
import sqlalchemy as sa
from pydantic import ValidationError

sys.path.insert(
    0, str(Path(__file__).resolve().parents[2] / "infrastructure" / "tests")
)

from db_fixture import apply_admin_tables

from nemlab_infrastructure.admin.auth import AdminAuth
from nemlab_infrastructure.admin.identity import AdminIdentity
from nemlab_infrastructure.admin.mail import (
    LocalMailbox,
    OutboxMailer,
)
from nemlab_worker.mail import MailWorker
from nemlab_worker.settings import WorkerSettings

EMAIL = "owner@example.test"


def test_worker_settings_gate_mail_dir() -> None:
    with pytest.raises(ValidationError):
        WorkerSettings(mail_enabled=True)
    with pytest.raises(ValidationError):
        WorkerSettings(mail_enabled=True, mail_dir="m", mail_poll_ms=5)
    ok = WorkerSettings(mail_enabled=True, mail_dir="mailbox", mail_poll_ms=1000)
    assert ok.mail_enabled


def _delivered(directory: Path, timeout: float = 10) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if list(directory.glob("*.eml")):
            return True
        time.sleep(0.05)
    return False


def test_mail_worker_start_tick_stop(scratch_db: sa.Engine, tmp_path: Path) -> None:
    apply_admin_tables(scratch_db)
    AdminIdentity(scratch_db).bootstrap_owner("Owner", EMAIL)
    assert AdminAuth(scratch_db, base_url="http://x/admin").request_sign_in(EMAIL)
    worker = MailWorker(
        OutboxMailer(scratch_db, LocalMailbox(str(tmp_path / "m"))), 0.05
    )
    worker.start()
    assert worker.running
    try:
        assert _delivered(tmp_path / "m")
        with scratch_db.connect() as conn:
            status = conn.execute(
                sa.text("SELECT status FROM admin_email_outbox")
            ).scalar_one()
        assert status == "sent"
    finally:
        worker.stop()
    assert not worker.running


def test_run_idles_without_flags() -> None:
    from unittest.mock import patch

    from nemlab_worker import main

    stop = threading.Event()
    stop.set()
    with patch("nemlab_worker.main.create_bounded_engine") as engine:
        main.run(WorkerSettings(), stop)
    engine.assert_not_called()
