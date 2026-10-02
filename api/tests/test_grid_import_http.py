"""Grid-import operator endpoints — bearer-authenticated, bounded windows."""

import uuid
from datetime import date, timedelta
from uuid import UUID

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from nemlab_core.prices import Region
from nemlab_infrastructure.grid.imports import GridImportJobs, StaleClaimException
from nemlab_infrastructure.grid.store import GridStore

BASE = "/api/admin/v1/grid-imports"
TOKEN = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG"
BODY = {
    "region": "NSW1",
    "startDay": "2023-09-01",
    "endExclusive": "2023-09-04",
}
HEADERS = {"Authorization": f"Bearer {TOKEN}", "X-Actor": "spoofed"}


def _jobs(engine: sa.Engine) -> GridImportJobs:
    return GridImportJobs(engine, GridStore(engine))


def _count(engine: sa.Engine, sql: str, **params: object) -> int:
    with engine.connect() as conn:
        return conn.execute(sa.text(sql), params).scalar_one()


def test_unauthenticated_requests_are_rejected(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    assert client.get(BASE).status_code == 401
    assert (
        client.post(BASE, json=BODY, headers={"Idempotency-Key": "request"}).status_code
        == 401
    )
    assert client.post(f"{BASE}/{uuid.uuid4()}/cancel", content="").status_code == 401
    assert _count(scratch_db, "SELECT count(*) FROM grid_import_job") == 0


def test_submission_bounds_idempotence_and_actor(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    first = client.post(
        BASE, json=BODY, headers={**HEADERS, "Idempotency-Key": "request-1"}
    )
    assert first.status_code == 202
    id = first.json()["id"]
    assert first.headers["location"] == f"{BASE}/{id}"
    assert first.json()["status"] == "QUEUED"
    assert first.json()["nextDay"] == "2023-09-01"
    # Same key, same window -> deduplicated.
    repeat = client.post(
        BASE, json=BODY, headers={**HEADERS, "Idempotency-Key": "request-1"}
    )
    assert repeat.json()["id"] == id
    # New key, same active window -> deduplicated onto the same job.
    same = client.post(
        BASE, json=BODY, headers={**HEADERS, "Idempotency-Key": "request-2"}
    )
    assert same.json()["id"] == id
    assert _count(scratch_db, "SELECT count(*) FROM grid_import_job") == 1
    assert (
        _count(
            scratch_db,
            "SELECT count(*) FROM grid_import_job_event WHERE actor = :actor",
            actor="operator:alice",
        )
        == 3
    )
    assert "spoofed" not in client.get(f"{BASE}/{id}", headers=HEADERS).text
    assert "claimToken" not in client.get(f"{BASE}/{id}", headers=HEADERS).text


def test_rejects_invalid_windows_and_conflicting_keys(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    for invalid in (
        '{"region":"NSW1","startDay":"2023-09-01","endExclusive":"2023-09-01"}',
        '{"region":"NSW1","startDay":"2023-09-01","endExclusive":"2023-10-03"}',
        '{"region":"NSW1","startDay":"2023-09-01","endExclusive":"2200-01-01"}',
        '{"region":"BOGUS","startDay":"2023-09-01","endExclusive":"2023-09-04"}',
        '{"region":"NSW1","startDay":"2023-09-01","endExclusive":"2023-09-04","actor":"x"}',
    ):
        response = client.post(
            BASE,
            content=invalid,
            headers={
                **HEADERS,
                "Idempotency-Key": "invalid",
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 400, response.text
        assert response.json()["code"] == "INVALID_REQUEST"
    assert _count(scratch_db, "SELECT count(*) FROM grid_import_job") == 0
    assert (
        client.post(
            BASE, json=BODY, headers={**HEADERS, "Idempotency-Key": "fixed"}
        ).status_code
        == 202
    )
    conflict = client.post(
        BASE,
        json={**BODY, "endExclusive": "2023-09-05"},
        headers={**HEADERS, "Idempotency-Key": "fixed"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"


def test_status_events_and_cancel_are_audited(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    submitted = client.post(
        BASE, json=BODY, headers={**HEADERS, "Idempotency-Key": "request"}
    )
    id = UUID(submitted.json()["id"])
    claim = _jobs(scratch_db).claim()
    assert claim is not None and claim.claim_token is not None
    cancelled = client.post(f"{BASE}/{id}/cancel", headers=HEADERS, content="")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    assert (
        client.post(f"{BASE}/{id}/cancel", headers=HEADERS, content="").status_code
        == 200
    )
    with pytest.raises(StaleClaimException):
        _jobs(scratch_db).fail(id, claim.claim_token, "STALE_WORKER")
    events = client.get(f"{BASE}/{id}/events", headers=HEADERS)
    assert "CANCELLED" in events.text and "CANCEL_NOOP" in events.text
    assert client.get(f"{BASE}?limit=1", headers=HEADERS).status_code == 200


def test_invalid_ids_and_bounds(client: TestClient) -> None:
    assert client.get(f"{BASE}/not-a-uuid", headers=HEADERS).status_code == 400
    assert client.get(f"{BASE}/{uuid.uuid4()}", headers=HEADERS).status_code == 404
    assert (
        client.post(
            f"{BASE}/{uuid.uuid4()}/cancel", headers=HEADERS, content=""
        ).status_code
        == 404
    )
    assert client.get(f"{BASE}?limit=101", headers=HEADERS).status_code == 400


def test_queue_capacity_produces_backpressure(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    jobs = _jobs(scratch_db)
    for i in range(20):
        jobs.submit(
            f"fill-{i}",
            Region.NSW1,
            date(2023, 1, 1) + timedelta(days=40 * i),
            date(2023, 1, 1) + timedelta(days=40 * i + 1),
            "test",
        )
    response = client.post(
        BASE, json=BODY, headers={**HEADERS, "Idempotency-Key": "overflow"}
    )
    assert response.status_code == 429
    assert response.json()["code"] == "QUEUE_FULL"
    assert response.headers["retry-after"] == "30"


def test_storage_failure_returns_safe_error(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    with scratch_db.begin() as conn:
        conn.execute(
            sa.text("ALTER TABLE grid_import_job RENAME TO temporarily_missing")
        )
    try:
        response = client.get(BASE, headers=HEADERS)
        assert response.status_code == 503
        assert response.json()["code"] == "STORAGE_UNAVAILABLE"
        assert "SELECT" not in response.text
    finally:
        with scratch_db.begin() as conn:
            conn.execute(
                sa.text("ALTER TABLE temporarily_missing RENAME TO grid_import_job")
            )


def test_disabled_admin_returns_404(scratch_db: sa.Engine, clean: None) -> None:
    from nemlab_api.app import create_app
    from nemlab_api.settings import ApiSettings
    from nemlab_infrastructure.settings import DatabaseSettings

    base = DatabaseSettings()
    url = (
        f"jdbc:postgresql://{scratch_db.url.host}:{scratch_db.url.port}"
        f"/{scratch_db.url.database}"
    )
    app = create_app(
        ApiSettings(db_url=url, db_user=base.db_user, db_password=base.db_password)
    )
    assert TestClient(app).get(BASE).status_code == 404
