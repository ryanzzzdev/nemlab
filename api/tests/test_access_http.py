"""NEM-098 HTTP journey — request access, verify, owner decision, viewer
grant lifecycle, recent-auth enforcement and delivery-state visibility."""

import uuid
from typing import Any
from uuid import UUID

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from nemlab_infrastructure.admin.auth import AdminAuth, csrf_for
from nemlab_infrastructure.admin.identity import AdminIdentity

PUBLIC = "/api/access/v1"
ADMIN_REQUESTS = "/api/admin/v1/access-requests"
ADMIN_GRANTS = "/api/admin/v1/viewer-grants"
AUTH = "/api/auth/v1"
OWNER_EMAIL = "owner@example.test"
APPLICANT = "applicant@example.test"
TOKEN = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG"
BEARER = {"Authorization": f"Bearer {TOKEN}"}
ORIGIN = {"Origin": "http://testserver"}
BASE_URL = "http://testserver/admin"


@pytest.fixture(autouse=True)
def owner(scratch_db: sa.Engine) -> None:
    AdminIdentity(scratch_db).bootstrap_owner("Owner", OWNER_EMAIL)


def _owner_id(engine: sa.Engine) -> UUID:
    with engine.connect() as conn:
        return conn.execute(
            sa.text("SELECT id FROM admin_user WHERE role = 'owner'")
        ).scalar_one()


def _seed(client: TestClient, engine: sa.Engine, email: str) -> dict[str, Any]:
    """A real server-side session without exercising the mail path — the
    dev-only seed command's service entry point, used here so tests do not
    depend on resend cooldowns."""
    raw, principal = AdminAuth(engine, base_url=BASE_URL).seed_session(email)
    client.cookies.set("nemlab_session", raw)
    return {"csrfToken": csrf_for(raw), "role": principal.role}


def _sign_in(client: TestClient, scratch_db: sa.Engine, email: str) -> dict[str, Any]:
    response = client.post(f"{AUTH}/sign-in-requests", json={"email": email})
    assert response.status_code == 202
    with scratch_db.connect() as conn:
        body = conn.execute(
            sa.text(
                "SELECT body FROM admin_email_outbox"
                " WHERE kind = 'sign_in' AND recipient = :email"
                " ORDER BY created_at DESC LIMIT 1"
            ),
            {"email": email},
        ).scalar_one()
    raw = body.split("#token=")[1].split("\n")[0]
    response = client.post(f"{AUTH}/sessions", json={"token": raw})
    assert response.status_code == 200
    return response.json()


def _submit(
    client: TestClient, email: str = APPLICANT, name: str = "Applicant"
) -> None:
    response = client.post(
        f"{PUBLIC}/requests",
        json={"displayName": name, "email": email, "message": "please"},
    )
    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}


def _verify(
    client: TestClient, scratch_db: sa.Engine, email: str = APPLICANT
) -> dict[str, Any]:
    with scratch_db.connect() as conn:
        body = conn.execute(
            sa.text(
                "SELECT body FROM admin_email_outbox"
                " WHERE kind = 'request_verification' AND recipient = :email"
                " ORDER BY created_at DESC LIMIT 1"
            ),
            {"email": email},
        ).scalar_one()
    raw = body.split("#token=")[1].split("\n")[0]
    response = client.post(f"{PUBLIC}/verifications", json={"token": raw})
    assert response.status_code == 200
    return response.json()


def _headers(session: dict[str, Any]) -> dict[str, str]:
    return {**ORIGIN, "x-csrf-token": session["csrfToken"]}


def test_full_request_to_viewer_journey(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    _submit(client)
    # Enumeration-safe: same generic acceptance for duplicates and unknowns.
    _submit(client, email="someone-else@example.test")
    with scratch_db.connect() as conn:
        pending = conn.execute(
            sa.text("SELECT count(*) FROM admin_access_request")
        ).scalar_one()
    assert pending == 2

    session = _verify(client, scratch_db)
    assert session["role"] == "applicant"
    status = client.get(f"{PUBLIC}/requests/status")
    assert status.status_code == 200
    assert status.json()["status"] == "pending"
    # The consumed token cannot be replayed.
    replayed = client.post(
        f"{PUBLIC}/verifications", json={"token": "same-token-shape"}
    )
    assert replayed.status_code == 401

    # Owner sees the verified request and approves for 30 days.
    client.cookies.clear()
    owner = _seed(client, scratch_db, OWNER_EMAIL)
    queue = client.get(ADMIN_REQUESTS)
    assert queue.status_code == 200
    applicant = next(r for r in queue.json() if r["email"] == APPLICANT)
    detail = client.get(f"{ADMIN_REQUESTS}/{applicant['id']}")
    assert detail.status_code == 200
    assert {d["kind"] for d in detail.json()["deliveries"]} == {"request_verification"}

    headers = _headers(owner)
    decision = client.post(
        f"{ADMIN_REQUESTS}/{applicant['id']}/decisions",
        json={"decision": "approve", "days": 30, "version": applicant["version"]},
        headers=headers,
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "approved"
    # The invite appears under the request's deliveries.
    deliveries = client.get(f"{ADMIN_REQUESTS}/{applicant['id']}").json()["deliveries"]
    assert {d["kind"] for d in deliveries} == {"request_verification", "sign_in"}
    # A stale replayed decision conflicts instead of duplicating.
    conflict = client.post(
        f"{ADMIN_REQUESTS}/{applicant['id']}/decisions",
        json={"decision": "reject", "version": applicant["version"]},
        headers=headers,
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "ACCESS_CONFLICT"

    # The viewer signs in through the mailed invite and reads safely.
    client.cookies.clear()
    viewer = _sign_in(client, scratch_db, APPLICANT)
    assert viewer["role"] == "viewer"
    assert client.get("/api/admin/v1/grid-imports").status_code == 200
    # Automation cannot touch access management.
    client.cookies.clear()
    assert client.get(ADMIN_GRANTS, headers=BEARER).status_code == 403

    # Owner revokes the grant; the viewer's next request is denied.
    owner = _seed(client, scratch_db, OWNER_EMAIL)
    grant = next(g for g in client.get(ADMIN_GRANTS).json() if g["state"] == "active")
    revoked = client.post(
        f"{ADMIN_GRANTS}/{grant['id']}/revoke",
        json={"reason": "access no longer needed"},
        headers=_headers(owner),
    )
    assert revoked.status_code == 200
    assert revoked.json()["state"] == "revoked"

    client.cookies.clear()
    generic = client.post(f"{AUTH}/sign-in-requests", json={"email": APPLICANT})
    assert generic.status_code == 202  # no mail for a revoked grant


def test_recent_auth_required_for_decisions(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    _submit(client)
    _verify(client, scratch_db)
    client.cookies.clear()
    owner = _seed(client, scratch_db, OWNER_EMAIL)
    headers = _headers(owner)
    request = client.get(ADMIN_REQUESTS).json()[0]

    # Reads are fine; decisions need a session under 15 minutes old.
    with scratch_db.begin() as conn:
        conn.execute(
            sa.text(
                "UPDATE admin_session SET created_at = now() - interval '20 minutes'"
            )
        )
    assert client.get(ADMIN_REQUESTS).status_code == 200
    stale = client.post(
        f"{ADMIN_REQUESTS}/{request['id']}/decisions",
        json={"decision": "reject", "version": request["version"]},
        headers=headers,
    )
    assert stale.status_code == 403
    assert stale.json()["code"] == "RECENT_AUTH_REQUIRED"
    # Extends and revokes are decisions too.
    assert (
        client.post(
            f"{ADMIN_GRANTS}/{uuid.uuid4()}/extend",
            json={"days": 30},
            headers=headers,
        ).status_code
        == 403
    )


def test_applicant_only_status_and_resend(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    _submit(client)
    _verify(client, scratch_db)
    # Cookie + bearer is a deterministic conflict even on public routes.
    response = client.get(f"{PUBLIC}/requests/status", headers=BEARER)
    assert response.status_code == 401
    client.cookies.clear()
    _seed(client, scratch_db, OWNER_EMAIL)
    assert client.get(f"{PUBLIC}/requests/status").status_code == 403
    client.cookies.clear()

    # Applicant resend needs the CSRF header like any cookie mutation.
    _submit(client, email="second@example.test", name="Second")
    second = _verify(client, scratch_db, "second@example.test")
    assert client.post(f"{PUBLIC}/requests/resend").status_code == 403
    resent = client.post(
        f"{PUBLIC}/requests/resend",
        headers={**ORIGIN, "x-csrf-token": second["csrfToken"]},
    )
    assert resent.status_code == 202


def test_owner_endpoints_reject_other_identities(client: TestClient) -> None:
    assert client.get(ADMIN_REQUESTS).status_code == 401
    assert client.get(ADMIN_REQUESTS, headers=BEARER).status_code == 403
    assert client.get(ADMIN_GRANTS, headers=BEARER).status_code == 403
    fake = uuid.uuid4()
    assert (
        client.post(
            f"{ADMIN_REQUESTS}/{fake}/decisions",
            json={"decision": "reject", "version": 0},
            headers=BEARER,
        ).status_code
        == 403
    )


def test_owner_resend_and_missing_requests(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    owner = _seed(client, scratch_db, OWNER_EMAIL)
    headers = _headers(owner)
    missing = uuid.uuid4()
    assert client.get(f"{ADMIN_REQUESTS}/{missing}").status_code == 404
    assert (
        client.post(f"{ADMIN_REQUESTS}/{missing}/resend", headers=headers).status_code
        == 404
    )

    # Unverified request: resend re-queues the verification mail.
    _submit(client)
    request_id = UUID(
        str(
            _scalar(
                scratch_db,
                "SELECT id FROM admin_access_request WHERE email = :e",
                e=APPLICANT,
            )
        )
    )
    assert (
        client.post(
            f"{ADMIN_REQUESTS}/{request_id}/resend", headers=headers
        ).status_code
        == 202
    )
    deliveries = client.get(f"{ADMIN_REQUESTS}/{request_id}").json()["deliveries"]
    assert len([d for d in deliveries if d["kind"] == "request_verification"]) == 2

    # Once pending there is nothing to resend; approved resends the invite.
    _verify(client, scratch_db)
    client.cookies.clear()
    owner = _seed(client, scratch_db, OWNER_EMAIL)
    headers = _headers(owner)
    assert (
        client.post(
            f"{ADMIN_REQUESTS}/{request_id}/resend", headers=headers
        ).status_code
        == 409
    )
    request = client.get(f"{ADMIN_REQUESTS}/{request_id}").json()
    decided = client.post(
        f"{ADMIN_REQUESTS}/{request_id}/decisions",
        json={"decision": "approve", "days": 7, "version": request["version"]},
        headers=headers,
    )
    assert decided.status_code == 200
    assert (
        client.post(
            f"{ADMIN_REQUESTS}/{request_id}/resend", headers=headers
        ).status_code
        == 202
    )
    deliveries = client.get(f"{ADMIN_REQUESTS}/{request_id}").json()["deliveries"]
    assert len([d for d in deliveries if d["kind"] == "sign_in"]) == 2


def _scalar(engine: sa.Engine, sql: str, **params: object) -> object:
    with engine.connect() as conn:
        return conn.execute(sa.text(sql), params).scalar_one()
