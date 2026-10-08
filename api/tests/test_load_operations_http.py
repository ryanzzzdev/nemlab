"""NEM-102 load-operation HTTP tests — owner dispatch lifecycle through
the API, safe viewer reads, denied mutations for every non-owner
identity and the deterministic request-key surface."""

import hashlib
import uuid
from uuid import UUID

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from nemlab_infrastructure.admin.identity import AdminIdentity

BASE = "/api/admin/v1/load-operations"
START = "2023-09-04"
TOKEN = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG"
BEARER = {"Authorization": f"Bearer {TOKEN}"}
OWNER_EMAIL = "owner@example.test"
VIEWER_EMAIL = "viewer@example.test"
BODY = {"region": "NSW1", "startDay": START, "endExclusive": "2023-09-14"}


@pytest.fixture(autouse=True)
def owner(scratch_db: sa.Engine) -> None:
    AdminIdentity(scratch_db).bootstrap_owner("Owner", OWNER_EMAIL)


def _owner_id(engine: sa.Engine) -> UUID:
    with engine.connect() as conn:
        return conn.execute(
            sa.text("SELECT id FROM admin_user WHERE role = 'owner'")
        ).scalar_one()


def _session(client: TestClient, engine: sa.Engine, user_id: UUID) -> None:
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


def _viewer(client: TestClient, engine: sa.Engine) -> dict[str, str]:
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
        conn.execute(
            sa.text(
                "INSERT INTO admin_viewer_grant"
                " (id, request_id, user_id, granted_by, granted_at, expires_at)"
                " VALUES (:id, :request, :user, :owner, now(),"
                " now() + interval '30 days')"
            ),
            {
                "id": uuid.uuid4(),
                "request": request_id,
                "user": user_id,
                "owner": _owner_id(engine),
            },
        )
    _session(client, engine, user_id)
    return {"x-csrf-token": "unused", "Origin": "http://testserver"}


def _owner_headers(client: TestClient, engine: sa.Engine) -> dict[str, str]:
    client.post("/api/auth/v1/sign-in-requests", json={"email": OWNER_EMAIL})
    with engine.connect() as conn:
        body = conn.execute(
            sa.text(
                "SELECT body FROM admin_email_outbox"
                " WHERE recipient = :email ORDER BY created_at DESC LIMIT 1"
            ),
            {"email": OWNER_EMAIL},
        ).scalar_one()
    raw = body.split("#token=")[1].split("\n")[0]
    session = client.post("/api/auth/v1/sessions", json={"token": raw}).json()
    return {
        "x-csrf-token": session["csrfToken"],
        "Origin": "http://testserver",
    }


def test_owner_dispatch_lifecycle(client: TestClient, scratch_db: sa.Engine) -> None:
    headers = _owner_headers(client, scratch_db)
    created = client.post(BASE, json=BODY, headers=headers)
    assert created.status_code == 201
    op = created.json()
    assert op["status"] == "dispatching"
    assert op["phase"] == "grid"
    assert op["nextDay"] == START
    op_id = op["id"]

    dispatched = client.post(f"{BASE}/{op_id}/dispatch", headers=headers)
    assert dispatched.status_code == 200
    outcome = dispatched.json()
    assert outcome["outcome"] == "submitted"
    child = outcome["child"]
    assert child["phase"] == "grid"
    assert child["requestKey"] == f"load:{op_id}:grid:{START}"
    assert child["endExclusive"] == "2023-09-14"
    assert len(child["jobs"]) == 1

    detail = client.get(f"{BASE}/{op_id}")
    assert detail.status_code == 200
    children = detail.json()["children"]
    assert children[0]["jobs"][0]["status"] == "QUEUED"
    assert detail.json()["phase"] == "price"  # 10-day range: grid done

    # Pause → dispatch conflicts → resume → price chunk dispatches.
    paused = client.post(f"{BASE}/{op_id}/pause", headers=headers)
    assert paused.json()["status"] == "paused"
    assert client.post(f"{BASE}/{op_id}/dispatch", headers=headers).status_code == 409
    assert client.post(f"{BASE}/{op_id}/pause", headers=headers).status_code == 409
    resumed = client.post(f"{BASE}/{op_id}/resume", headers=headers)
    assert resumed.json()["status"] == "dispatching"
    second = client.post(f"{BASE}/{op_id}/dispatch", headers=headers).json()
    assert second["child"]["phase"] == "price"
    assert len(second["child"]["jobs"]) == 10  # per-day price jobs

    listing = client.get(BASE)
    assert listing.status_code == 200
    assert listing.json()[0]["id"] == op_id


def test_viewer_reads_but_cannot_dispatch(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    # Automation creates the operation; the viewer sees label not actor.
    created = client.post(BASE, json=BODY, headers=BEARER)
    assert created.status_code == 201
    op_id = created.json()["id"]
    assert created.json()["actor"].startswith("operator:")

    _viewer(client, scratch_db)
    assert client.get(BASE).status_code == 200
    detail = client.get(f"{BASE}/{op_id}")
    assert detail.status_code == 200
    assert detail.json()["actor"] == "Operator"

    for path in (
        BASE,
        f"{BASE}/{op_id}/dispatch",
        f"{BASE}/{op_id}/pause",
        f"{BASE}/{op_id}/resume",
    ):
        response = client.post(
            path,
            json=BODY,
            headers={"x-csrf-token": "x", "Origin": "http://testserver"},
        )
        assert response.status_code == 403, path
        assert response.json()["code"] == "FORBIDDEN"


def test_anonymous_and_missing_operation(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    assert client.get(BASE).status_code == 401
    assert client.post(BASE, json=BODY).status_code == 401
    _viewer(client, scratch_db)
    missing = uuid.uuid4()
    assert client.get(f"{BASE}/{missing}").status_code == 404
    assert (
        client.post(
            f"{BASE}/{missing}/dispatch",
            headers={"x-csrf-token": "x", "Origin": "http://testserver"},
        ).status_code
        == 403  # viewer write denied on capability before existence check
    )


def test_cookie_writes_need_csrf(client: TestClient, scratch_db: sa.Engine) -> None:
    _owner_headers(client, scratch_db)
    assert client.post(BASE, json=BODY).status_code == 403


def test_begin_validates_bounds(client: TestClient, scratch_db: sa.Engine) -> None:
    headers = _owner_headers(client, scratch_db)
    over = {
        "region": "NSW1",
        "startDay": START,
        "endExclusive": "2024-09-30",
    }  # >366 days
    assert client.post(BASE, json=over, headers=headers).status_code == 400
    inverted = {
        "region": "NSW1",
        "startDay": "2023-09-10",
        "endExclusive": "2023-09-01",
    }
    assert client.post(BASE, json=inverted, headers=headers).status_code == 400
