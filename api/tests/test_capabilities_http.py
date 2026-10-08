"""NEM-097 capability matrix — identity x route access over /api/admin/**.

Identities exercised: anonymous, applicant session, viewer sessions in
every grant state, owner session and legacy bearer automation. Writes
through a cookie additionally need the CSRF header and a matching Origin.
"""

import hashlib
import uuid
from typing import Any
from uuid import UUID

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from nemlab_infrastructure.admin.identity import AdminIdentity

LIST = "/api/admin/v1/grid-imports"
SUBMIT = "/api/admin/v1/price-refreshes"
COVERAGE = "/api/admin/v1/grid-coverage/NSW1?start=2023-09-01&endExclusive=2023-09-02"
PUBLICATIONS = "/api/admin/v1/grid-publications"
LOADS = "/api/admin/v1/load-operations"
BODY = {"region": "NSW1", "day": "2023-09-11"}
TOKEN = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG"
BEARER = {"Authorization": f"Bearer {TOKEN}"}
OWNER_EMAIL = "owner@example.test"
VIEWER_EMAIL = "viewer@example.test"


@pytest.fixture(autouse=True)
def owner(scratch_db: sa.Engine) -> None:
    AdminIdentity(scratch_db).bootstrap_owner("Owner", OWNER_EMAIL)


def _owner_id(engine: sa.Engine) -> UUID:
    with engine.connect() as conn:
        return conn.execute(
            sa.text("SELECT id FROM admin_user WHERE role = 'owner'")
        ).scalar_one()


def _request_sign_in(client: TestClient, email: str) -> None:
    response = client.post("/api/auth/v1/sign-in-requests", json={"email": email})
    assert response.status_code == 202


def _sign_in(client: TestClient, scratch_db: sa.Engine, email: str) -> dict[str, Any]:
    _request_sign_in(client, email)
    with scratch_db.connect() as conn:
        body = conn.execute(
            sa.text("SELECT body FROM admin_email_outbox ORDER BY id DESC LIMIT 1")
        ).scalar_one()
    raw = body.split("#token=")[1].split("\n")[0]
    response = client.post("/api/auth/v1/sessions", json={"token": raw})
    assert response.status_code == 200
    return response.json()


_REQUEST_INSERTS = {
    "unverified": (
        "INSERT INTO admin_access_request (id, display_name, email, status)"
        " VALUES (:id, 'Applicant', :email, 'unverified')"
    ),
    "pending": (
        "INSERT INTO admin_access_request"
        " (id, display_name, email, status, verified_at)"
        " VALUES (:id, 'Applicant', :email, 'pending', now())"
    ),
    "approved": (
        "INSERT INTO admin_access_request"
        " (id, display_name, email, status, verified_at, decided_at, decided_by)"
        " VALUES (:id, 'Applicant', :email, 'approved', now(), now(), :owner)"
    ),
    "rejected": (
        "INSERT INTO admin_access_request"
        " (id, display_name, email, status, verified_at, decided_at, decided_by)"
        " VALUES (:id, 'Applicant', :email, 'rejected', now(), now(), :owner)"
    ),
}


def _insert_request(engine: sa.Engine, email: str, status: str) -> UUID:
    request_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            sa.text(_REQUEST_INSERTS[status]),
            {"id": request_id, "email": email, "owner": _owner_id(engine)},
        )
    return request_id


def _insert_viewer(engine: sa.Engine, *, grant: str = "active") -> UUID:
    user_id, request_id = uuid.uuid4(), uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO admin_access_request"
                " (id, display_name, email, status, verified_at, decided_at,"
                " decided_by) VALUES (:id, 'Viewer', :email, 'approved', now(),"
                " now(), :owner)"
            ),
            {"id": request_id, "email": VIEWER_EMAIL, "owner": _owner_id(engine)},
        )
        conn.execute(
            sa.text(
                "INSERT INTO admin_user (id, role, display_name, email)"
                " VALUES (:id, 'viewer', 'Viewer', :email)"
            ),
            {"id": user_id, "email": VIEWER_EMAIL},
        )
        statement = {
            "active": (
                "INSERT INTO admin_viewer_grant"
                " (id, request_id, user_id, granted_by, granted_at, expires_at)"
                " VALUES (:id, :request, :user, :owner, now(),"
                " now() + interval '30 days')"
            ),
            "expired": (
                "INSERT INTO admin_viewer_grant"
                " (id, request_id, user_id, granted_by, granted_at, expires_at)"
                " VALUES (:id, :request, :user, :owner,"
                " now() - interval '40 days', now() - interval '10 days')"
            ),
            "revoked": (
                "INSERT INTO admin_viewer_grant"
                " (id, request_id, user_id, granted_by, granted_at, expires_at,"
                " revoked_at, revoked_by)"
                " VALUES (:id, :request, :user, :owner,"
                " now() - interval '10 days', now() + interval '20 days',"
                " now(), :owner)"
            ),
        }[grant]
        conn.execute(
            sa.text(statement),
            {
                "id": uuid.uuid4(),
                "request": request_id,
                "user": user_id,
                "owner": _owner_id(engine),
            },
        )
    return user_id


def _applicant_session(client: TestClient, engine: sa.Engine) -> None:
    request_id = _insert_request(engine, "applicant@example.test", "pending")
    raw = "applicant-session-raw-secret"
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO admin_session (id, request_id, token_hash, expires_at)"
                " VALUES (:id, :request, :hash, now() + interval '8 hours')"
            ),
            {
                "id": uuid.uuid4(),
                "request": request_id,
                "hash": hashlib.sha256(raw.encode()).hexdigest(),
            },
        )
    client.cookies.set("nemlab_session", raw)


def test_anonymous_and_applicant_are_denied(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    for path in (LIST, COVERAGE, PUBLICATIONS, LOADS):
        assert client.get(path).status_code == 401
    _applicant_session(client, scratch_db)
    for path in (LIST, COVERAGE, PUBLICATIONS, LOADS):
        response = client.get(path)
        assert response.status_code == 403, path
        assert response.json()["code"] == "FORBIDDEN"
    assert (
        client.post(SUBMIT, json=BODY, headers={"Idempotency-Key": "k"}).status_code
        == 403
    )


def test_viewer_reads_safely_but_cannot_write(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    _insert_viewer(scratch_db)
    # Bearer automation records its real actor; the viewer must see a label.
    submitted = client.post(
        SUBMIT, json=BODY, headers={**BEARER, "Idempotency-Key": "seen-by-viewer"}
    )
    assert submitted.status_code == 202
    job_id = submitted.json()["id"]

    _sign_in(client, scratch_db, VIEWER_EMAIL)
    assert client.get(LIST).status_code == 200
    assert client.get(SUBMIT).status_code == 200
    assert client.get(COVERAGE).status_code == 200
    assert client.get(PUBLICATIONS).status_code == 200
    assert client.get(LOADS).status_code == 200
    assert client.get(f"{SUBMIT}/{job_id}").status_code == 200

    events = client.get(f"{SUBMIT}/{job_id}/events")
    assert events.status_code == 200
    actors = {event["actor"] for event in events.json()}
    assert actors == {"Operator"}
    assert "alice" not in events.text

    for method, path in (
        ("post", SUBMIT),
        ("post", f"{SUBMIT}/{job_id}/cancel"),
        ("post", LIST),
        ("post", PUBLICATIONS),
        ("post", LOADS),
    ):
        response = getattr(client, method)(
            path, json=BODY, headers={"Idempotency-Key": "viewer-attempt"}
        )
        assert response.status_code == 403, (method, path)
        assert response.json()["code"] == "FORBIDDEN"


def _user_session(client: TestClient, engine: sa.Engine, user_id: UUID) -> None:
    raw = f"user-session-{user_id}"
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO admin_session (id, user_id, token_hash, expires_at)"
                " VALUES (:id, :user, :hash, now() + interval '8 hours')"
            ),
            {
                "id": uuid.uuid4(),
                "user": user_id,
                "hash": hashlib.sha256(raw.encode()).hexdigest(),
            },
        )
    client.cookies.set("nemlab_session", raw)


def test_expired_grant_gets_no_mail_and_denies_session(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    user_id = _insert_viewer(scratch_db, grant="expired")
    _request_sign_in(client, VIEWER_EMAIL)
    with scratch_db.connect() as conn:
        sent = conn.execute(
            sa.text("SELECT count(*) FROM admin_email_outbox")
        ).scalar_one()
    assert sent == 0
    _user_session(client, scratch_db, user_id)
    assert client.get(LIST).status_code == 401


def test_revoked_grant_blocks_active_session(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    _insert_viewer(scratch_db)
    _sign_in(client, scratch_db, VIEWER_EMAIL)
    assert client.get(LIST).status_code == 200
    with scratch_db.begin() as conn:
        conn.execute(
            sa.text(
                "UPDATE admin_viewer_grant SET revoked_at = now(), revoked_by = :owner"
            ),
            {"owner": _owner_id(scratch_db)},
        )
    assert client.get(LIST).status_code == 401


def test_owner_session_writes_need_csrf_and_origin(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    session = _sign_in(client, scratch_db, OWNER_EMAIL)
    assert session["role"] == "owner"
    assert client.get(LIST).status_code == 200

    missing = client.post(SUBMIT, json=BODY, headers={"Idempotency-Key": "no-csrf"})
    assert missing.status_code == 403
    assert missing.json()["code"] == "FORBIDDEN"

    headers = {
        "Idempotency-Key": "with-csrf",
        "x-csrf-token": session["csrfToken"],
        "Origin": "http://testserver",
    }
    created = client.post(SUBMIT, json=BODY, headers=headers)
    assert created.status_code == 202
    job_id = created.json()["id"]
    cancelled = client.post(f"{SUBMIT}/{job_id}/cancel", headers=headers)
    assert cancelled.status_code == 200


def test_bearer_automation_keeps_operational_access(
    client: TestClient,
) -> None:
    submitted = client.post(
        SUBMIT, json=BODY, headers={**BEARER, "Idempotency-Key": "automation"}
    )
    assert submitted.status_code == 202
    assert client.get(LIST, headers=BEARER).status_code == 200
    events = client.get(f"{SUBMIT}/{submitted.json()['id']}/events", headers=BEARER)
    assert "operator:alice" in events.text


def test_conflicting_credentials_and_unregistered_routes_deny(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    _sign_in(client, scratch_db, OWNER_EMAIL)
    conflict = client.get(LIST, headers=BEARER)
    assert conflict.status_code == 401

    # Deny-by-default: even the owner gets a bare 404 on unregistered
    # paths and unregistered methods on registered templates.
    for method, path in (
        ("get", "/api/admin/v1/unknown"),
        ("delete", SUBMIT),
        ("post", f"{SUBMIT}/{uuid.uuid4()}/events"),
        ("get", "/api/admin"),
    ):
        assert getattr(client, method)(path).status_code == 404
    client.cookies.clear()
    assert client.get("/api/admin/v1/unknown", headers=BEARER).status_code == 404
