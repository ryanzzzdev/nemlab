"""NEM-096 browser auth endpoints — sign-in links, sessions, CSRF, limits.

The mailbox is the durable outbox: a sign-in request leaves a pending row
whose body carries the raw fragment token, mirroring the real email flow
without any live transport.
"""

import logging
from typing import Any

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from pydantic import ValidationError

from nemlab_api.settings import ApiSettings
from nemlab_infrastructure.admin.identity import AdminIdentity

BASE = "/api/auth/v1"
EMAIL = "owner@example.test"
TOKEN = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG"


@pytest.fixture(autouse=True)
def owner(scratch_db: sa.Engine) -> None:
    AdminIdentity(scratch_db).bootstrap_owner("Owner", EMAIL)


def _request_sign_in(client: TestClient, email: str = EMAIL) -> None:
    response = client.post(f"{BASE}/sign-in-requests", json={"email": email})
    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}


def _raw_token(scratch_db: sa.Engine) -> str:
    with scratch_db.connect() as conn:
        body = conn.execute(
            sa.text("SELECT body FROM admin_email_outbox ORDER BY id DESC LIMIT 1")
        ).scalar_one()
    return body.split("#token=")[1].split("\n")[0]


def _outbox_count(scratch_db: sa.Engine) -> int:
    with scratch_db.connect() as conn:
        return conn.execute(
            sa.text("SELECT count(*) FROM admin_email_outbox")
        ).scalar_one()


def _sign_in(client: TestClient, scratch_db: sa.Engine) -> dict[str, Any]:
    _request_sign_in(client)
    response = client.post(f"{BASE}/sessions", json={"token": _raw_token(scratch_db)})
    assert response.status_code == 200
    return response.json()


def test_generic_response_hides_account_existence(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    _request_sign_in(client, EMAIL)
    _request_sign_in(client, "nobody@example.test")
    _request_sign_in(client, "OWNER@example.test")  # case-insensitive hit
    # One real mail for each distinct valid account request; the unknown
    # address produced the same 202 but no outbox row.
    assert _outbox_count(scratch_db) == 1  # resend cooldown dedupes the rest


def test_full_sign_in_session_logout(client: TestClient, scratch_db: sa.Engine) -> None:
    body = _sign_in(client, scratch_db)
    assert body["role"] == "owner" and body["name"] == "Owner"
    assert "expiresAt" in body and len(body["csrfToken"]) == 64
    cookie = client.cookies.get("nemlab_session")
    assert cookie is not None and len(cookie) == 43

    session = client.get(f"{BASE}/session")
    assert session.status_code == 200
    assert session.json()["role"] == "owner"

    origin = {"Origin": "http://testserver"}
    assert client.post(f"{BASE}/logout").status_code == 403  # no CSRF
    assert (
        client.post(
            f"{BASE}/logout",
            headers={**origin, "x-csrf-token": "wrong"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"{BASE}/logout",
            headers={
                "Origin": "http://evil.example",
                "x-csrf-token": body["csrfToken"],
            },
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"{BASE}/logout",
            headers={**origin, "x-csrf-token": body["csrfToken"]},
        ).status_code
        == 204
    )
    assert client.get(f"{BASE}/session").status_code == 401


def test_exchange_rejects_bad_and_replayed_tokens(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    for token in ("", "bogus", "x" * 200):
        response = client.post(f"{BASE}/sessions", json={"token": token})
        assert response.status_code == 401
        assert response.json()["code"] == "INVALID_TOKEN"
    raw = _raw_token_from_request(client, scratch_db)
    assert client.post(f"{BASE}/sessions", json={"token": raw}).status_code == 200
    replay = client.post(f"{BASE}/sessions", json={"token": raw})
    assert replay.status_code == 401


def _raw_token_from_request(client: TestClient, scratch_db: sa.Engine) -> str:
    _request_sign_in(client)
    return _raw_token(scratch_db)


def test_failed_exchange_rate_limit(client: TestClient, scratch_db: sa.Engine) -> None:
    for _ in range(10):
        assert (
            client.post(f"{BASE}/sessions", json={"token": "nope"}).status_code == 401
        )
    assert client.post(f"{BASE}/sessions", json={"token": "nope"}).status_code == 429


def test_sign_in_ip_rate_limit(client: TestClient) -> None:
    for i in range(20):
        response = client.post(
            f"{BASE}/sign-in-requests", json={"email": f"user{i}@example.test"}
        )
        assert response.status_code == 202
    response = client.post(
        f"{BASE}/sign-in-requests", json={"email": "user-x@example.test"}
    )
    assert response.status_code == 429
    assert response.json()["code"] == "RATE_LIMITED"


def test_conflicting_cookie_and_bearer_rejected(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    _sign_in(client, scratch_db)
    response = client.get(
        f"{BASE}/session", headers={"Authorization": f"Bearer {TOKEN}"}
    )
    assert response.status_code == 401


def test_session_requires_valid_cookie(client: TestClient) -> None:
    assert client.get(f"{BASE}/session").status_code == 401
    client.cookies.set("nemlab_session", "forged")
    assert client.get(f"{BASE}/session").status_code == 401
    client.cookies.clear()


def test_request_validation(client: TestClient) -> None:
    assert client.post(f"{BASE}/sign-in-requests", json={}).status_code == 400
    assert (
        client.post(
            f"{BASE}/sign-in-requests", json={"email": "not-an-email"}
        ).status_code
        == 400
    )
    assert (
        client.post(
            f"{BASE}/sign-in-requests",
            json={"email": EMAIL, "extra": 1},
        ).status_code
        == 400
    )


def test_auth_query_strings_not_logged(client: TestClient) -> None:
    records: list[logging.LogRecord] = []
    logger = logging.getLogger("nemlab_api.requests")
    handler = logging.Handler()
    handler.emit = records.append
    logger.addHandler(handler)
    previous_level, previous_disabled = logger.level, logger.disabled
    logger.setLevel(logging.INFO)
    # Alembic's fileConfig(disable_existing_loggers=True) can leave this logger
    # disabled when the schema tests ran earlier in the same process.
    logger.disabled = False
    try:
        client.get(f"{BASE}/session?token=secret-value")
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)
        logger.disabled = previous_disabled
    line = next(
        record.getMessage()
        for record in records
        if "/api/auth/v1/session" in record.getMessage()
    )
    assert "secret-value" not in line and "token=" not in line


def test_production_cookie_config_fails_closed() -> None:
    # Default posture is production: relaxing Secure requires an explicit
    # development environment, and the combination cannot start up.
    with pytest.raises(ValidationError):
        ApiSettings(insecure_cookies=True)
    with pytest.raises(ValidationError):
        ApiSettings(environment="staging", insecure_cookies=True)
    dev = ApiSettings(environment="development", insecure_cookies=True)
    assert not dev.secure_cookies
    assert ApiSettings().secure_cookies


def test_admin_requires_base_url() -> None:
    with pytest.raises(ValidationError):
        ApiSettings(
            db_url="jdbc:postgresql://x/db",
            db_user="u",
            db_password="p",
            admin_enabled=True,
            admin_operator="alice",
            admin_token=TOKEN,
        )
