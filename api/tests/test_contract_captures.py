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

    # -- operator grid imports ------------------------------------------------

    GRID = "/api/admin/v1/grid-imports"
    grid_window = {
        "region": "NSW1",
        "startDay": "2023-09-01",
        "endExclusive": "2023-09-03",
    }
    for route in (GRID, f"{GRID}/{uuid.uuid4()}", f"{GRID}/{uuid.uuid4()}/events"):
        get(route)
    post(GRID, grid_window)  # 401 without a token
    grid_submitted = post(GRID, grid_window, {**auth, "Idempotency-Key": "grid-1"})
    assert grid_submitted.status_code == 202
    grid_id = grid_submitted.json()["id"]
    post(GRID, grid_window, {**auth, "Idempotency-Key": "grid-1"})  # replay
    post(
        GRID,
        {**grid_window, "endExclusive": "2023-09-04"},
        {**auth, "Idempotency-Key": "grid-1"},
    )  # 409 IDEMPOTENCY_CONFLICT
    post(
        GRID,
        "{",
        {**auth, "Idempotency-Key": "grid-bad", "Content-Type": "application/json"},
    )
    get(GRID, auth)
    get(f"{GRID}/{grid_id}", auth)
    get(f"{GRID}/not-a-uuid", auth)
    get(f"{GRID}/{uuid.uuid4()}", auth)
    get(f"{GRID}/{grid_id}/events", auth)
    get(f"{GRID}/{uuid.uuid4()}/events", auth)
    post(f"{GRID}/{grid_id}/cancel", "", auth)
    post(f"{GRID}/{uuid.uuid4()}/cancel", "", auth)
    with scratch_db.begin() as conn:
        conn.execute(sa.text("ALTER TABLE grid_import_job RENAME TO missing_grid_job"))
    try:
        get(GRID, auth)
    finally:
        with scratch_db.begin() as conn:
            conn.execute(
                sa.text("ALTER TABLE missing_grid_job RENAME TO grid_import_job")
            )

    # -- operator grid publications --------------------------------------------

    PUBS = "/api/admin/v1/grid-publications"
    pub_window = {
        "region": "NSW1",
        "startDay": "2023-10-01",
        "endExclusive": "2023-10-02",
    }
    get(PUBS)  # 401
    post(PUBS, pub_window)  # 401
    published = post(PUBS, pub_window, auth)
    assert published.status_code == 201
    pub_id = published.json()["id"]
    post(
        PUBS,
        {"region": "NSW1", "startDay": "2023-10-02", "endExclusive": "2023-10-01"},
        auth,
    )  # 400 INVALID_REQUEST
    get(PUBS, auth)
    get(f"{PUBS}/{pub_id}", auth)
    get(f"{PUBS}/{uuid.uuid4()}", auth)  # 404 PUBLICATION_NOT_FOUND
    get(f"{PUBS}/not-a-uuid", auth)
    v2 = post(
        PUBS,
        {
            "region": "NSW1",
            "startDay": "2023-10-02",
            "endExclusive": "2023-10-03",
            "detectorSuite": "v2",
        },
        auth,
    )
    assert v2.status_code == 201
    post(
        PUBS,
        {**pub_window, "detectorSuite": "v9"},
        auth,
    )  # 400 INVALID_REQUEST

    # -- public GridReplay catalogue --------------------------------------------

    from nemlab_infrastructure.grid.batch import (
        GridBatch,
        Metric,
    )
    from nemlab_infrastructure.grid.batch import (
        Slot as GridSlot,
    )
    from nemlab_infrastructure.grid.events import GridCatalogue
    from nemlab_infrastructure.grid.source import GridFetch
    from nemlab_infrastructure.grid.store import GridStore

    # A day with one negative-price run and one spike, plus flat demand/flows.
    event_prices = [Decimal("50")] * 288
    event_prices[10] = event_prices[11] = event_prices[12] = Decimal("-7")
    event_prices[100] = Decimal("1500")
    store.save(
        Fetch(
            PriceBatch(
                Region.NSW1,
                DAY + timedelta(days=1),
                tuple(Slot(Kind.VALUE, v) for v in event_prices),
            ),
            RETRIEVED,
            response_hash("capture-grid-day"),
            "test-1",
        )
    )
    flat = tuple(GridSlot(Kind.VALUE, Decimal("12")) for _ in range(288))
    GridStore(scratch_db).save(
        GridFetch(
            (
                GridBatch(
                    Region.NSW1, Metric.DEMAND, "", DAY + timedelta(days=1), flat
                ),
                GridBatch(
                    Region.NSW1,
                    Metric.FLOW_IMPORTS,
                    "",
                    DAY + timedelta(days=1),
                    flat,
                ),
                GridBatch(
                    Region.NSW1,
                    Metric.FLOW_EXPORTS,
                    "",
                    DAY + timedelta(days=1),
                    flat,
                ),
            ),
            RETRIEVED,
            response_hash("capture-grid-market"),
            "test-1",
        )
    )
    catalogue = GridCatalogue(scratch_db)
    catalogue.publish(Region.NSW1, DAY + timedelta(days=1), DAY + timedelta(days=2))

    EV = "/api/v1/events"
    get(f"{EV}?region=VIC1")  # 404 CATALOGUE_NOT_PUBLISHED
    page = get(f"{EV}?region=NSW1")
    assert page.status_code == 200
    get(f"{EV}?region=NSW1&type=price_spike")
    get(f"{EV}?region=NSW1&from=2023-10-02&to=2023-10-02")
    get(f"{EV}?region=NSW1&limit=101")  # 400 INVALID_REQUEST
    get(f"{EV}?region=NSW1&from=2023-10-02")  # 400 INVALID_REQUEST
    get(f"{EV}?region=NSW1&cursor=bogus")  # 400 INVALID_REQUEST
    import base64

    stale = base64.urlsafe_b64encode(
        f"{uuid.uuid4()}:2023-10-02T14:55:00+00:00:{uuid.uuid4()}".encode()
    ).decode()
    get(f"{EV}?region=NSW1&cursor={stale}")  # 404 PUBLICATION_NOT_FOUND
    page2 = get(f"{EV}?region=NSW1&limit=1")
    if page2.json()["nextCursor"]:
        get(f"{EV}?region=NSW1&cursor={page2.json()['nextCursor']}")
    event_id = next(
        e["id"] for e in page.json()["events"] if e["type"] == "price_spike"
    )
    get(f"{EV}?region=NSW1&type=price_spike&sort=highest")
    get(f"{EV}?region=NSW1&sort=highest")  # 400 unsupported combination
    get(f"{EV}?region=NSW1&type=negative_price_run&minDurationMinutes=10")
    get(f"{EV}?region=NSW1&type=price_spike&valueGte=1000")
    get(f"{EV}/highlights?region=NSW1")
    get(f"{EV}/highlights?region=NSW1&type=negative_price_run")
    get(f"{EV}/highlights?region=QLD1")  # 404 CATALOGUE_NOT_PUBLISHED
    get(f"{EV}/{event_id}")
    get(f"{EV}/{uuid.uuid4()}")  # 404 EVENT_NOT_FOUND
    get(f"{EV}/not-a-uuid")  # 400 INVALID_REQUEST
    get(f"{EV}/{event_id}/preview")
    get(f"{EV}/{uuid.uuid4()}/preview")  # 404 EVENT_NOT_FOUND
    get(f"{EV}/{event_id}/replay")
    get(f"{EV}/{event_id}/replay?startDay=2023-10-02&endExclusive=2023-10-03")
    get(
        f"{EV}/{event_id}/replay?startDay=2023-10-01&endExclusive=2023-10-10"
    )  # 400 INVALID_REQUEST
    get(f"{EV}/{uuid.uuid4()}/replay")  # 404 EVENT_NOT_FOUND

    jobs = RefreshJobService(scratch_db, store)

    # A windowed submission fans out to one job per day; cancel them at once —
    # the visitor-exhaustion captures below claim the oldest queued job and
    # expect that flow's own jobs to be first in line.
    windowed = post(
        BASE,
        {"region": "NSW1", "startDay": "2023-09-01", "endExclusive": "2023-09-04"},
        {**auth, "Idempotency-Key": "capture-window"},
    )
    assert windowed.status_code == 202
    assert len(windowed.json()["jobs"]) == 3
    for windowed_job in windowed.json()["jobs"]:
        jobs.cancel(UUID(windowed_job["id"]), "test")

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
    from nemlab_infrastructure.jobs import (
        MAX_PENDING_JOBS,
    )
    from nemlab_infrastructure.jobs import (
        QueueFull as RefreshQueueFull,
    )

    # Fill on another region so the NSW1 probe day cannot dedup onto an
    # active job instead of exercising the cap.
    for day in range(MAX_PENDING_JOBS):
        try:
            jobs.submit(
                f"fill-{day}",
                Region.QLD1,
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
    assert statuses == [200, 201, 202, 400, 401, 404, 409, 413, 415, 429, 503]
    assert len(written) >= 45
