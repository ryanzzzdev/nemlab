"""NEM-119 — admin simulation-inspection endpoints: security matrix and
bounded read projections over ``/api/admin/v1/simulations``."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from test_capabilities_http import (
    OWNER_EMAIL,
    VIEWER_EMAIL,
    _insert_request,
    _insert_viewer,
    _sign_in,
    _user_session,
)

from nemlab_core import comparison
from nemlab_core.prices import Region
from nemlab_core.request import (
    Costs,
    EfficiencyInput,
    SimulationRequest,
    Site,
    Windows,
)
from nemlab_infrastructure.admin.identity import AdminIdentity
from nemlab_infrastructure.prices.batch import Kind, PriceBatch, Slot
from nemlab_infrastructure.prices.batch import hash as response_hash
from nemlab_infrastructure.prices.source import Fetch
from nemlab_infrastructure.prices.store import PriceStore
from nemlab_infrastructure.simulations import SimulationJobs

BASE = "/api/admin/v1/simulations"
DAY = date(2023, 10, 1)
TOKEN = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG"
BEARER = {"Authorization": f"Bearer {TOKEN}"}
SCOPE = f"?region=NSW1&startDay={DAY}&endDay={DAY}"


@pytest.fixture(autouse=True)
def owner(scratch_db: sa.Engine) -> None:
    AdminIdentity(scratch_db).bootstrap_owner("Owner", OWNER_EMAIL)


def _request() -> SimulationRequest:
    return SimulationRequest(
        Region.NSW1,
        DAY,
        Site(
            Decimal(1),
            Decimal(0),
            Decimal(1),
            Decimal(0),
            Decimal(1),
            Decimal(1),
            Decimal(1),
            Decimal(1),
        ),
        EfficiencyInput(Decimal(1), Decimal(1), None),
        Costs(Decimal(0), Decimal(0), Decimal(0)),
        Windows(0, 5, 5, 10),
        None,
    )


@pytest.fixture
def simulation(scratch_db: sa.Engine) -> UUID:
    """One completed stored simulation to inspect."""
    store = PriceStore(scratch_db)
    store.save(
        Fetch(
            PriceBatch(
                Region.NSW1,
                DAY,
                tuple(Slot(Kind.VALUE, Decimal("42.5")) for _ in range(288)),
            ),
            datetime(2026, 9, 18, tzinfo=UTC),
            response_hash("catalogue-http"),
            "test-1",
        )
    )
    jobs = SimulationJobs(scratch_db)
    id = jobs.submit(_request())
    claim = jobs.claim()
    assert claim is not None
    input = jobs.input(id)
    jobs.complete(
        id,
        claim.token,
        comparison.run(input.parameters(), input.prices, input.versions.limits),
    )  # type: ignore[arg-type]
    return id


def test_identity_matrix(
    client: TestClient, scratch_db: sa.Engine, simulation: UUID
) -> None:
    # Anonymous: nothing.
    assert client.get(BASE + SCOPE).status_code == 401
    assert client.get(f"{BASE}/{simulation}").status_code == 401
    # Bearer automation: operational read.
    assert client.get(BASE + SCOPE, headers=BEARER).status_code == 200
    assert client.get(f"{BASE}/{simulation}", headers=BEARER).status_code == 200
    # Viewer session: same safe reads.
    _insert_viewer(scratch_db)
    _sign_in(client, scratch_db, VIEWER_EMAIL)
    assert client.get(BASE + SCOPE).status_code == 200
    assert client.get(f"{BASE}/{simulation}").status_code == 200
    # Applicant session: denied.
    request_id = _insert_request(scratch_db, "applicant@example.test", "pending")
    import hashlib

    raw = "applicant-raw"
    with scratch_db.begin() as conn:
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
    assert client.get(BASE + SCOPE).status_code == 403


def test_expired_and_revoked_grants_deny(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    user_id = _insert_viewer(scratch_db, grant="expired")
    _user_session(client, scratch_db, user_id)
    assert client.get(BASE + SCOPE).status_code == 401

    # An active grant admits the session; revoking blocks it mid-flight.
    client.cookies.clear()
    _insert_viewer(scratch_db, email="second@example.test")
    _sign_in(client, scratch_db, "second@example.test")
    assert client.get(BASE + SCOPE).status_code == 200
    with scratch_db.begin() as conn:
        conn.execute(
            sa.text(
                "UPDATE admin_viewer_grant SET revoked_at = now(),"
                " revoked_by = (SELECT id FROM admin_user WHERE role = 'owner')"
                " WHERE user_id = (SELECT id FROM admin_user"
                "                WHERE email = 'second@example.test')"
            )
        )
    assert client.get(BASE + SCOPE).status_code == 401


def test_list_projection_and_filters(
    client: TestClient, scratch_db: sa.Engine, simulation: UUID
) -> None:
    _sign_in(client, scratch_db, OWNER_EMAIL)
    page = client.get(BASE + SCOPE)
    assert page.status_code == 200
    body = page.json()
    assert body["total"] == 1
    assert body["counts"] == {"QUEUED": 0, "RUNNING": 0, "SUCCEEDED": 1, "FAILED": 0}
    row = body["rows"][0]
    assert row["id"] == str(simulation)
    assert row["status"] == "SUCCEEDED"
    assert row["region"] == "NSW1" and row["day"] == str(DAY)
    assert row["strategies"] == ["fixed", "hindsight"]
    assert row["attempts"] == 1 and row["hasResult"]
    assert row["capacityMWh"] == "1"
    # Filters
    assert client.get(BASE + SCOPE + "&status=FAILED").json()["rows"] == []
    assert client.get(BASE + SCOPE + "&strategy=threshold").json()["rows"] == []
    assert client.get(BASE + SCOPE + "&status=SUCCEEDED").json()["total"] == 1
    # Outside the scope: empty, not an error.
    assert (
        client.get(BASE + "?region=NSW1&startDay=2023-10-02&endDay=2023-10-02").json()[
            "rows"
        ]
        == []
    )


def test_list_validation_errors_are_recoverable(
    client: TestClient, scratch_db: sa.Engine, simulation: UUID
) -> None:
    _sign_in(client, scratch_db, OWNER_EMAIL)
    for query in (
        "?region=NSW1",  # missing days
        "?region=NSW1&startDay=2023-10-02&endDay=2023-10-01",
        f"{SCOPE}&status=BOGUS",
        f"{SCOPE}&strategy=oracle",
        f"{SCOPE}&limit=0",
        f"{SCOPE}&limit=101",
        f"{SCOPE}&sort=sideways",
    ):
        response = client.get(BASE + query)
        assert response.status_code == 400, query
        assert response.json()["code"] in ("INVALID_SCOPE", "INVALID_REQUEST")
    cursor_page = client.get(BASE + SCOPE + "&cursor=junk")
    assert cursor_page.status_code == 400
    assert cursor_page.json()["code"] == "INVALID_CURSOR"


def test_detail_projection_lifecycle_and_provenance(
    client: TestClient, scratch_db: sa.Engine, simulation: UUID
) -> None:
    _sign_in(client, scratch_db, OWNER_EMAIL)
    response = client.get(f"{BASE}/{simulation}")
    assert response.status_code == 200
    body = response.json()
    assert body["simulation"]["id"] == str(simulation)
    assert body["scenario"]["request"]["region"] == "NSW1"
    assert body["scenario"]["versions"]["solver"]
    assert body["result"]["solver"]["status"] == "OPTIMAL"
    assert "fixed" in body["result"]["accounting"]
    assert body["execution"]["attempts"] == 1
    assert body["lifecycle"]["recorded"]
    assert [e["kind"] for e in body["lifecycle"]["events"]] == [
        "QUEUED",
        "CLAIMED",
        "SUCCEEDED",
    ]
    assert body["provenance"]["comparison"] == "matches"
    assert body["provenance"]["pinnedRevision"]
    # Malicious/unknown identifiers never bypass the projection.
    assert client.get(f"{BASE}/{uuid.uuid4()}").status_code == 404
    assert client.get(f"{BASE}/not-a-uuid").status_code == 400
    # Session cookie + bearer together are rejected — never dual credentials.
    assert client.get(f"{BASE}/{simulation}", headers=BEARER).status_code == 401
