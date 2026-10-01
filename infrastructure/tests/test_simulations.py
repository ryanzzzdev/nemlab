"""Ported ``SimulationJobsTest`` + ``ScenarioPreparationTest`` — fenced
simulation queue, immutable inputs/results, JSON round-trip on real
PostgreSQL."""

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
import sqlalchemy as sa
from db_fixture import apply_schema
from sqlalchemy import text

from nemlab_core import comparison, hindsight
from nemlab_core.accounting import Accounting
from nemlab_core.prices import Region
from nemlab_core.request import (
    Costs,
    EfficiencyInput,
    Invalid,
    SimulationRequest,
    Site,
    ThresholdInput,
    Windows,
)
from nemlab_infrastructure import simulations
from nemlab_infrastructure.prices.batch import Kind, PriceBatch, Slot
from nemlab_infrastructure.prices.batch import hash as response_hash
from nemlab_infrastructure.prices.source import Fetch, parse
from nemlab_infrastructure.prices.store import PriceStore
from nemlab_infrastructure.simulations import (
    QueueFull,
    SimulationJobs,
    StaleClaim,
    UnsupportedVersion,
    Versions,
)

DAY = date(2023, 9, 11)
AT = datetime(2026, 9, 20, tzinfo=UTC)
BODY = (
    Path(__file__).resolve().parents[2]
    / "docs/project/evidence/oe-validation/historical-price-response.json"
).read_text()


def n(value: str) -> Decimal:
    return Decimal(value)


def request(fee: int = 0) -> SimulationRequest:
    """``SimulationJobsTest.request`` — cheap dispatch against the seed day."""
    zero, one, power = Decimal(0), Decimal(1), Decimal(12)
    return SimulationRequest(
        Region.NSW1,
        DAY,
        Site(one, zero, one, zero, power, power, power, power),
        EfficiencyInput(one, one, None),
        Costs(Decimal(fee), zero, zero),
        Windows(0, 5, 5, 10),
    )


def scenario_request() -> SimulationRequest:
    """``ScenarioPreparationTest.request`` — exercises the real OE fixture day."""
    return SimulationRequest(
        Region.NSW1,
        DAY,
        Site(n("2"), n("0"), n("2"), n("0"), n("1"), n("1"), n("1"), n("1")),
        EfficiencyInput(None, None, n(".9")),
        Costs(n("2"), n("2"), n("10")),
        Windows(600, 840, 1020, 1260),
    )


def fetch(first: str, at: datetime) -> Fetch:
    slots = [Slot(Kind.VALUE, Decimal(0))] * 288
    slots[0] = Slot(Kind.VALUE, Decimal(first))
    slots[1] = Slot(Kind.VALUE, Decimal(200))
    return Fetch(
        PriceBatch(Region.NSW1, DAY, tuple(slots)),
        at,
        response_hash(first),
        "fixture",
    )


@pytest.fixture
def store(scratch_db: sa.Engine) -> PriceStore:
    apply_schema(scratch_db)
    with scratch_db.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE simulation_result, simulation_job, simulation_input,"
                " refresh_job_event, refresh_request, refresh_job,"
                " price_snapshot, price_current, price_import_attempt,"
                " price_revision, price_backfill"
            )
        )
    prices = PriceStore(scratch_db)
    prices.save(fetch("-30", AT))
    return prices


@pytest.fixture
def jobs(store: PriceStore) -> SimulationJobs:
    return SimulationJobs(store.engine)


def _count(engine: sa.Engine, table: str) -> int:
    tables = {
        "simulation_input": "SELECT count(*) FROM simulation_input",
        "simulation_job": "SELECT count(*) FROM simulation_job",
        "simulation_result": "SELECT count(*) FROM simulation_result",
        "price_revision": "SELECT count(*) FROM price_revision",
        "price_snapshot": "SELECT count(*) FROM price_snapshot",
        "refresh_job": "SELECT count(*) FROM refresh_job",
        "price_import_attempt": "SELECT count(*) FROM price_import_attempt",
        "price_backfill": "SELECT count(*) FROM price_backfill",
    }
    with engine.connect() as conn:
        return conn.execute(text(tables[table])).scalar_one()


def _ready(engine: sa.Engine, id: UUID) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE simulation_job SET available_at = clock_timestamp()"
                " - interval '1 second' WHERE id = :id"
            ),
            {"id": id},
        )


def compute(jobs: SimulationJobs, id: UUID) -> comparison.SimulationComparison:
    input = jobs.input(id)
    return comparison.run(input.parameters(), input.prices, input.versions.limits)


# -- ScenarioPreparation --------------------------------------------------------


def test_captured_fixture_runs_through_the_engine(store: PriceStore) -> None:
    fixture = parse(Region.NSW1, DAY, BODY, AT)
    # Replace the synthetic seed with the real OE fixture day.
    with store.engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE simulation_result, simulation_job, simulation_input,"
                " refresh_job_event, refresh_request, refresh_job,"
                " price_snapshot, price_current, price_import_attempt,"
                " price_revision, price_backfill"
            )
        )
    revision = store.save(fixture)
    p = simulations.prepare(store, scenario_request(), DAY + timedelta(days=1))
    assert p.price_revision == revision
    assert p.prices == fixture.batch.to_price_day()
    assert len(p.key) == 64
    hindsight_result = hindsight.solve(
        p.parameters.battery,
        p.parameters.windows,
        p.parameters.costs,
        p.prices,
        p.versions.limits,
    )
    assert hindsight_result.status is hindsight.Status.OPTIMAL


def test_equivalent_requests_and_repeated_imports_have_same_key(
    store: PriceStore,
) -> None:
    p = simulations.prepare(store, scenario_request())
    s = scenario_request().site
    assert s is not None
    equivalent = SimulationRequest(
        Region.NSW1,
        DAY,
        Site(
            n("2.000"),
            s.minimum_mwh,
            s.maximum_mwh,
            n("-0.00"),
            s.charge_mw,
            s.discharge_mw,
            s.import_limit_mw,
            s.export_limit_mw,
        ),
        p.parameters.values.efficiency,
        scenario_request().costs,
        scenario_request().windows,
    )
    again = simulations.prepare(store, equivalent)
    assert p.key == again.key


def test_corrections_change_new_keys_but_never_captured_inputs(
    store: PriceStore,
) -> None:
    before = simulations.prepare(store, scenario_request())
    base = store.revision(before.price_revision)
    slots = list(base.slots)
    slots[0] = Slot(Kind.VALUE, n("123.4567890123456789"))
    store.save(
        Fetch(
            PriceBatch(Region.NSW1, DAY, tuple(slots)),
            AT + timedelta(seconds=1),
            response_hash("test"),
            "test",
        )
    )
    after = simulations.prepare(store, scenario_request())
    assert before.key != after.key
    assert before.price_revision != after.price_revision
    assert store.revision(before.price_revision).to_price_day() == before.prices
    assert after.prices.intervals[0].price == n("123.4567890123456789")


def test_unavailable_and_incomplete_days_never_create_work(
    store: PriceStore,
) -> None:
    with pytest.raises(Invalid) as missing:
        simulations.prepare(store, scenario_for(date(2023, 9, 20)))
    assert missing.value.code == "PRICE_DAY_UNAVAILABLE"
    for kind in (Kind.MISSING, Kind.SOURCE_NULL):
        coverage = store.coverage(Region.NSW1, DAY)
        assert coverage is not None
        base = store.revision(coverage.revision)
        slots = list(base.slots)
        slots[0] = Slot(kind, None)
        store.save(
            Fetch(
                PriceBatch(Region.NSW1, DAY, tuple(slots)),
                AT + timedelta(seconds=60),
                response_hash(f"test-{kind.name}"),
                "test",
            )
        )
        with pytest.raises(Invalid) as error:
            simulations.prepare(store, scenario_request())
        assert error.value.code == "PRICE_DAY_INCOMPLETE"
    assert _count(store.engine, "price_snapshot") == 0
    assert _count(store.engine, "refresh_job") == 0
    assert _count(store.engine, "price_backfill") == 0


def scenario_for(day: date) -> SimulationRequest:
    r = scenario_request()
    return SimulationRequest(r.region, day, r.site, r.efficiency, r.costs, r.windows)


def test_invalid_parameters_rejected_before_database_access(
    scratch_db: sa.Engine,
) -> None:
    dead = PriceStore(sa.create_engine("postgresql+psycopg://127.0.0.1:1/unused"))
    with pytest.raises(Invalid) as required:
        simulations.prepare(dead, None)
    assert required.value.code == "REQUIRED"
    r = scenario_request()
    with pytest.raises(Invalid) as field:
        simulations.prepare(
            dead,
            SimulationRequest(r.region, r.day, None, r.efficiency, r.costs, r.windows),
        )
    assert field.value.field == "site"


def test_each_result_affecting_parameter_participates_in_identity(
    store: PriceStore,
) -> None:
    baseline = simulations.prepare(store, scenario_request()).key
    r = scenario_request()
    assert r.site is not None and r.efficiency is not None
    assert r.costs is not None and r.windows is not None
    variants: list[SimulationRequest] = []
    for field in range(8):
        values = [n(v) for v in ("2", "0", "2", "0", "1", "1", "1", "1")]
        values[field] = n("3" if field == 0 else "1.5" if field == 2 else ".5")
        if field == 1:
            values[3] = n(".5")
        variants.append(
            SimulationRequest(
                r.region, r.day, Site(*values), r.efficiency, r.costs, r.windows
            )
        )
    for field in range(3):
        values = [n("2"), n("2"), n("10")]
        values[field] = n("3")
        variants.append(
            SimulationRequest(
                r.region, r.day, r.site, r.efficiency, Costs(*values), r.windows
            )
        )
    leg = r.normalise().values.efficiency.charge
    for e in (
        EfficiencyInput(n(".8"), leg, None),
        EfficiencyInput(leg, n(".8"), None),
    ):
        variants.append(
            SimulationRequest(r.region, r.day, r.site, e, r.costs, r.windows)
        )
    for field in range(4):
        minutes = [600, 840, 1020, 1260]
        minutes[field] += 5
        variants.append(
            SimulationRequest(
                r.region, r.day, r.site, r.efficiency, r.costs, Windows(*minutes)
            )
        )
    keys = {simulations.prepare(store, v).key for v in variants}
    assert baseline not in keys
    assert len(keys) == len(variants)
    canonical = Versions.current().canonical()
    for part in (
        "battery-v1",
        "HiGHS",
        "ordered-windows-v1",
        "ordered-hindsight-v1",
    ):
        assert part in canonical


# -- SimulationJobs -------------------------------------------------------------


def test_submissions_deduplicate_globally_and_claims_single_winner(
    jobs: SimulationJobs, scratch_db: sa.Engine
) -> None:
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(4) as pool:
        ids = list(
            pool.map(lambda _i: SimulationJobs(scratch_db).submit(request()), range(4))
        )
    assert len(set(ids)) == 1
    jobs.submit(request(1))
    with ThreadPoolExecutor(4) as pool:
        claims = list(pool.map(lambda _i: SimulationJobs(scratch_db).claim(), range(4)))
    assert sum(1 for c in claims if c is not None) == 1
    assert _count(scratch_db, "simulation_input") == 2
    assert _count(scratch_db, "simulation_job") == 2


def test_result_and_inputs_preserved_across_corrections(
    jobs: SimulationJobs, store: PriceStore, scratch_db: sa.Engine
) -> None:
    id = jobs.submit(request())
    claim = jobs.claim()
    assert claim is not None
    input = jobs.input(id)
    result = compute(jobs, id)
    assert result.fixed_accounting.margin == pytest.approx(230)
    assert result.hindsight.accounting is not None
    assert result.hindsight.accounting.margin == pytest.approx(230)
    jobs.complete(id, claim.token, result)  # type: ignore[arg-type]
    assert jobs.find(id).status == "SUCCEEDED"  # type: ignore[union-attr]
    assert jobs.result(id) == result
    assert jobs.submit(request()) == id
    store.save(fetch("-50", datetime.now(UTC) + timedelta(seconds=10)))
    assert jobs.submit(request()) != id
    assert jobs.input(id) == input
    assert SimulationJobs(scratch_db).result(id) == result
    for sql in (
        "UPDATE simulation_input SET request='{}'::jsonb WHERE id = :id",
        "DELETE FROM simulation_input WHERE id = :id",
        "UPDATE simulation_result SET result='{}'::jsonb WHERE id = :id",
        "DELETE FROM simulation_result WHERE id = :id",
    ):
        with pytest.raises(sa.exc.DatabaseError), scratch_db.begin() as conn:
            conn.execute(text(sql), {"id": id})
            conn.rollback()


def test_threshold_experiments_get_distinct_jobs_and_round_trip(
    jobs: SimulationJobs, store: PriceStore
) -> None:
    r = request()
    thresholded = SimulationRequest(
        r.region,
        r.day,
        r.site,
        r.efficiency,
        r.costs,
        r.windows,
        ThresholdInput(n("0"), n("100")),
    )
    plain, with_thresholds = jobs.submit(r), jobs.submit(thresholded)
    assert plain != with_thresholds
    assert jobs.submit(thresholded) == with_thresholds
    assert jobs.input(plain).request.thresholds is None
    assert jobs.input(with_thresholds).request.thresholds is not None
    threshold_result = None
    for _ in range(2):
        claim = jobs.claim()
        assert claim is not None
        result = compute(jobs, claim.id)
        if claim.id == with_thresholds:
            threshold_result = result
            assert result.threshold is not None
            assert result.threshold.version == "price-threshold-v1"
            first = result.threshold.dispatch.intervals[0]
            second = result.threshold.dispatch.intervals[1]
            assert first.imported_mwh > 0
            assert second.exported_mwh > 0
        else:
            assert result.threshold is None
        jobs.complete(claim.id, claim.token, result)  # type: ignore[arg-type]
    assert threshold_result is not None
    stored = jobs.result(with_thresholds)
    assert stored is not None
    assert stored.fixed_dispatch == threshold_result.fixed_dispatch
    assert stored.hindsight == threshold_result.hindsight
    # jsonb normalises decimal literals (1E+2 -> 100): values round-trip.
    assert stored.threshold is not None
    assert stored.threshold.thresholds.charge_below == n("0")
    assert stored.threshold.thresholds.discharge_above == n("100")
    assert stored.threshold.dispatch == threshold_result.threshold.dispatch
    assert stored.threshold.accounting == threshold_result.threshold.accounting
    # Legacy rows without the experiment still read back.
    doc = json.loads(simulations._encode(simulations._result_json(threshold_result)))
    del doc["threshold"]
    legacy = simulations._read_result(doc)
    assert legacy.threshold is None
    assert legacy.fixed_dispatch == threshold_result.fixed_dispatch


def test_expired_claims_recover_with_new_tokens_and_stop_after_three(
    jobs: SimulationJobs, scratch_db: sa.Engine
) -> None:
    id = jobs.submit(request())
    abandoned = jobs.claim()
    assert abandoned is not None and abandoned.token is not None
    for attempt in range(1, 4):
        with scratch_db.begin() as conn:
            conn.execute(
                text(
                    "UPDATE simulation_job SET lease_until = clock_timestamp()"
                    " - interval '1 second' WHERE id = :id"
                ),
                {"id": id},
            )
        fresh = SimulationJobs(scratch_db)
        assert fresh.claim() is None
        with pytest.raises(StaleClaim):
            fresh.complete(id, abandoned.token, compute(fresh, id))  # type: ignore[arg-type]
        with pytest.raises(StaleClaim):
            fresh.fail(id, abandoned.token, "LATE", True)  # type: ignore[arg-type]
        if attempt < 3:
            assert fresh.find(id).status == "QUEUED"  # type: ignore[union-attr]
            assert fresh.claim() is None
            _ready(scratch_db, id)
            replacement = fresh.claim()
            assert replacement is not None
            assert replacement.token != abandoned.token
            assert replacement.attempts == attempt + 1
    assert jobs.find(id).status == "FAILED"  # type: ignore[union-attr]
    assert jobs.find(id).diagnostic == "LEASE_EXPIRED"  # type: ignore[union-attr]
    assert jobs.result(id) is None


def test_retries_process_failure_but_not_permanent_failure(
    jobs: SimulationJobs, scratch_db: sa.Engine
) -> None:
    id = jobs.submit(request())
    claim = jobs.claim()
    assert claim is not None
    jobs.fail(id, claim.token, "SIMULATION_DEADLINE_EXCEEDED", True)  # type: ignore[arg-type]
    assert jobs.claim() is None
    _ready(scratch_db, id)
    second = jobs.claim()
    assert second is not None
    jobs.fail(id, second.token, "INVALID_CHILD_RESULT", False)  # type: ignore[arg-type]
    assert jobs.find(id).status == "FAILED"  # type: ignore[union-attr]
    assert jobs.find(id).attempts == 2  # type: ignore[union-attr]
    assert jobs.submit(request()) == id


def test_incomplete_solver_result_retained_without_success(
    jobs: SimulationJobs,
) -> None:
    id = jobs.submit(request())
    claim = jobs.claim()
    assert claim is not None
    result = compute(jobs, id)
    h = result.hindsight
    incomplete = hindsight.Outcome(
        hindsight.Status.FEASIBLE_NOT_PROVEN,
        "FEASIBLE",
        "NOT_RUN",
        h.dispatch,
        h.accounting,
        h.solver_objective,
        None,
        None,
        h.elapsed_nanos,
        h.limits,
        "Proof incomplete",
    )
    jobs.complete(
        id,
        claim.token,  # type: ignore[arg-type]
        comparison.SimulationComparison(
            result.fixed_dispatch, result.fixed_accounting, incomplete, None
        ),
    )
    assert jobs.find(id).status == "FAILED"  # type: ignore[union-attr]
    assert jobs.find(id).diagnostic == "SOLVER_FEASIBLE_NOT_PROVEN"  # type: ignore[union-attr]
    stored = jobs.result(id)
    assert stored is not None
    assert stored.hindsight == incomplete


def test_tampered_accounting_rejected_without_a_result(
    jobs: SimulationJobs,
) -> None:
    id = jobs.submit(request())
    claim = jobs.claim()
    assert claim is not None
    result = compute(jobs, id)
    a = result.fixed_accounting
    invalid = Accounting(
        a.imported_mwh,
        a.exported_mwh,
        a.charging_cost,
        a.revenue,
        a.fees,
        a.degradation,
        a.margin + 1,
        a.losses_mwh,
    )
    with pytest.raises(ValueError):
        jobs.complete(
            id,
            claim.token,  # type: ignore[arg-type]
            comparison.SimulationComparison(
                result.fixed_dispatch, invalid, result.hindsight, None
            ),
        )
    assert jobs.result(id) is None
    assert jobs.find(id).status == "RUNNING"  # type: ignore[union-attr]


def test_publication_failure_rolls_back_result_and_terminal_state(
    jobs: SimulationJobs, scratch_db: sa.Engine
) -> None:
    id = jobs.submit(request())
    claim = jobs.claim()
    assert claim is not None
    result = compute(jobs, id)
    with scratch_db.begin() as conn:
        conn.execute(
            text(
                "CREATE FUNCTION fail_simulation_finish() RETURNS trigger"
                " LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'injected';"
                " END; $$"
            )
        )
        conn.execute(
            text(
                "CREATE TRIGGER fail_simulation_finish BEFORE UPDATE"
                " ON simulation_job FOR EACH ROW"
                " EXECUTE FUNCTION fail_simulation_finish()"
            )
        )
    try:
        with pytest.raises(sa.exc.DatabaseError):
            jobs.complete(id, claim.token, result)  # type: ignore[arg-type]
        assert _count(scratch_db, "simulation_result") == 0
        assert jobs.find(id).status == "RUNNING"  # type: ignore[union-attr]
    finally:
        with scratch_db.begin() as conn:
            conn.execute(text("DROP TRIGGER fail_simulation_finish ON simulation_job"))
            conn.execute(text("DROP FUNCTION fail_simulation_finish()"))
    jobs.complete(id, claim.token, result)  # type: ignore[arg-type]


def test_expiry_during_publication_rolls_back_result(
    jobs: SimulationJobs, scratch_db: sa.Engine
) -> None:
    id = jobs.submit(request())
    claim = jobs.claim()
    assert claim is not None
    result = compute(jobs, id)
    with scratch_db.begin() as conn:
        conn.execute(
            text(
                "CREATE FUNCTION expire_simulation() RETURNS trigger"
                " LANGUAGE plpgsql AS $$ BEGIN UPDATE simulation_job"
                " SET lease_until = clock_timestamp() - interval '1 second'"
                " WHERE id = NEW.id; RETURN NEW; END; $$"
            )
        )
        conn.execute(
            text(
                "CREATE TRIGGER expire_simulation BEFORE INSERT"
                " ON simulation_result FOR EACH ROW"
                " EXECUTE FUNCTION expire_simulation()"
            )
        )
    try:
        with pytest.raises(StaleClaim):
            jobs.complete(id, claim.token, result)  # type: ignore[arg-type]
        assert jobs.result(id) is None
    finally:
        with scratch_db.begin() as conn:
            conn.execute(text("DROP TRIGGER expire_simulation ON simulation_result"))
            conn.execute(text("DROP FUNCTION expire_simulation()"))


def test_queue_capacity_and_submission_rollback_leave_no_orphan_inputs(
    jobs: SimulationJobs, scratch_db: sa.Engine
) -> None:
    with scratch_db.begin() as conn:
        conn.execute(
            text(
                "CREATE FUNCTION fail_simulation_submit() RETURNS trigger"
                " LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'injected';"
                " END; $$"
            )
        )
        conn.execute(
            text(
                "CREATE TRIGGER fail_simulation_submit BEFORE INSERT"
                " ON simulation_job FOR EACH ROW"
                " EXECUTE FUNCTION fail_simulation_submit()"
            )
        )
    try:
        with pytest.raises(sa.exc.DatabaseError):
            jobs.submit(request())
        assert _count(scratch_db, "simulation_input") == 0
    finally:
        with scratch_db.begin() as conn:
            conn.execute(text("DROP TRIGGER fail_simulation_submit ON simulation_job"))
            conn.execute(text("DROP FUNCTION fail_simulation_submit()"))
    first = jobs.submit(request())
    for fee in range(1, 100):
        jobs.submit(request(fee))
    with pytest.raises(QueueFull):
        jobs.submit(request(100))
    assert jobs.submit(request()) == first
    assert _count(scratch_db, "simulation_input") == 100


def test_running_refresh_does_not_block_simulation_claims(
    jobs: SimulationJobs, store: PriceStore, scratch_db: sa.Engine
) -> None:
    import uuid as uuid_

    backfill = store.create_backfill(Region.NSW1, DAY, DAY + timedelta(days=1))
    with scratch_db.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO refresh_job(id, backfill_id, region, market_day,"
                " status, attempts, claim_token, lease_until) VALUES (:id,"
                " :backfill, 'NSW1', :day, 'RUNNING', 1, :token,"
                " clock_timestamp() + interval '5 minutes')"
            ),
            {
                "id": uuid_.uuid4(),
                "backfill": backfill,
                "day": DAY,
                "token": uuid_.uuid4(),
            },
        )
    id = jobs.submit(request())
    claim = jobs.claim()
    assert claim is not None
    assert claim.id == id


def test_java_era_rows_read_back_and_unsupported_versions_blocked(
    jobs: SimulationJobs, store: PriceStore, scratch_db: sa.Engine
) -> None:
    """Historical rows written by the Java service keep reading; their stored
    ``ojAlgo`` versions are rejected for execution rather than silently
    converted."""
    import uuid as uuid_

    revision = store.coverage(Region.NSW1, DAY)
    assert revision is not None
    prepared = simulations.prepare(store, scenario_request())
    java_versions = {
        "request": "simulation-request-v1",
        "model": "battery-v1",
        "fixed": "ordered-windows-v1",
        "hindsight": "ordered-hindsight-v1",
        "solver": "ojAlgo 57.3.0",
        "executionProfile": "ordered-comparison-v1",
        "limits": {"milliseconds": 5000, "iterations": 100000},
    }
    legacy_id = uuid_.uuid4()
    with scratch_db.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO simulation_input"
                " (id, scenario_key, revision_id, request, versions)"
                " VALUES (:id, :key, :rev, CAST(:request AS jsonb),"
                " CAST(:versions AS jsonb))"
            ),
            {
                "id": legacy_id,
                "key": response_hash("java-era"),
                "rev": prepared.price_revision,
                "request": simulations._encode(
                    simulations._request_json(prepared.parameters.values)
                ),
                "versions": json.dumps(java_versions),
            },
        )
        conn.execute(
            text("INSERT INTO simulation_job(id, status) VALUES (:id, 'QUEUED')"),
            {"id": legacy_id},
        )
        legacy_result = (
            Path(__file__).resolve().parents[2]
            / "docs/project/evidence/python-rebuild/fixtures"
            / "saved-result-legacy-two-strategy.json"
        ).read_text()
        conn.execute(
            text(
                "INSERT INTO simulation_result(id, result)"
                " VALUES (:id, CAST(:result AS jsonb))"
            ),
            {"id": legacy_id, "result": legacy_result},
        )
    input = jobs.input(legacy_id)
    assert input.versions.solver == "ojAlgo 57.3.0"
    with pytest.raises(UnsupportedVersion):
        input.parameters()
    stored = jobs.result(legacy_id)
    assert stored is not None
    assert stored.threshold is None
    assert stored.hindsight.status is hindsight.Status.OPTIMAL
    assert len(stored.fixed_dispatch.intervals) == 288
