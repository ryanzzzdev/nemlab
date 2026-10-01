"""``SimulationHttpTest`` port — public simulation submission, status, result
and visitor-triggered refresh over real PostgreSQL via ``TestClient``."""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import httpx
import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from nemlab_api.simulations import parse_request
from nemlab_core import comparison
from nemlab_core.comparison import SimulationComparison
from nemlab_core.hindsight import Outcome, Status
from nemlab_core.prices import Region
from nemlab_infrastructure.jobs import RefreshJobService
from nemlab_infrastructure.prices.batch import Kind, PriceBatch, Slot
from nemlab_infrastructure.prices.batch import hash as response_hash
from nemlab_infrastructure.prices.source import Fetch
from nemlab_infrastructure.prices.store import PriceStore
from nemlab_infrastructure.simulations import SimulationJobs

PATH = "/api/v1/simulations"
DAY = date(2023, 10, 1)
AT = datetime(2026, 9, 20, tzinfo=UTC)
TOKEN = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG"


def body() -> str:
    return (
        '{"region":"NSW1","day":"2023-10-01",'
        '"site":{"capacityMWh":"1.00","minimumMWh":"0","maximumMWh":"1",'
        '"initialMWh":"0","chargeMW":"12","dischargeMW":"12",'
        '"importLimitMW":"12","exportLimitMW":"12"},'
        '"efficiency":{"roundTrip":"1"},'
        '"costs":{"importFee":"0","exportFee":"0","degradationPerExportedMWh":"0"},'
        '"windows":{"chargeStart":0,"chargeEnd":5,"dischargeStart":5,"dischargeEnd":10}}'
    )


@pytest.fixture
def sim_settings(scratch_db: sa.Engine, clean: None):
    from nemlab_api.settings import ApiSettings
    from nemlab_infrastructure.settings import DatabaseSettings

    base = DatabaseSettings()
    url = (
        f"jdbc:postgresql://{scratch_db.url.host}:{scratch_db.url.port}"
        f"/{scratch_db.url.database}"
    )
    return ApiSettings(
        db_url=url,
        db_user=base.db_user,
        db_password=base.db_password,
        simulation_api_enabled=True,
    )


@pytest.fixture
def sim_client(sim_settings) -> Any:
    from nemlab_api.app import create_app

    with TestClient(create_app(sim_settings)) as test_client:
        yield test_client


@pytest.fixture
def store(scratch_db: sa.Engine) -> PriceStore:
    return PriceStore(scratch_db)


@pytest.fixture
def sims(scratch_db: sa.Engine) -> SimulationJobs:
    return SimulationJobs(scratch_db)


@pytest.fixture
def refreshes(scratch_db: sa.Engine, store: PriceStore) -> RefreshJobService:
    return RefreshJobService(scratch_db, store)


def save(
    store: PriceStore, first: str, gap: Kind | None = None, at: datetime = AT
) -> None:
    slots = [Slot(Kind.VALUE, Decimal(0))] * 288
    slots[0] = Slot(Kind.VALUE, Decimal(first))
    slots[1] = Slot(Kind.VALUE, Decimal(200))
    if gap is not None:
        slots[3] = Slot(gap, None)
    store.save(
        Fetch(
            PriceBatch(Region.NSW1, DAY, tuple(slots)),
            at,
            response_hash(first),
            "test",
        )
    )


def fetch(day: date) -> Fetch:
    slots = tuple(Slot(Kind.VALUE, Decimal(1)) for _ in range(288))
    return Fetch(
        PriceBatch(Region.NSW1, day, slots), AT, response_hash("visitor-fetch"), "test"
    )


def complete(sims: SimulationJobs, claim) -> None:
    input = sims.input(claim.id)
    sims.complete(
        claim.id,
        claim.token,
        comparison.run(input.parameters(), input.prices, input.versions.limits),
    )


def post(
    client: TestClient,
    body_text: str | None = None,
    content_type: str = "application/json",
) -> httpx.Response:
    return client.post(PATH, content=body_text, headers={"Content-Type": content_type})


def test_submit_poll_complete_and_reopen_preserves_inputs(
    sim_client: TestClient,
    sims: SimulationJobs,
    store: PriceStore,
    scratch_db: sa.Engine,
) -> None:
    save(store, "-30.000000000000000001")
    submitted = post(sim_client, body())
    assert submitted.status_code == 202
    id = submitted.json()["id"]
    assert submitted.headers["Location"] == f"{PATH}/{id}"
    assert submitted.headers["Retry-After"] == "2"
    assert sim_client.get(f"{PATH}/{id}").json()["status"] == "QUEUED"
    pending = sim_client.get(f"{PATH}/{id}/result")
    assert pending.json()["code"] == "RESULT_NOT_READY"
    claim = sims.claim()
    assert claim is not None
    running = sim_client.get(f"{PATH}/{id}")
    assert running.json()["status"] == "RUNNING"
    assert str(claim.token) not in running.text
    complete(sims, claim)
    result = sim_client.get(f"{PATH}/{id}/result")
    assert result.status_code == 200
    data = result.json()
    assert data["fixed"]["accounting"]["margin"] == pytest.approx(230)
    assert len(data["hindsight"]["dispatch"]["intervals"]) == 288
    assert data["solver"]["status"] == "OPTIMAL"
    assert data["prices"][0]["price"] == "-30.000000000000000001"
    assert data["inputs"]["site"]["capacityMWh"] == "1"
    assert data["inputs"]["efficiency"]["charge"] == "1"
    assert "roundTrip" not in data["inputs"]["efficiency"]
    assert data["prices"][0]["start"] == "2023-09-30T14:00:00Z"
    assert data["prices"][287]["end"] == "2023-10-01T14:00:00Z"
    for private in (
        "claim_token",
        "claimToken",
        "leaseUntil",
        "diagnostic",
        "solverState",
        "certificateState",
    ):
        assert private not in result.text, private
    duplicate = post(sim_client, body().replace('"1.00"', '"1.0"'))
    assert duplicate.status_code == 200
    assert duplicate.json()["id"] == id
    save(store, "-50", at=AT + timedelta(seconds=1))
    assert sim_client.get(f"{PATH}/{id}/result").json() == data
    assert post(sim_client, body()).json()["id"] != id
    with scratch_db.connect() as conn:
        assert (
            conn.execute(sa.text("SELECT count(*) FROM refresh_job")).scalar_one() == 0
        )


def test_threshold_requests_round_trip_through_stored_result(
    sim_client: TestClient, sims: SimulationJobs, store: PriceStore
) -> None:
    save(store, "-30")
    with_thresholds = body().replace(
        '"windows":{"chargeStart":0,"chargeEnd":5,"dischargeStart":5,"dischargeEnd":10}',
        '"windows":{"chargeStart":0,"chargeEnd":5,"dischargeStart":5,"dischargeEnd":10},'
        '"thresholds":{"chargeBelow":"-10.0","dischargeAbove":"150"}',
    )
    submitted = post(sim_client, with_thresholds)
    assert submitted.status_code == 202
    id = submitted.json()["id"]
    complete(sims, sims.claim())
    data = sim_client.get(f"{PATH}/{id}/result").json()
    threshold = data["threshold"]
    assert threshold["version"] == "price-threshold-v1"
    assert threshold["thresholds"]["chargeBelow"] == "-10"
    assert len(threshold["dispatch"]["intervals"]) == 288
    assert "margin" in threshold["accounting"]
    assert data["inputs"]["thresholds"]["chargeBelow"] == "-10"
    # The plain scenario is a different scenario; its result has no experiment.
    plain = post(sim_client, body())
    plain_id = plain.json()["id"]
    assert plain_id != id
    complete(sims, sims.claim())
    plain_data = sim_client.get(f"{PATH}/{plain_id}/result").json()
    assert plain_data["threshold"] is None
    assert "thresholds" not in plain_data["inputs"]


def test_duplicate_pending_requests_reuse_job_and_normalised_legs(
    sim_client: TestClient, store: PriceStore, scratch_db: sa.Engine
) -> None:
    save(store, "-30")
    first = post(sim_client, body())
    second = post(
        sim_client,
        body().replace('"roundTrip":"1"', '"charge":"1.00","discharge":"1"'),
    )
    assert second.status_code == 202
    assert first.json()["id"] == second.json()["id"]
    with scratch_db.connect() as conn:
        assert (
            conn.execute(sa.text("SELECT count(*) FROM simulation_job")).scalar_one()
            == 1
        )


def test_strict_json_and_domain_errors_reject_before_creating_jobs(
    sim_client: TestClient, store: PriceStore, scratch_db: sa.Engine
) -> None:
    save(store, "-30")
    variants = [
        "null",
        "[]",
        "{}",
        "{",
        body() + " {}",
        body().replace('"capacityMWh":"1.00"', '"capacityMWh":1'),
        body().replace('"region":"NSW1"', '"region":"NSW1","region":"QLD1"'),
        body().replace('"minimumMWh":"0"', '"unknown":0,"minimumMWh":"0"'),
        body().replace('"region":"NSW1"', '"region":"BOGUS"'),
        body().replace("2023-10-01", "2200-01-01"),
        body().replace("2023-10-01", "2023-02-30"),
        body().replace('"roundTrip":"1"', '"roundTrip":"1","charge":"1"'),
        body().replace('"capacityMWh":"1.00"', '"capacityMWh":"NaN"'),
        body().replace('"chargeMW":"12"', '"chargeMW":"-1"'),
        body().replace('"chargeEnd":5', '"chargeEnd":6'),
        body().replace('"chargeEnd":5', '"chargeEnd":5.0'),
        body().replace('"importFee":"0"', '"importFee":"1e100000"'),
        body().replace(
            '"dischargeEnd":10}}',
            '"dischargeEnd":10},"thresholds":{"chargeBelow":"30"}}',
        ),
        body().replace(
            '"dischargeEnd":10}}',
            '"dischargeEnd":10},"thresholds":{"chargeBelow":"150","dischargeAbove":"30"}}',
        ),
        body().replace(
            '"dischargeEnd":10}}',
            '"dischargeEnd":10},"thresholds":{"chargeBelow":30,"dischargeAbove":"150"}}',
        ),
        body().replace(
            '"dischargeEnd":10}}',
            '"dischargeEnd":10},"thresholds":{"chargeBelow":"30","dischargeAbove":"150","extra":"1"}}',
        ),
    ]
    for value in variants:
        response = post(sim_client, value)
        assert response.status_code == 400, value
        assert response.json()["code"] == "INVALID_REQUEST"
        assert "field" in response.json()
    with scratch_db.connect() as conn:
        assert (
            conn.execute(sa.text("SELECT count(*) FROM simulation_input")).scalar_one()
            == 0
        )
    assert sim_client.get(f"{PATH}/not-uuid").status_code == 400
    assert sim_client.get(f"{PATH}/1-1-1-1-1/result").status_code == 400


def test_eligible_days_without_prices_enqueue_one_visitor_refresh(
    sim_client: TestClient, refreshes: RefreshJobService, scratch_db: sa.Engine
) -> None:
    pending = post(sim_client, body())
    assert pending.status_code == 409
    assert pending.json()["code"] == "PRICE_REFRESH_PENDING"
    assert pending.headers["Retry-After"] == "30"
    with scratch_db.connect() as conn:
        assert (
            conn.execute(sa.text("SELECT count(*) FROM refresh_job")).scalar_one() == 1
        )
        key = conn.execute(
            sa.text("SELECT request_key FROM refresh_request")
        ).scalar_one()
    assert key == "visitor-price-v1:NSW1:2023-10-01"
    # Repeated submissions deduplicate onto the same active job.
    assert post(sim_client, body()).json()["code"] == "PRICE_REFRESH_PENDING"
    with scratch_db.connect() as conn:
        assert (
            conn.execute(sa.text("SELECT count(*) FROM refresh_job")).scalar_one() == 1
        )
        assert (
            conn.execute(sa.text("SELECT count(*) FROM simulation_job")).scalar_one()
            == 0
        )
    # Once the fetch commits a complete revision the submission proceeds.
    claim = refreshes.claim()
    assert claim is not None
    refreshes.complete(claim.id, claim.claim_token, fetch(DAY))
    assert post(sim_client, body()).status_code == 202
    with scratch_db.connect() as conn:
        assert (
            conn.execute(sa.text("SELECT count(*) FROM simulation_job")).scalar_one()
            == 1
        )


def test_incomplete_days_trigger_refresh_but_ineligible_days_never_do(
    sim_client: TestClient, store: PriceStore, scratch_db: sa.Engine
) -> None:
    save(store, "-30", gap=Kind.MISSING)
    pending = post(sim_client, body())
    assert pending.status_code == 409
    assert pending.json()["code"] == "PRICE_REFRESH_PENDING"
    for bad in ("2020-01-01", "2200-01-01"):
        response = post(sim_client, body().replace("2023-10-01", bad))
        assert response.status_code == 400
        assert response.json()["code"] == "INVALID_REQUEST"
    with scratch_db.connect() as conn:
        assert (
            conn.execute(sa.text("SELECT count(*) FROM refresh_job")).scalar_one() == 1
        )


def test_visitor_refreshes_retry_after_failure_then_report_exhaustion(
    sim_client: TestClient, refreshes: RefreshJobService, scratch_db: sa.Engine
) -> None:
    for attempt in (1, 2, 3):
        assert post(sim_client, body()).json()["code"] == "PRICE_REFRESH_PENDING"
        claim = refreshes.claim()
        assert claim is not None
        refreshes.fail_permanently(claim.id, claim.claim_token, "HTTP_401")
        with scratch_db.connect() as conn:
            count = conn.execute(
                sa.text("SELECT count(*) FROM refresh_job")
            ).scalar_one()
        assert count == attempt
    exhausted = post(sim_client, body())
    assert exhausted.status_code == 409
    assert exhausted.json()["code"] == "PRICE_REFRESH_FAILED"
    with scratch_db.connect() as conn:
        assert (
            conn.execute(sa.text("SELECT count(*) FROM refresh_job")).scalar_one() == 3
        )
        assert (
            conn.execute(sa.text("SELECT count(*) FROM simulation_job")).scalar_one()
            == 0
        )


def test_visitor_fetches_cannot_saturate_the_shared_queue(
    sim_client: TestClient, scratch_db: sa.Engine
) -> None:
    for i in range(1, 11):
        response = post(sim_client, body().replace("2023-10-01", f"2023-10-{i:02d}"))
        assert response.json()["code"] == "PRICE_REFRESH_PENDING", i
    limited = post(sim_client, body().replace("2023-10-01", "2023-10-15"))
    assert limited.status_code == 429
    assert limited.json()["code"] == "VISITOR_REFRESH_LIMIT"
    assert limited.headers["Retry-After"] == "60"
    with scratch_db.connect() as conn:
        assert (
            conn.execute(sa.text("SELECT count(*) FROM refresh_job")).scalar_one() == 10
        )


def test_failed_and_unproven_jobs_never_expose_a_proven_result(
    sim_client: TestClient, sims: SimulationJobs, store: PriceStore
) -> None:
    save(store, "-30")
    id = post(sim_client, body()).json()["id"]
    claim = sims.claim()
    assert claim is not None
    sims.fail(UUID(id), claim.token, "SIMULATION_DEADLINE_EXCEEDED", False)
    status = sim_client.get(f"{PATH}/{id}")
    assert status.json()["failureCode"] == "SIMULATION_DEADLINE_EXCEEDED"
    assert sim_client.get(f"{PATH}/{id}/result").json()["code"] == "SIMULATION_FAILED"
    assert post(sim_client, body()).status_code == 200
    assert sims.find(UUID(id)).attempts == 1  # type: ignore[union-attr]
    other = post(sim_client, body().replace('"importFee":"0"', '"importFee":"1"'))
    other_id = UUID(other.json()["id"])
    second = sims.claim()
    assert second is not None
    input = sims.input(other_id)
    result = comparison.run(input.parameters(), input.prices, input.versions.limits)
    h = result.hindsight
    incomplete = Outcome(
        Status.FEASIBLE_NOT_PROVEN,
        "FEASIBLE",
        "NOT_RUN",
        h.dispatch,
        h.accounting,
        h.solver_objective,
        None,
        None,
        h.elapsed_nanos,
        h.limits,
        "internal diagnostic must stay private",
    )
    sims.complete(
        other_id,
        second.token,
        SimulationComparison(
            result.fixed_dispatch, result.fixed_accounting, incomplete, None
        ),
    )
    status = sim_client.get(f"{PATH}/{other_id}")
    assert status.json()["failureCode"] == "SOLVER_FEASIBLE_NOT_PROVEN"
    assert "internal diagnostic" not in status.text
    assert sim_client.get(f"{PATH}/{other_id}/result").status_code == 409


def test_unknown_ids_body_limit_and_content_type_have_explicit_responses(
    sim_client: TestClient,
) -> None:
    id = str(uuid.uuid4())
    assert sim_client.get(f"{PATH}/{id}").status_code == 404
    assert sim_client.get(f"{PATH}/{id}/result").status_code == 404
    assert post(sim_client, " " * 16_385).status_code == 413
    assert post(sim_client, body(), "text/plain").status_code == 415
    assert sim_client.post("/api/admin/v1/price-refreshes", json={}).status_code == 404


def test_queue_saturation_returns_retry_after_while_duplicates_still_work(
    sim_client: TestClient,
    sims: SimulationJobs,
    store: PriceStore,
    scratch_db: sa.Engine,
) -> None:
    save(store, "-30")
    for i in range(100):
        sims.submit(
            parse_request(
                body().replace('"importFee":"0"', f'"importFee":"{i}"').encode()
            )
        )
    full = post(sim_client, body().replace('"importFee":"0"', '"importFee":"100"'))
    assert full.status_code == 429
    assert full.headers["Retry-After"] == "5"
    assert post(sim_client, body()).status_code == 202


def test_database_failures_are_safe_across_all_operations(
    sim_client: TestClient, scratch_db: sa.Engine
) -> None:
    id = str(uuid.uuid4())
    with scratch_db.begin() as conn:
        conn.execute(
            sa.text("ALTER TABLE simulation_job RENAME TO missing_simulation_job")
        )
        conn.execute(
            sa.text("ALTER TABLE price_current RENAME TO missing_price_current")
        )
    try:
        for response in (
            post(sim_client, body()),
            sim_client.get(f"{PATH}/{id}"),
            sim_client.get(f"{PATH}/{id}/result"),
        ):
            assert response.status_code == 503
            assert response.json()["code"] == "STORAGE_UNAVAILABLE"
            assert "jdbc:" not in response.text
    finally:
        with scratch_db.begin() as conn:
            conn.execute(
                sa.text("ALTER TABLE missing_simulation_job RENAME TO simulation_job")
            )
            conn.execute(
                sa.text("ALTER TABLE missing_price_current RENAME TO price_current")
            )
