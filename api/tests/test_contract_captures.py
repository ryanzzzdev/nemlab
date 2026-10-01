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
from uuid import UUID

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

    # -- simulations ------------------------------------------------------------
    # The price-read seed above leaves the day incomplete (MISSING slots); a
    # later correction makes 2023-10-01 complete so submissions proceed.
    from nemlab_api.simulations import parse_request
    from nemlab_core import comparison
    from nemlab_infrastructure.simulations import SimulationJobs

    complete_slots = tuple(Slot(Kind.VALUE, Decimal(0)) for _ in range(288))
    store.save(
        Fetch(
            PriceBatch(Region.NSW1, DAY, complete_slots),
            RETRIEVED + timedelta(seconds=1),
            response_hash("complete"),
            "test-2",
        )
    )
    sims = SimulationJobs(scratch_db)
    SIM = "/api/v1/simulations"
    JSON = {"Content-Type": "application/json"}

    def sim_post(body_text: str, headers: dict | None = None) -> httpx.Response:
        return post(SIM, body_text, {**JSON, **(headers or {})})

    request_body = (
        '{"region":"NSW1","day":"2023-10-01",'
        '"site":{"capacityMWh":"1.00","minimumMWh":"0","maximumMWh":"1",'
        '"initialMWh":"0","chargeMW":"12","dischargeMW":"12",'
        '"importLimitMW":"12","exportLimitMW":"12"},'
        '"efficiency":{"roundTrip":"1"},'
        '"costs":{"importFee":"0","exportFee":"0","degradationPerExportedMWh":"0"},'
        '"windows":{"chargeStart":0,"chargeEnd":5,"dischargeStart":5,"dischargeEnd":10}}'
    )
    submitted = sim_post(request_body)
    assert submitted.status_code == 202
    sim_id = submitted.json()["id"]
    get(f"{SIM}/{sim_id}")
    get(f"{SIM}/{sim_id}/result")  # 409 RESULT_NOT_READY
    claim = sims.claim()
    assert claim is not None
    computed = sims.input(claim.id)
    sims.complete(
        claim.id,
        claim.token,
        comparison.run(
            computed.parameters(), computed.prices, computed.versions.limits
        ),
    )
    get(f"{SIM}/{sim_id}")  # 200 SUCCEEDED
    get(f"{SIM}/{sim_id}/result")  # 200 result payload
    sim_post(request_body)  # 200 deduplicated resubmission

    # Invalid JSON/fields, identifiers, size, content type.
    sim_post("{")
    sim_post(request_body.replace('"region":"NSW1"', '"region":"BOGUS"'))
    sim_post(" " * 16_385)
    sim_post(request_body, {"Content-Type": "text/plain"})
    get(f"{SIM}/not-a-uuid")
    missing = str(uuid.uuid4())
    get(f"{SIM}/{missing}")
    get(f"{SIM}/{missing}/result")

    # Failed jobs expose a classified code but no proven result.
    failed = sim_post(
        request_body.replace('"importFee":"0"', '"importFee":"7"')
    ).json()["id"]
    failed_claim = sims.claim()
    assert failed_claim is not None
    sims.fail(UUID(failed), failed_claim.token, "SIMULATION_DEADLINE_EXCEEDED", False)
    get(f"{SIM}/{failed}")
    get(f"{SIM}/{failed}/result")  # 409 SIMULATION_FAILED

    # Visitor-triggered refresh: pending, exhaustion, then the 10-job cap.
    unfetched = request_body.replace("2023-10-01", "2023-11-02")
    sim_post(unfetched)  # 409 PRICE_REFRESH_PENDING, creates the visitor job
    for _ in range(3):
        visitor = jobs.claim()
        assert visitor is not None
        jobs.fail_permanently(visitor.id, visitor.claim_token, "HTTP_401")
        # r2 and r3 retry submissions; the post after the third failure is
        # exhausted -> 409 PRICE_REFRESH_FAILED.
        sim_post(unfetched)
    # Ten distinct days fill the visitor pending cap; the eleventh is limited.
    for i in range(3, 13):
        sim_post(request_body.replace("2023-10-01", f"2023-11-{i:02d}"))
    sim_post(request_body.replace("2023-10-01", "2023-11-13"))  # 429

    # Shared queue saturation still returns 429 while a duplicate succeeds.
    for i in range(20, 120):
        sims.submit(
            parse_request(
                request_body.replace('"importFee":"0"', f'"importFee":"{i}"').encode()
            )
        )
    sim_post(request_body.replace('"importFee":"0"', '"importFee":"119"'))  # 429
    sim_post(request_body)  # 200 dedup onto the succeeded job

    with scratch_db.begin() as conn:
        conn.execute(
            sa.text("ALTER TABLE simulation_job RENAME TO missing_simulation_job")
        )
        conn.execute(
            sa.text("ALTER TABLE price_current RENAME TO missing_price_current")
        )
    try:
        sim_post(request_body)
        get(f"{SIM}/{sim_id}")
        get(f"{SIM}/{sim_id}/result")
    finally:
        with scratch_db.begin() as conn:
            conn.execute(
                sa.text("ALTER TABLE missing_simulation_job RENAME TO simulation_job")
            )
            conn.execute(
                sa.text("ALTER TABLE missing_price_current RENAME TO price_current")
            )

    # Refresh-queue saturation last: any earlier fill would starve the visitor
    # submissions above, and ``claim`` picks the oldest pending job.
    from nemlab_infrastructure.jobs import QueueFull as RefreshQueueFull

    for day in range(100):
        try:
            jobs.submit(
                f"fill-{day}",
                Region.NSW1,
                date(2023, 1, 1) + timedelta(days=day),
                "test",
            )
        except RefreshQueueFull:
            break
    post(
        BASE,
        {"region": "NSW1", "day": "2023-09-13"},
        {**auth, "Idempotency-Key": "full"},
    )

    written = list(CAPTURES.glob("*.json"))
    statuses = sorted({json.loads(f.read_text())["status"] for f in written})
    assert statuses == [200, 202, 400, 401, 404, 409, 413, 415, 429, 503]
    assert len(written) >= 45
