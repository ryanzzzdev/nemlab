"""NEM-083/084/086 — discovery HTTP tests: corrected durations, typed
sorts/filters, publication-wide highlights and bounded previews."""

from datetime import timedelta
from decimal import Decimal

import pytest
import sqlalchemy as sa
from starlette.testclient import TestClient
from test_events_http import BASE, DAY, DAY2, _seed

from nemlab_core.prices import Region
from nemlab_infrastructure.grid.events import GridCatalogue


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


# -- NEM-083: duration semantics ------------------------------------------------


def test_demand_ramp_duration_is_elapsed_span(client: TestClient, published) -> None:
    """37 observations span 36 five-minute intervals = 180 minutes."""
    events = client.get(f"{BASE}?region=NSW1").json()["events"]
    ramp = next(e for e in events if e["type"] == "demand_ramp")
    assert ramp["intervalCount"] == 37
    assert ramp["durationMinutes"] == 180


def test_run_and_spike_durations_count_intervals(client: TestClient, published) -> None:
    events = client.get(f"{BASE}?region=NSW1").json()["events"]
    run = next(e for e in events if e["type"] == "negative_price_run")
    assert run["intervalCount"] == 3 and run["durationMinutes"] == 15
    spikes = [e for e in events if e["type"] == "price_spike"]
    assert all(e["durationMinutes"] == e["intervalCount"] * 5 for e in spikes)


# -- NEM-084: typed sorts and filters --------------------------------------------


def test_highest_sort_orders_by_value(client: TestClient, published) -> None:
    body = client.get(f"{BASE}?region=NSW1&type=price_spike&sort=highest").json()
    values = [e["value"] for e in body["events"]]
    assert values == ["2000", "1500"]


def test_sort_requires_supported_type(client: TestClient, published) -> None:
    assert client.get(f"{BASE}?region=NSW1&sort=highest").status_code == 400
    assert (
        client.get(
            f"{BASE}?region=NSW1&type=negative_price_run&sort=highest"
        ).status_code
        == 400
    )
    assert (
        client.get(f"{BASE}?region=NSW1&type=price_spike&sort=oldest").status_code
        == 400
    )
    assert client.get(f"{BASE}?region=NSW1&sort=bogus").status_code == 400


def test_oldest_sort_reverses(client: TestClient, published) -> None:
    newest = client.get(f"{BASE}?region=NSW1").json()["events"]
    oldest = client.get(f"{BASE}?region=NSW1&sort=oldest").json()["events"]
    assert [e["id"] for e in oldest] == [e["id"] for e in reversed(newest)]


def test_numeric_filters(client: TestClient, published) -> None:
    deep = client.get(f"{BASE}?region=NSW1&type=price_spike&valueGte=1800").json()
    assert [e["value"] for e in deep["events"]] == ["2000"]
    assert deep["matchingTotal"] == 1
    assert deep["typeTotals"]["price_spike"] == 1

    runs = client.get(f"{BASE}?region=NSW1&type=negative_price_run&valueLte=-8").json()
    assert runs["events"] == [] and runs["matchingTotal"] == 0
    runs = client.get(f"{BASE}?region=NSW1&type=negative_price_run&valueLte=-7").json()
    assert len(runs["events"]) == 1

    assert (
        client.get(f"{BASE}?region=NSW1&type=price_spike&valueLte=-5").status_code
        == 400
    )
    assert client.get(f"{BASE}?region=NSW1&valueGte=100").status_code == 400


def test_min_duration_filter(client: TestClient, published) -> None:
    body = client.get(
        f"{BASE}?region=NSW1&type=negative_price_run&minDurationMinutes=16"
    ).json()
    assert body["events"] == []
    body = client.get(
        f"{BASE}?region=NSW1&type=negative_price_run&minDurationMinutes=15"
    ).json()
    assert len(body["events"]) == 1
    assert (
        client.get(
            f"{BASE}?region=NSW1&type=demand_ramp&minDurationMinutes=60"
        ).status_code
        == 400
    )


def test_cursor_binds_query_fingerprint(client: TestClient, published) -> None:
    first = client.get(
        f"{BASE}?region=NSW1&type=price_spike&sort=highest&limit=1"
    ).json()
    cursor = first["nextCursor"]
    assert cursor is not None
    # same query continues
    ok = client.get(f"{BASE}?region=NSW1&type=price_spike&sort=highest&cursor={cursor}")
    assert ok.status_code == 200
    assert [e["value"] for e in ok.json()["events"]] == ["1500"]
    # a different query rejects the cursor
    changed = client.get(
        f"{BASE}?region=NSW1&type=price_spike&sort=newest&cursor={cursor}"
    )
    assert changed.status_code == 400
    dropped = client.get(f"{BASE}?region=NSW1&cursor={cursor}")
    assert dropped.status_code == 400


def test_matching_total_counts_whole_scope(client: TestClient, published) -> None:
    body = client.get(f"{BASE}?region=NSW1&limit=1").json()
    assert body["matchingTotal"] == 4
    assert body["typeTotals"]["price_spike"] == 2


# -- highlights -------------------------------------------------------------------


def test_highlights_response(client: TestClient, published) -> None:
    response = client.get(f"{BASE}/highlights?region=NSW1")
    assert response.status_code == 200
    body = response.json()
    assert body["selectionVersion"] == "highlights-v2"
    assert body["publication"]["region"] == "NSW1"
    assert body["matchingTotal"] == 4
    highlights = body["highlights"]
    # The 1500 spike is per-day capped: the run and ramp already fill its day.
    assert len(highlights) == 3
    by_reason = {h["selectedBy"] for h in highlights}
    assert "highest_price" in by_reason
    top = next(h for h in highlights if h["selectedBy"] == "highest_price")
    assert top["value"] == "2000"
    assert top["reasons"][0]["code"] == "highest_price"
    assert top["reasons"][0]["rank"] == 1
    assert top["reasons"][0]["population"] == 2


def test_highlights_scoped_and_typed(client: TestClient, published) -> None:
    body = client.get(f"{BASE}/highlights?region=NSW1&type=negative_price_run").json()
    assert all(h["type"] == "negative_price_run" for h in body["highlights"])
    assert body["typeTotals"]["negative_price_run"] == 1
    assert client.get(f"{BASE}/highlights?region=VIC1").status_code == 404


# -- preview ---------------------------------------------------------------------


def test_preview_bounded_shape(client: TestClient, published) -> None:
    events = client.get(f"{BASE}?region=NSW1").json()["events"]
    spike = next(
        e
        for e in events
        if e["type"] == "price_spike" and e["marketDay"] == "2023-09-04"
    )
    response = client.get(f"{BASE}/{spike['id']}/preview")
    assert response.status_code == 200
    preview = response.json()
    assert preview["version"] == "preview-v1"
    assert preview["metric"] == "price"
    assert preview["unit"] == "AUD/MWh"
    assert len(preview["slots"]) <= 48
    assert preview["sourcePoints"] >= preview["eventRanges"][0]["endSlot"]
    assert any(s["max"] == "1500" for s in preview["slots"])
    assert (
        client.get(f"{BASE}/00000000-0000-0000-0000-000000000000/preview").status_code
        == 404
    )


def test_preview_for_ramp_uses_demand(client: TestClient, published) -> None:
    events = client.get(f"{BASE}?region=NSW1").json()["events"]
    ramp = next(e for e in events if e["type"] == "demand_ramp")
    preview = client.get(f"{BASE}/{ramp['id']}/preview").json()
    assert preview["metric"] == "demand" and preview["unit"] == "MW"
    assert any(s["max"] == "5600" for s in preview["slots"])
