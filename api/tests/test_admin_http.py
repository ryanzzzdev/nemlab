"""Ported ``AdminHttpTest`` — bearer-authenticated operator refresh endpoints."""

import uuid
from datetime import date, timedelta
from uuid import UUID

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from pydantic import ValidationError

from nemlab_api.app import create_app
from nemlab_api.settings import ApiSettings
from nemlab_core.prices import Region
from nemlab_infrastructure.jobs import (
    MAX_PENDING_JOBS,
    RefreshJobService,
    StaleClaimException,
)
from nemlab_infrastructure.prices.store import PriceStore
from nemlab_infrastructure.settings import DatabaseSettings

BASE = "/api/admin/v1/price-refreshes"
TOKEN = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG"
BODY = {"region": "NSW1", "day": "2023-09-11"}
HEADERS = {"Authorization": f"Bearer {TOKEN}", "X-Actor": "spoofed"}


def _jobs(engine: sa.Engine) -> RefreshJobService:
    return RefreshJobService(engine, PriceStore(engine))


def _count(engine: sa.Engine, sql: str, **params: object) -> int:
    with engine.connect() as conn:
        return conn.execute(sa.text(sql), params).scalar_one()


def test_unauthorised_requests_cannot_read_or_mutate_jobs(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    assert (
        client.post(
            BASE,
            content='{"region":"NSW1","day":"2023-09-11"}',
            headers={
                "Idempotency-Key": "request",
                "Content-Type": "application/json",
            },
        ).status_code
        == 401
    )
    assert (
        client.post(
            BASE,
            json=BODY,
            headers={"Authorization": "Bearer wrong", "Idempotency-Key": "request"},
        ).status_code
        == 401
    )
    assert (
        client.get(BASE, headers={"Authorization": "Basic dXNlcjpwYXNz"}).status_code
        == 401
    )
    assert client.get(f"{BASE}?access_token={TOKEN}").status_code == 401
    assert client.post(f"{BASE}/{uuid.uuid4()}/cancel", content="").status_code == 401
    response = client.get(BASE)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.text == '{"code":"UNAUTHORISED"}'
    assert response.headers["content-type"].startswith("application/json")
    assert _count(scratch_db, "SELECT count(*) FROM refresh_job") == 0
    assert _count(scratch_db, "SELECT count(*) FROM refresh_job_event") == 0


def test_submission_idempotent_and_actor_comes_from_authentication(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    first = client.post(
        BASE, json=BODY, headers={**HEADERS, "Idempotency-Key": "request-1"}
    )
    assert first.status_code == 202
    assert "set-cookie" not in first.headers
    id = first.json()["id"]
    assert first.headers["location"] == f"{BASE}/{id}"
    assert first.json()["status"] == "QUEUED"
    for key in ("request-1", "request-2"):
        repeat = client.post(
            BASE, json=BODY, headers={**HEADERS, "Idempotency-Key": key}
        )
        assert repeat.json()["id"] == id
    status = client.get(f"{BASE}/{id}", headers=HEADERS)
    assert status.status_code == 200
    assert "claimToken" not in status.text
    assert "backfillId" not in status.text
    assert TOKEN not in status.text
    assert _count(scratch_db, "SELECT count(*) FROM refresh_job") == 1
    assert (
        _count(
            scratch_db,
            "SELECT count(*) FROM refresh_job_event WHERE actor = :actor",
            actor="operator:alice",
        )
        == 3
    )
    assert (
        _count(
            scratch_db,
            "SELECT count(*) FROM refresh_job_event WHERE actor = :actor",
            actor="spoofed",
        )
        == 0
    )
    events = client.get(f"{BASE}/{id}/events", headers=HEADERS)
    assert "operator:alice" in events.text
    assert client.get(f"{BASE}?limit=1", headers=HEADERS).status_code == 200


def test_rejects_invalid_bodies_and_conflicting_keys_without_leaking_inputs(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    assert (
        client.post(BASE, json=BODY, headers=HEADERS).status_code == 400
    )  # missing Idempotency-Key
    for invalid in (
        "{}",
        "{",
        '{"region":"BOGUS","day":"2023-09-11"}',
        '{"region":"NSW1","day":"2200-01-01"}',
        '{"region":"NSW1","day":"2020-01-01"}',
        '{"region":"NSW1","day":"2023-09-11","actor":"spoofed"}',
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
        assert "spoofed" not in response.text
        assert response.json()["code"] == "INVALID_REQUEST"
    assert _count(scratch_db, "SELECT count(*) FROM refresh_job") == 0
    assert (
        client.post(
            BASE, json=BODY, headers={**HEADERS, "Idempotency-Key": "fixed"}
        ).status_code
        == 202
    )
    conflict = client.post(
        BASE,
        json={"region": "NSW1", "day": "2023-09-12"},
        headers={**HEADERS, "Idempotency-Key": "fixed"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"


def test_cancellation_is_audited_idempotent_and_revokes_running_claim(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    submitted = client.post(
        BASE, json=BODY, headers={**HEADERS, "Idempotency-Key": "request"}
    )
    id = UUID(submitted.json()["id"])
    claim = _jobs(scratch_db).claim()
    assert claim is not None
    assert claim.claim_token is not None
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
    assert "CANCELLED" in events.text
    assert "CANCEL_NOOP" in events.text
    assert (
        _count(
            scratch_db,
            "SELECT count(*) FROM refresh_job_event WHERE job_id = :id"
            " AND actor = 'operator:alice' AND action LIKE 'CANCEL%'",
            id=id,
        )
        == 2
    )
    with scratch_db.connect() as conn:
        final_event = conn.execute(
            sa.text("SELECT max(id) FROM refresh_job_event")
        ).scalar_one()
    assert (
        client.get(f"{BASE}/{id}/events?after={final_event}", headers=HEADERS).text
        == "[]"
    )


def test_invalid_ids_and_bounds_have_explicit_responses(client: TestClient) -> None:
    assert client.get(f"{BASE}/not-a-uuid", headers=HEADERS).status_code == 400
    assert client.get(f"{BASE}/{uuid.uuid4()}", headers=HEADERS).status_code == 404
    assert (
        client.post(
            f"{BASE}/{uuid.uuid4()}/cancel", headers=HEADERS, content=""
        ).status_code
        == 404
    )
    assert client.get(f"{BASE}?limit=101", headers=HEADERS).status_code == 400
    assert client.get(f"{BASE}?limit=0", headers=HEADERS).status_code == 400


def test_queue_capacity_produces_backpressure(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    jobs = _jobs(scratch_db)
    for day in range(MAX_PENDING_JOBS):
        jobs.submit(
            f"fill-{day}",
            Region.QLD1,
            date(2023, 1, 1) + timedelta(days=day),
            "test",
        )
    response = client.post(
        BASE, json=BODY, headers={**HEADERS, "Idempotency-Key": "overflow"}
    )
    assert response.status_code == 429
    assert response.headers["retry-after"] == "30"
    assert response.json()["code"] == "QUEUE_FULL"


def test_storage_failure_returns_safe_error_without_sql_or_credentials(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    with scratch_db.begin() as conn:
        conn.execute(
            sa.text("ALTER TABLE refresh_job RENAME TO temporarily_missing_refresh_job")
        )
    try:
        response = client.get(BASE, headers=HEADERS)
        assert response.status_code == 503
        assert response.json()["code"] == "STORAGE_UNAVAILABLE"
        assert "SELECT" not in response.text
        assert "jdbc:" not in response.text
    finally:
        with scratch_db.begin() as conn:
            conn.execute(
                sa.text(
                    "ALTER TABLE temporarily_missing_refresh_job RENAME TO refresh_job"
                )
            )


def test_token_configuration_fails_closed(scratch_db: sa.Engine, clean: None) -> None:
    base = DatabaseSettings()
    url = (
        f"jdbc:postgresql://{scratch_db.url.host}:{scratch_db.url.port}"
        f"/{scratch_db.url.database}"
    )
    good = {
        "db_url": url,
        "db_user": base.db_user,
        "db_password": base.db_password,
        "admin_enabled": True,
        "admin_operator": "alice",
        "admin_token": TOKEN,
    }
    for override in (
        {"admin_token": "short"},
        {"admin_operator": "-bad"},
        {"admin_operator": ""},
        {"admin_token": ""},
        {"db_password": ""},
    ):
        with pytest.raises(ValidationError):
            ApiSettings(**{**good, **override})


def test_disabled_features_require_no_database_or_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No DB env, no admin credentials: the shell still starts and answers 404.
    for key in ("NEMLAB_DB_URL", "NEMLAB_DB_USER", "NEMLAB_DB_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    app = create_app(ApiSettings())
    client = TestClient(app)
    assert client.get("/actuator/health").status_code == 200
    assert client.get("/api/v1/prices/NSW1/2023-10-01").status_code == 404
    assert client.get("/api/admin/v1/price-refreshes").status_code == 404
    assert client.post("/api/v1/prices/NSW1/2023-10-01").status_code == 404


def test_security_headers_match_the_java_filter_chain(client: TestClient) -> None:
    public = client.get("/api/v1/prices/NSW1/2023-10-01")
    assert public.headers["x-content-type-options"] == "nosniff"
    assert public.headers["x-frame-options"] == "DENY"
    assert public.headers["x-xss-protection"] == "0"
    denied = client.get(BASE)
    for name, value in (
        ("x-content-type-options", "nosniff"),
        ("x-frame-options", "DENY"),
        ("x-xss-protection", "0"),
        ("pragma", "no-cache"),
        ("expires", "0"),
    ):
        assert denied.headers[name] == value
    assert "no-cache" in denied.headers["cache-control"]
