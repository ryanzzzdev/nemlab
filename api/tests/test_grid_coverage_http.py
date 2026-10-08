"""Grid-coverage operator endpoint — bearer-authenticated bounded reads."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import sqlalchemy as sa
from fastapi.testclient import TestClient

from nemlab_core.prices import Region
from nemlab_infrastructure.grid.batch import GridBatch, Metric, Slot
from nemlab_infrastructure.grid.source import GridFetch
from nemlab_infrastructure.grid.store import GridStore
from nemlab_infrastructure.prices.batch import Kind
from nemlab_infrastructure.prices.batch import hash as response_hash

BASE = "/api/admin/v1/grid-coverage"
TOKEN = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
DAY = date(2023, 9, 4)
AT = datetime(2026, 9, 17, tzinfo=UTC)
WINDOW = "start=2023-09-04&endExclusive=2023-09-06"


def _save(store: GridStore, day: date, batches: list[GridBatch]) -> None:
    store.save(GridFetch(tuple(batches), AT, response_hash("coverage"), "test-1"))


def _market(
    day: date, value: Decimal = Decimal("5000"), missing: tuple[int, ...] = ()
) -> list[GridBatch]:
    return [
        GridBatch(
            Region.NSW1,
            metric,
            "",
            day,
            tuple(
                Slot(Kind.MISSING, None) if i in missing else Slot(Kind.VALUE, value)
                for i in range(288)
            ),
        )
        for metric in (Metric.DEMAND, Metric.FLOW_IMPORTS, Metric.FLOW_EXPORTS)
    ]


def _power(day: date, fueltech: str) -> GridBatch:
    return GridBatch(
        Region.NSW1,
        Metric.POWER,
        fueltech,
        day,
        tuple(Slot(Kind.VALUE, Decimal("12")) for _ in range(288)),
    )


def test_unauthenticated_requests_are_rejected(client: TestClient) -> None:
    assert client.get(f"{BASE}/NSW1?{WINDOW}").status_code == 401


def test_rejects_invalid_windows(client: TestClient) -> None:
    invalid = (
        f"{BASE}/NSW1?{WINDOW.replace('2023-09-06', '2023-09-04')}",  # empty
        f"{BASE}/NSW1?start=2023-09-04&endExclusive=2023-10-06",  # > 31 days
        f"{BASE}/NSW1?start=2021-09-30&endExclusive=2021-10-01",  # pre-floor
        f"{BASE}/NSW1?start=2023-09-04&endExclusive=2200-01-01",  # incomplete
        f"{BASE}/NSW1?start=2023-09-04",  # missing endExclusive
        f"{BASE}/NSW1?start=20230904&endExclusive=2023-09-06",  # strict ISO
        f"{BASE}/BOGUS?{WINDOW}",  # unknown region
    )
    for route in invalid:
        response = client.get(route, headers=AUTH)
        assert response.status_code == 400, route
        assert response.json()["code"] == "INVALID_REQUEST"


def test_empty_coverage_marks_every_day_not_imported(
    client: TestClient,
) -> None:
    response = client.get(f"{BASE}/NSW1?{WINDOW}", headers=AUTH)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["region"] == "NSW1" and body["marketOffset"] == "+10:00"
    assert [d["day"] for d in body["days"]] == ["2023-09-04", "2023-09-05"]
    for day in body["days"]:
        assert day["availability"] == "NOT_IMPORTED"
        assert [s["metric"] for s in day["series"]] == [
            "demand",
            "flow_imports",
            "flow_exports",
        ]
        assert all(
            s["series"] == ""
            and s["availability"] == "NOT_IMPORTED"
            and s["revision"] is None
            and s["valid"] is None
            for s in day["series"]
        )


def test_stored_series_and_partial_days(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    store = GridStore(scratch_db)
    _save(store, DAY, [*_market(DAY), _power(DAY, "wind"), _power(DAY, "solar")])
    _save(store, DAY + timedelta(days=1), _market(DAY + timedelta(days=1))[:1])
    response = client.get(f"{BASE}/NSW1?{WINDOW}", headers=AUTH)
    assert response.status_code == 200
    complete, partial = response.json()["days"]

    assert complete["availability"] == "COMPLETE"
    assert [s["series"] for s in complete["series"]] == ["", "", "", "solar", "wind"]
    demand = complete["series"][0]
    assert demand["availability"] == "COMPLETE" and demand["valid"] == 288
    assert demand["retrievedAt"] == "2026-09-17T00:00:00Z"
    assert complete["series"][3]["metric"] == "power"

    # Only demand stored on the second day — required metrics stay explicit.
    assert partial["availability"] == "PARTIAL"
    by_metric = {s["metric"]: s for s in partial["series"]}
    assert by_metric["demand"]["availability"] == "COMPLETE"
    assert by_metric["flow_imports"]["availability"] == "NOT_IMPORTED"


def test_incomplete_series_is_not_complete(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    _save(GridStore(scratch_db), DAY, _market(DAY, missing=(5,)))
    response = client.get(f"{BASE}/NSW1?{WINDOW}", headers=AUTH)
    day = response.json()["days"][0]
    assert day["availability"] == "PARTIAL"
    demand = day["series"][0]
    assert demand["availability"] == "INCOMPLETE"
    assert demand["missing"] == 1 and demand["valid"] == 287


def test_storage_failure_returns_safe_error(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    with scratch_db.begin() as conn:
        conn.execute(sa.text("ALTER TABLE grid_current RENAME TO missing_current"))
    try:
        response = client.get(f"{BASE}/NSW1?{WINDOW}", headers=AUTH)
        assert response.status_code == 503
        assert response.json()["code"] == "STORAGE_UNAVAILABLE"
        assert "SELECT" not in response.text
    finally:
        with scratch_db.begin() as conn:
            conn.execute(sa.text("ALTER TABLE missing_current RENAME TO grid_current"))


def _demand_days(
    store: GridStore, start: date, count: int, *, missing: bool = False
) -> None:
    for offset in range(count):
        day = start + timedelta(days=offset)
        _save(
            store,
            day,
            [
                GridBatch(
                    Region.NSW1,
                    Metric.DEMAND,
                    "",
                    day,
                    tuple(
                        Slot(Kind.MISSING, None)
                        if missing
                        else Slot(Kind.VALUE, Decimal("5000"))
                        for _ in range(288)
                    ),
                )
            ],
        )


def test_baseline_readiness_route(client: TestClient, scratch_db: sa.Engine) -> None:
    store = GridStore(scratch_db)
    baseline_start = DAY - timedelta(days=90)
    _demand_days(store, baseline_start, 60)
    response = client.get(
        f"{BASE}/NSW1/baseline?startDay=2023-09-04&endExclusive=2023-09-05",
        headers=AUTH,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["baselineDays"] == 90
    assert body["minCompleteDays"] == 60
    assert body["minClassDays"] == 20
    day = body["days"][0]
    assert day["day"] == "2023-09-04"
    assert day["completeDays"] == 60
    # 60 consecutive days contain 44 same-class days — ready against the
    # 60/20 thresholds.
    assert day["classDays"] == 44
    assert day["ready"] is True


def test_baseline_readiness_window_shift(
    client: TestClient, scratch_db: sa.Engine
) -> None:
    store = GridStore(scratch_db)
    _demand_days(store, DAY - timedelta(days=90), 61)
    body = client.get(
        f"{BASE}/NSW1/baseline?startDay=2023-09-04&endExclusive=2023-09-06",
        headers=AUTH,
    ).json()
    # Day one's window covers all 61 seeded days; day two's window drops
    # the oldest baseline day and picks up day one (unseeded) — per-day
    # windows, not a single window-level count.
    assert [d["completeDays"] for d in body["days"]] == [61, 60]


def test_baseline_rejects_bad_windows(client: TestClient) -> None:
    invalid = (
        f"{BASE}/NSW1/baseline?startDay=2023-09-05&endExclusive=2023-09-04",
        f"{BASE}/NSW1/baseline?startDay=2023-09-04&endExclusive=2023-10-10",
        # Baseline reaching before the earliest market day.
        f"{BASE}/NSW1/baseline?startDay=2021-10-01&endExclusive=2021-10-02",
    )
    for route in invalid:
        response = client.get(route, headers=AUTH)
        assert response.status_code == 400, route


def test_baseline_requires_auth(client: TestClient) -> None:
    response = client.get(
        f"{BASE}/NSW1/baseline?startDay=2023-09-04&endExclusive=2023-09-05"
    )
    assert response.status_code == 401
