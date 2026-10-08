"""NEM-058 grid-publication HTTP tests — operator detection runs."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from nemlab_core.prices import Region
from nemlab_infrastructure.prices.batch import Kind, PriceBatch, Slot, hash
from nemlab_infrastructure.prices.source import Fetch
from nemlab_infrastructure.prices.store import PriceStore

DAY = date(2023, 9, 4)
AT = datetime(2026, 9, 17, tzinfo=UTC)
TOKEN = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG"
AUTH = {"Authorization": "Bearer " + TOKEN}


@pytest.fixture
def scratch_url(scratch_db: sa.Engine) -> sa.Engine:
    return scratch_db


def _seed_price(engine: sa.Engine, day: date, prices: list[Decimal]) -> None:
    PriceStore(engine).save(
        Fetch(
            PriceBatch(
                Region.NSW1,
                day,
                tuple(Slot(Kind.VALUE, v) for v in prices),
            ),
            AT,
            hash(f"price-{day}-{prices[0]}"),
            "t-1",
        )
    )


def test_publish_list_detail(client: TestClient, scratch_url: sa.Engine) -> None:
    prices = [Decimal("50")] * 288
    prices[10] = prices[11] = prices[12] = Decimal("-7")
    _seed_price(scratch_url, DAY, prices)
    created = client.post(
        "/api/admin/v1/grid-publications",
        json={
            "region": "NSW1",
            "startDay": "2023-09-04",
            "endExclusive": "2023-09-05",
        },
        headers=AUTH,
    )
    assert created.status_code == 201
    body = created.json()
    assert body["eventCount"] == 1
    assert body["detectorVersion"] == "v1"
    assert body["coverage"]["2023-09-04"]["price"]["missing"] == 0
    listing = client.get("/api/admin/v1/grid-publications", headers=AUTH)
    assert listing.status_code == 200
    assert listing.json()[0]["id"] == body["id"]
    detail = client.get(f"/api/admin/v1/grid-publications/{body['id']}", headers=AUTH)
    assert detail.json()["eventCount"] == 1


def test_publish_requires_auth(client: TestClient) -> None:
    response = client.post(
        "/api/admin/v1/grid-publications",
        json={
            "region": "NSW1",
            "startDay": "2023-09-04",
            "endExclusive": "2023-09-05",
        },
    )
    assert response.status_code == 401


def test_publish_rejects_bad_window(client: TestClient) -> None:
    response = client.post(
        "/api/admin/v1/grid-publications",
        json={
            "region": "NSW1",
            "startDay": "2023-09-05",
            "endExclusive": "2023-09-04",
        },
        headers=AUTH,
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_REQUEST"


def test_publication_not_found(client: TestClient) -> None:
    response = client.get(
        "/api/admin/v1/grid-publications/00000000-0000-0000-0000-000000000000",
        headers=AUTH,
    )
    assert response.status_code == 404
    assert response.json()["code"] == "PUBLICATION_NOT_FOUND"


def test_publication_provenance_and_attempts(
    client: TestClient, scratch_url: sa.Engine
) -> None:
    _seed_price(scratch_url, DAY, [Decimal("50")] * 288)
    created = client.post(
        "/api/admin/v1/grid-publications",
        json={
            "region": "NSW1",
            "startDay": "2023-09-04",
            "endExclusive": "2023-09-05",
            "attemptKey": "ui-attempt-1",
        },
        headers=AUTH,
    )
    assert created.status_code == 201
    body = created.json()
    assert body["runId"] is not None
    assert body["actor"] == "Operator"  # bearer identity -> role label
    assert body["attemptKey"] == "ui-attempt-1"

    attempts = client.get("/api/admin/v1/grid-publications/attempts", headers=AUTH)
    assert attempts.status_code == 200
    run = attempts.json()[0]
    assert run["id"] == body["runId"]
    assert run["status"] == "COMPLETE"
    assert run["publicationId"] == body["id"]
    assert run["attemptKey"] == "ui-attempt-1"
    assert run["actor"] == "Operator"

    detail = client.get(
        f"/api/admin/v1/grid-publications/{body['id']}", headers=AUTH
    ).json()
    assert detail["runId"] == body["runId"]
    assert detail["attemptKey"] == "ui-attempt-1"
    assert detail["eventCounts"] == {}
    assert detail["highlights"]["version"] == "highlights-v2"
    assert detail["highlights"]["selected"] == 0
    assert detail["highlights"]["excluded"] == 0


def test_event_counts_in_detail(client: TestClient, scratch_url: sa.Engine) -> None:
    prices = [Decimal("50")] * 288
    prices[10] = prices[11] = prices[12] = Decimal("-7")
    _seed_price(scratch_url, DAY, prices)
    created = client.post(
        "/api/admin/v1/grid-publications",
        json={
            "region": "NSW1",
            "startDay": "2023-09-04",
            "endExclusive": "2023-09-05",
        },
        headers=AUTH,
    )
    detail = client.get(
        f"/api/admin/v1/grid-publications/{created.json()['id']}", headers=AUTH
    ).json()
    assert detail["eventCounts"] == {"negative_price_run": 1}
    assert detail["highlights"]["eligible"] == 1
    assert detail["highlights"]["totals"]["negative_price_run"] == 1


def test_attempts_require_auth(client: TestClient) -> None:
    assert client.get("/api/admin/v1/grid-publications/attempts").status_code == 401
