"""Ported ``PriceReadHttpTest`` — public price reads over a real scratch DB."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import sqlalchemy as sa
from fastapi.testclient import TestClient

from nemlab_core.prices import Region
from nemlab_infrastructure.prices.batch import Kind, PriceBatch, Slot
from nemlab_infrastructure.prices.batch import hash as response_hash
from nemlab_infrastructure.prices.source import Fetch
from nemlab_infrastructure.prices.store import PriceStore

DAY = date(2023, 10, 1)
RETRIEVED = datetime(2026, 9, 18, tzinfo=UTC)


def save(
    store: PriceStore, day: date, incomplete: bool, first: str, retrieved: datetime
) -> None:
    slots = [Slot(Kind.VALUE, Decimal(first))] * 288
    slots[1] = Slot(Kind.VALUE, Decimal("-25"))
    slots[2] = Slot(Kind.VALUE, Decimal(0))
    if incomplete:
        slots[3] = Slot(Kind.MISSING, None)
        slots[4] = Slot(Kind.SOURCE_NULL, None)
    store.save(
        Fetch(
            PriceBatch(Region.NSW1, day, tuple(slots)),
            retrieved,
            response_hash(f"fixture-{first}"),
            "test-1",
        )
    )


_COUNTS = {
    "refresh_job": "SELECT count(*) FROM refresh_job",
    "refresh_job_event": "SELECT count(*) FROM refresh_job_event",
    "price_import_attempt": "SELECT count(*) FROM price_import_attempt",
    "price_current": "SELECT count(*) FROM price_current",
}


def _count(engine: sa.Engine, table: str) -> int:
    with engine.connect() as conn:
        return conn.execute(sa.text(_COUNTS[table])).scalar_one()


def test_coverage_includes_complete_incomplete_and_unimported_days(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    store = PriceStore(scratch_db)
    save(store, DAY, False, "42.5", RETRIEVED)
    save(store, DAY.replace(day=2), True, "42.5", RETRIEVED)
    response = client.get(
        "/api/v1/prices/NSW1/coverage?start=2023-10-01&endExclusive=2023-10-04"
    )
    assert response.status_code == 200
    days = response.json()["days"]
    assert len(days) == 3
    assert days[0]["availability"] == "COMPLETE"
    assert days[0]["valid"] == 288
    assert days[1]["availability"] == "INCOMPLETE"
    assert days[1]["valid"] == 286
    assert days[1]["missing"] == 1
    assert days[1]["sourceNull"] == 1
    assert days[2]["availability"] == "NOT_IMPORTED"
    assert days[2]["revision"] is None
    assert days[2]["missing"] is None


def test_series_preserves_exact_values_states_and_nem_time(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    save(PriceStore(scratch_db), DAY, True, "123.4567890123456789", RETRIEVED)
    response = client.get("/api/v1/prices/NSW1/2023-10-01")
    assert response.status_code == 200
    assert "no-store" in response.headers["cache-control"]
    body = response.json()
    assert body["unit"] == "AUD/MWh"
    assert body["marketOffset"] == "+10:00"
    assert body["intervalLabel"] == "END"
    assert body["intervalSeconds"] == 300
    intervals = body["intervals"]
    assert len(intervals) == 288
    assert intervals[0]["start"] == "2023-09-30T14:00:00Z"
    assert intervals[287]["end"] == "2023-10-01T14:00:00Z"
    assert intervals[0]["price"] == "123.4567890123456789"
    assert isinstance(intervals[0]["price"], str)
    assert intervals[1]["price"] == "-25"
    assert intervals[2]["price"] == "0"
    assert intervals[3]["state"] == "MISSING"
    assert intervals[4]["state"] == "SOURCE_NULL"
    assert intervals[3]["price"] is None
    assert intervals[4]["price"] is None


def test_corrections_advance_current_revision_but_leave_old_snapshot_intact(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    store = PriceStore(scratch_db)
    save(store, DAY, False, "10", RETRIEVED)
    old = store.coverage(Region.NSW1, DAY)
    assert old is not None
    snapshot = store.snapshot(old.revision)
    save(store, DAY, False, "99", RETRIEVED + timedelta(seconds=1))
    result = client.get("/api/v1/prices/NSW1/2023-10-01").json()
    assert result["coverage"]["revision"] != str(old.revision)
    assert result["intervals"][0]["price"] == "99"
    assert store.snapshot_prices(snapshot).intervals[0].price == Decimal("10")


def test_missing_series_returns_404_and_does_not_create_jobs(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    response = client.get("/api/v1/prices/NSW1/2023-10-01")
    assert response.status_code == 404
    assert response.json()["code"] == "PRICE_DAY_NOT_IMPORTED"
    assert _count(scratch_db, "refresh_job") == 0
    assert _count(scratch_db, "price_import_attempt") == 0
    assert client.post("/api/v1/prices/NSW1/2023-10-01").status_code == 404
    assert client.get("/api/admin/v1/price-refreshes").status_code == 401


def test_validates_region_dates_and_range_limits(client: TestClient) -> None:
    for path in (
        "/api/v1/prices/BOGUS/2023-10-01",
        "/api/v1/prices/NSW1/not-a-day",
        "/api/v1/prices/NSW1/2200-01-01",
        "/api/v1/prices/NSW1/2020-01-01",
        "/api/v1/prices/NSW1/coverage?start=2023-10-01",
        "/api/v1/prices/NSW1/coverage?start=2023-10-01&endExclusive=2023-10-01",
        "/api/v1/prices/NSW1/coverage?start=2023-10-01&endExclusive=2023-11-02",
    ):
        response = client.get(path)
        assert response.status_code == 400, path
        assert response.json() == {
            "code": "INVALID_REQUEST",
            "message": "Use a valid region and 1\u201331 completed market days"
            " since 2021-10-01",
        }
    maximum = client.get(
        "/api/v1/prices/NSW1/coverage?start=2023-10-01&endExclusive=2023-11-01"
    )
    assert len(maximum.json()["days"]) == 31


def test_database_failure_returns_safe_503(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    with scratch_db.begin() as conn:
        conn.execute(
            sa.text("ALTER TABLE price_current RENAME TO missing_price_current")
        )
    try:
        response = client.get("/api/v1/prices/NSW1/2023-10-01")
        assert response.status_code == 503
        assert response.json()["code"] == "STORAGE_UNAVAILABLE"
        assert "jdbc:" not in response.text
        assert "SELECT" not in response.text
    finally:
        with scratch_db.begin() as conn:
            conn.execute(
                sa.text("ALTER TABLE missing_price_current RENAME TO price_current")
            )
