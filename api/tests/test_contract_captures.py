"""Contract capture replay — the Python analogue of Java ``ContractCapture``.

Writes live TestClient responses to ``api/build/contract-responses/`` in the
same ``{method, path, status, headers, body}`` shape so ``verify.mjs``
validates them against the frozen OpenAPI schemas. Simulation evidence is
still produced by later milestones (NEM-076/077).
"""

import json
import shutil
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import sqlalchemy as sa
from fastapi.testclient import TestClient

from nemlab_core.prices import Region
from nemlab_infrastructure.jobs import RefreshJobService
from nemlab_infrastructure.prices.batch import Kind, PriceBatch, Slot
from nemlab_infrastructure.prices.batch import hash as response_hash
from nemlab_infrastructure.prices.source import Fetch
from nemlab_infrastructure.prices.store import PriceStore

CAPTURES = Path(__file__).resolve().parents[1] / "build" / "contract-responses"
TOKEN = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG"
BASE = "/api/admin/v1/price-refreshes"
DAY = date(2023, 10, 1)
RETRIEVED = datetime(2026, 9, 18, tzinfo=UTC)


def _record(method: str, path: str, response: httpx.Response) -> None:
    CAPTURES.mkdir(parents=True, exist_ok=True)
    capture = {
        "method": method.lower(),
        "path": path.split("?", 1)[0],
        "status": response.status_code,
        "headers": {
            name.lower(): response.headers.get_list(name)
            for name in dict.fromkeys(response.headers.keys())
        },
        "body": response.text,
    }
    (CAPTURES / f"{uuid.uuid4()}.json").write_text(json.dumps(capture))


def _save(store: PriceStore) -> None:
    slots = [Slot(Kind.VALUE, Decimal("42.5"))] * 288
    slots[3] = Slot(Kind.MISSING, None)
    slots[4] = Slot(Kind.SOURCE_NULL, None)
    store.save(
        Fetch(
            PriceBatch(Region.NSW1, DAY, tuple(slots)),
            RETRIEVED,
            response_hash("captures"),
            "test-1",
        )
    )


def test_contract_captures(
    client: TestClient, scratch_db: sa.Engine, clean: None
) -> None:
    shutil.rmtree(CAPTURES, ignore_errors=True)
    store = PriceStore(scratch_db)
    _save(store)
    auth = {"Authorization": f"Bearer {TOKEN}"}
    key = {"Idempotency-Key": "capture"}

    def get(path: str, headers: dict | None = None) -> httpx.Response:
        response = client.get(path, headers=headers)
        _record("GET", path, response)
        return response

    def post(
        path: str, body: object = None, headers: dict | None = None
    ) -> httpx.Response:
        if isinstance(body, dict):
            response = client.post(path, json=body, headers=headers)
        elif isinstance(body, str):
            response = client.post(path, content=body, headers=headers)
        else:
            response = client.post(path, headers=headers)
        _record("POST", path, response)
        return response

    # -- public price reads --------------------------------------------------
    get("/api/v1/prices/NSW1/coverage?start=2023-10-01&endExclusive=2023-10-04")
    get("/api/v1/prices/NSW1/coverage?start=2023-10-01")  # 400 INVALID_REQUEST
    get("/api/v1/prices/NSW1/2023-10-01")
    get("/api/v1/prices/NSW1/2023-10-02")  # 404 PRICE_DAY_NOT_IMPORTED

    # -- operator endpoints ---------------------------------------------------
    for route in (BASE, f"{BASE}/{uuid.uuid4()}", f"{BASE}/{uuid.uuid4()}/events"):
        get(route)
    post(BASE, {"region": "NSW1", "day": "2023-09-11"})
    post(f"{BASE}/{uuid.uuid4()}/cancel")

    submitted = post(BASE, {"region": "NSW1", "day": "2023-09-11"}, {**auth, **key})
    assert submitted.status_code == 202
    id = submitted.json()["id"]
    post(BASE, {"region": "NSW1", "day": "2023-09-12"}, {**auth, **key})  # 409
    post(
        BASE,
        "{",
        {**auth, "Idempotency-Key": "bad", "Content-Type": "application/json"},
    )
    get(BASE, auth)
    get(f"{BASE}?limit=101", auth)
    get(f"{BASE}/{id}", auth)
    get(f"{BASE}/not-a-uuid", auth)
    get(f"{BASE}/{uuid.uuid4()}", auth)
    get(f"{BASE}/{id}/events", auth)
    get(f"{BASE}/{id}/events?after=-1", auth)
    get(f"{BASE}/{uuid.uuid4()}/events", auth)
    post(f"{BASE}/{id}/cancel", "", auth)
    post(f"{BASE}/{uuid.uuid4()}/cancel", "", auth)

    jobs = RefreshJobService(scratch_db, store)
    for day in range(100):
        jobs.submit(
            f"fill-{day}", Region.NSW1, date(2023, 1, 1) + timedelta(days=day), "test"
        )
    post(
        BASE,
        {"region": "NSW1", "day": "2023-09-13"},
        {**auth, "Idempotency-Key": "full"},
    )

    with scratch_db.begin() as conn:
        conn.execute(sa.text("ALTER TABLE refresh_job RENAME TO missing_jobs"))
    try:
        get(BASE, auth)
    finally:
        with scratch_db.begin() as conn:
            conn.execute(sa.text("ALTER TABLE missing_jobs RENAME TO refresh_job"))

    with scratch_db.begin() as conn:
        conn.execute(sa.text("ALTER TABLE price_current RENAME TO missing_current"))
    try:
        get("/api/v1/prices/NSW1/coverage?start=2023-10-01&endExclusive=2023-10-02")
    finally:
        with scratch_db.begin() as conn:
            conn.execute(sa.text("ALTER TABLE missing_current RENAME TO price_current"))

    written = list(CAPTURES.glob("*.json"))
    statuses = sorted({json.loads(f.read_text())["status"] for f in written})
    assert statuses == [200, 202, 400, 401, 404, 409, 429, 503]
    assert len(written) >= 20
