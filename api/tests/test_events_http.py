"""NEM-059 public catalogue/replay HTTP tests.

Read-only public endpoints over published immutable event versions —
publication itself is seeded through the infrastructure layer.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from nemlab_core.prices import Region
from nemlab_infrastructure.grid.batch import GridBatch, Metric
from nemlab_infrastructure.grid.batch import Slot as GridSlot
from nemlab_infrastructure.grid.events import GridCatalogue
from nemlab_infrastructure.grid.source import GridFetch
from nemlab_infrastructure.grid.store import GridStore
from nemlab_infrastructure.prices.batch import Kind, PriceBatch, Slot, hash
from nemlab_infrastructure.prices.source import Fetch
from nemlab_infrastructure.prices.store import PriceStore

BASE = "/api/v1/events"
DAY = date(2023, 9, 4)
DAY2 = date(2023, 9, 5)
AT = datetime(2026, 9, 17, tzinfo=UTC)


def _seed(
    engine: sa.Engine,
    day: date,
    prices: list[Decimal | None],
    demand: list[Decimal] | None = None,
) -> None:
    PriceStore(engine).save(
        Fetch(
            PriceBatch(
                Region.NSW1,
                day,
                tuple(
                    Slot(Kind.VALUE if v is not None else Kind.MISSING, v)
                    for v in prices
                ),
            ),
            AT,
            hash(f"price-{day}-{prices[0]}"),
            "t-1",
        )
    )
    flat = [Decimal("12")] * 288
    flat_slots = tuple(GridSlot(Kind.VALUE, v) for v in flat)
    demand_slots = tuple(
        GridSlot(Kind.VALUE, v) for v in (demand or [Decimal("5000")] * 288)
    )
    GridStore(engine).save(
        GridFetch(
            (
                GridBatch(Region.NSW1, Metric.DEMAND, "", day, demand_slots),
                GridBatch(Region.NSW1, Metric.FLOW_IMPORTS, "", day, flat_slots),
                GridBatch(Region.NSW1, Metric.FLOW_EXPORTS, "", day, flat_slots),
            ),
            AT,
            hash(f"grid-{day}"),
            "t-1",
        )
    )


@pytest.fixture
def published(scratch_db: sa.Engine, clean: None) -> GridCatalogue:
    prices = [Decimal("50")] * 288
    prices[10] = prices[11] = prices[12] = Decimal("-7")
    prices[100] = Decimal("1500")
    ramp = [Decimal("5000")] * 36 + [Decimal("5600")] * 252
    _seed(scratch_db, DAY, prices, demand=ramp)
    day2 = [Decimal("50")] * 288
    day2[200] = Decimal("2000")
    _seed(scratch_db, DAY2, day2)
    catalogue = GridCatalogue(scratch_db)
    catalogue.publish(Region.NSW1, DAY, DAY2 + timedelta(days=1))
    return catalogue


def test_list_requires_publication(client: TestClient) -> None:
    response = client.get(f"{BASE}?region=NSW1")
    assert response.status_code == 404
    assert response.json()["code"] == "CATALOGUE_NOT_PUBLISHED"


def test_list_events(client: TestClient, published: GridCatalogue) -> None:
    response = client.get(f"{BASE}?region=NSW1")
    assert response.status_code == 200
    body = response.json()
    assert body["publication"]["region"] == "NSW1"
    assert body["publication"]["coverage"]["2023-09-04"]["price"]["missing"] == 0
    types = {e["type"] for e in body["events"]}
    assert {"negative_price_run", "price_spike", "demand_ramp"} <= types
    for event in body["events"]:
        assert event["detectorVersion"] == "v1"
        assert event["value"] is not None
    assert body["nextCursor"] is None


def test_list_type_filter(client: TestClient, published: GridCatalogue) -> None:
    response = client.get(f"{BASE}?region=NSW1&type=price_spike")
    events = response.json()["events"]
    assert events and all(e["type"] == "price_spike" for e in events)


def test_list_date_overlap(client: TestClient, published: GridCatalogue) -> None:
    both = client.get(f"{BASE}?region=NSW1&from=2023-09-04&to=2023-09-05")
    first = client.get(f"{BASE}?region=NSW1&from=2023-09-04&to=2023-09-04")
    assert {e["marketDay"] for e in both.json()["events"]} == {
        "2023-09-04",
        "2023-09-05",
    }
    assert {e["marketDay"] for e in first.json()["events"]} == {"2023-09-04"}


def test_pagination_pinned_across_republication(
    client: TestClient, published: GridCatalogue, scratch_db: sa.Engine
) -> None:
    first = client.get(f"{BASE}?region=NSW1&limit=1").json()
    assert first["nextCursor"] is not None
    # Republish (identical inputs dedupe events) then continue with cursor.
    published.publish(Region.NSW1, DAY, DAY2 + timedelta(days=1))
    second = client.get(f"{BASE}?region=NSW1&cursor={first['nextCursor']}").json()
    assert second["events"]
    assert all(e["id"] != first["events"][0]["id"] for e in second["events"])
    seen = {e["id"] for e in first["events"] + second["events"]}
    rest = client.get(f"{BASE}?region=NSW1&limit=50").json()["events"]
    # Every event appears exactly once across the pinned pages.
    page_ids = (
        seen
        | {
            e["id"]
            for e in client.get(
                f"{BASE}?region=NSW1&cursor={second['nextCursor']}"
            ).json()["events"]
        }
        if second["nextCursor"]
        else seen
    )
    assert len(page_ids) == len(rest)


def test_detail_and_replay(client: TestClient, published: GridCatalogue) -> None:
    events = client.get(f"{BASE}?region=NSW1").json()["events"]
    event = next(
        e
        for e in events
        if e["type"] == "price_spike" and e["marketDay"] == "2023-09-04"
    )
    detail = client.get(f"{BASE}/{event['id']}").json()
    assert detail["detectorParams"]["threshold"] == "1000"
    assert detail["replay"]["startDay"] == "2023-09-04"
    replay = client.get(f"{BASE}/{event['id']}/replay").json()
    assert replay["event"]["id"] == event["id"]
    assert len(replay["payload"]["price"]["2023-09-04"]) == 288
    metrics = {s["metric"] for s in replay["manifest"]["series"]}
    assert {"price", "demand", "flow_imports", "flow_exports"} <= metrics


def test_replay_subwindow(client: TestClient, published: GridCatalogue) -> None:
    events = client.get(f"{BASE}?region=NSW1").json()["events"]
    event = next(
        e
        for e in events
        if e["type"] == "price_spike" and e["marketDay"] == "2023-09-04"
    )
    response = client.get(
        f"{BASE}/{event['id']}/replay?startDay=2023-09-04&endExclusive=2023-09-05"
    )
    assert response.status_code == 200
    payload = response.json()["payload"]["price"]
    assert list(payload) == ["2023-09-04"]
    # Outside the stored window → 400
    outside = client.get(
        f"{BASE}/{event['id']}/replay?startDay=2023-09-05&endExclusive=2023-09-08"
    )
    assert outside.status_code == 400


def test_superseded_event_id_still_reproducible(
    client: TestClient, published: GridCatalogue, scratch_db: sa.Engine
) -> None:
    events = client.get(f"{BASE}?region=NSW1").json()["events"]
    original = next(e for e in events if e["type"] == "negative_price_run")
    # Correction republish mints version 2; v1 id must stay readable.
    prices = [Decimal("50")] * 288
    prices[10] = prices[11] = prices[12] = Decimal("-9")
    PriceStore(scratch_db).save(
        Fetch(
            PriceBatch(
                Region.NSW1,
                DAY,
                tuple(Slot(Kind.VALUE, v) for v in prices),
            ),
            AT + timedelta(minutes=1),
            hash("correction"),
            "t-2",
        )
    )
    published.publish(Region.NSW1, DAY, DAY2 + timedelta(days=1))
    detail = client.get(f"{BASE}/{original['id']}").json()
    assert detail["value"] == "-7" and detail["superseded"] is True


def test_not_found_and_bad_inputs(client: TestClient, published: GridCatalogue) -> None:
    assert client.get(f"{BASE}/00000000-0000-0000-0000-000000000000").status_code == 404
    assert (
        client.get(f"{BASE}/00000000-0000-0000-0000-000000000000/replay").status_code
        == 404
    )
    assert client.get(f"{BASE}?region=NSW1&cursor=bogus").status_code == 400
    assert client.get(f"{BASE}?region=NSW1&limit=101").status_code == 400
    assert (
        client.get(f"{BASE}?region=NSW1&from=2023-09-05&to=2023-09-04").status_code
        == 400
    )
    # half a range is rejected
    assert client.get(f"{BASE}?region=NSW1&from=2023-09-04").status_code == 400
