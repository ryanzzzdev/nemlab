"""NEM-117 — bounded catalogue/detail projections over stored simulations.

Filters, counts, keyset cursors, threshold-optional rows and provenance
comparison are exercised on real PostgreSQL; no result payload is decoded
for list rows.
"""

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from db_fixture import apply_schema
from sqlalchemy import text
from test_simulations import AT, DAY, compute, request

from nemlab_core.prices import Region
from nemlab_core.request import (
    Costs,
    EfficiencyInput,
    SimulationRequest,
    Site,
    ThresholdInput,
    Windows,
)
from nemlab_infrastructure.prices.batch import Kind, PriceBatch, Slot
from nemlab_infrastructure.prices.batch import hash as response_hash
from nemlab_infrastructure.prices.source import Fetch
from nemlab_infrastructure.prices.store import PriceStore
from nemlab_infrastructure.simulation_catalogue import (
    InvalidCursor,
    InvalidScope,
    SimulationCatalogue,
)
from nemlab_infrastructure.simulations import SimulationJobs

BODY = (
    Path(__file__).resolve().parents[2]
    / "docs/project/evidence/oe-validation/historical-price-response.json"
).read_text()


def fetch(first: str = "-30", at: datetime = AT) -> Fetch:
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
    prices.save(fetch())
    return prices


@pytest.fixture
def jobs(store: PriceStore) -> SimulationJobs:
    return SimulationJobs(store.engine)


@pytest.fixture
def catalogue(store: PriceStore) -> SimulationCatalogue:
    return SimulationCatalogue(store.engine)


def _finish(jobs: SimulationJobs, id: UUID) -> None:
    """Claim + complete one job with the real engine."""
    with jobs.engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE simulation_job SET available_at = clock_timestamp()"
                " - interval '1 second' WHERE id = :id"
            ),
            {"id": id},
        )
    job = jobs.claim()
    assert job is not None and job.id == id
    jobs.complete(id, job.token, compute(jobs, id))


def test_empty_scope_is_rejected(catalogue: SimulationCatalogue) -> None:
    with pytest.raises(InvalidScope):
        catalogue.page(region=Region.NSW1, start=None, end=None)
    with pytest.raises(InvalidScope):
        catalogue.page(
            region=Region.NSW1,
            start=DAY,
            end=date(2023, 10, 20),  # 40 days > 31
        )
    with pytest.raises(InvalidScope):
        catalogue.page(region=Region.NSW1, start=DAY, end=date(2023, 9, 1))
    with pytest.raises(InvalidScope):
        catalogue.page(region=Region.NSW1, start=DAY, end=DAY, status="BOGUS")
    with pytest.raises(InvalidScope):
        catalogue.page(region=Region.NSW1, start=DAY, end=DAY, strategy="oracle")
    with pytest.raises(InvalidScope):
        catalogue.page(region=Region.NSW1, start=DAY, end=DAY, limit=0)
    with pytest.raises(InvalidScope):
        catalogue.page(region=Region.NSW1, start=DAY, end=DAY, limit=101)


def test_page_lists_summaries_without_result_decoding(
    jobs: SimulationJobs, catalogue: SimulationCatalogue
) -> None:
    submitted = jobs.submit(request())
    _finish(jobs, submitted)
    queued = jobs.submit(
        SimulationRequest(
            Region.NSW1,
            DAY,
            Site(*[Decimal(1)] * 8),
            EfficiencyInput(Decimal(1), Decimal(1), None),
            Costs(Decimal(0), Decimal(0), Decimal(0)),
            Windows(600, 840, 1020, 1260),
            ThresholdInput(Decimal(10), Decimal(50)),
        )
    )
    page = catalogue.page(region=Region.NSW1, start=DAY, end=DAY)
    assert page.total == 2
    assert page.counts == {"QUEUED": 1, "RUNNING": 0, "SUCCEEDED": 1, "FAILED": 0}
    assert len(page.rows) == 2
    done = next(r for r in page.rows if r.id == submitted)
    waiting = next(r for r in page.rows if r.id == queued)
    assert done.status == "SUCCEEDED" and done.has_result and done.finished_at
    assert done.strategies == ("fixed", "hindsight")
    assert waiting.status == "QUEUED" and not waiting.has_result
    assert waiting.strategies == ("fixed", "threshold", "hindsight")
    assert waiting.capacity_mwh == Decimal(1)


def test_filters_and_counts_ignore_status_but_keep_scope(
    jobs: SimulationJobs, catalogue: SimulationCatalogue
) -> None:
    jobs.submit(request())
    page = catalogue.page(region=Region.NSW1, start=DAY, end=DAY, status="SUCCEEDED")
    assert page.rows == []
    # Counts reflect scope without the status filter.
    assert page.counts["QUEUED"] == 1
    assert page.total == 1
    empty = catalogue.page(region=Region.QLD1, start=DAY, end=DAY)
    assert empty.rows == [] and empty.total == 0


def test_keyset_pagination_is_deterministic_and_newest_first(
    jobs: SimulationJobs, catalogue: SimulationCatalogue, store: PriceStore
) -> None:
    # Sequential submits get increasing created_at; ties fall back to id.
    ids = [jobs.submit(request(fee=i + 1)) for i in range(3)]
    page1 = catalogue.page(region=Region.NSW1, start=DAY, end=DAY, limit=2)
    assert [r.id for r in page1.rows] == [ids[2], ids[1]]
    assert page1.next_cursor
    page2 = catalogue.page(
        region=Region.NSW1,
        start=DAY,
        end=DAY,
        limit=2,
        cursor=page1.next_cursor,
    )
    assert [r.id for r in page2.rows] == [ids[0]]
    assert page2.next_cursor is None


def test_cursor_rejects_malformed_and_foreign_scope(
    jobs: SimulationJobs, catalogue: SimulationCatalogue, store: PriceStore
) -> None:
    jobs.submit(request())
    page = catalogue.page(region=Region.NSW1, start=DAY, end=DAY, limit=1)
    with pytest.raises(InvalidCursor):
        catalogue.page(region=Region.NSW1, start=DAY, end=DAY, cursor="junk")
    with pytest.raises(InvalidCursor):
        catalogue.page(
            region=Region.QLD1,  # different scope
            start=DAY,
            end=DAY,
            cursor=page.next_cursor or "",
        )


def test_detail_projects_scenario_result_execution_provenance(
    jobs: SimulationJobs, catalogue: SimulationCatalogue
) -> None:
    id = jobs.submit(request())
    _finish(jobs, id)
    detail = catalogue.detail(id)
    assert detail is not None
    assert detail.summary.status == "SUCCEEDED"
    assert detail.summary.strategies == ("fixed", "hindsight")
    # Scenario: the recorded request, not UI defaults.
    assert detail.scenario.request["region"] == "NSW1"
    assert detail.scenario.request["day"] == str(DAY)
    assert detail.scenario.request["thresholds"] is None
    # Results: accounting + solver only.
    assert detail.result is not None
    assert "fixed" in detail.result.accounting
    assert "hindsight" in detail.result.accounting
    assert "threshold" not in detail.result.accounting
    assert detail.result.solver["status"] == "OPTIMAL"
    # Execution
    assert detail.execution.attempts == 1
    assert detail.execution.finished_at is not None
    # Provenance: pinned revision matches current stored coverage.
    assert detail.provenance.comparison == "matches"
    assert detail.provenance.pinned_revision == detail.provenance.current_revision


def test_detail_without_result_is_still_inspectable(
    jobs: SimulationJobs, catalogue: SimulationCatalogue
) -> None:
    id = jobs.submit(request())
    detail = catalogue.detail(id)
    assert detail is not None
    assert detail.summary.status == "QUEUED"
    assert detail.result is None
    assert detail.execution.finished_at is None


def test_unknown_id_is_none(catalogue: SimulationCatalogue) -> None:
    assert catalogue.detail(uuid4()) is None


def test_provenance_different_when_prices_corrected(
    jobs: SimulationJobs, catalogue: SimulationCatalogue, store: PriceStore
) -> None:
    id = jobs.submit(request())
    _finish(jobs, id)
    before = catalogue.detail(id)
    assert before is not None and before.provenance.comparison == "matches"
    # Corrected prices land — the pinned revision must not move.
    store.save(fetch(first="-31"))
    after = catalogue.detail(id)
    assert after is not None
    assert after.provenance.comparison == "different"
    assert after.provenance.pinned_revision == before.provenance.pinned_revision
    assert after.provenance.current_revision != after.provenance.pinned_revision
    # The saved result itself is unchanged.
    assert after.result == before.result


def test_legacy_threshold_absent_request_round_trips(
    jobs: SimulationJobs, catalogue: SimulationCatalogue
) -> None:
    id = jobs.submit(request())
    # Simulate a Java-era row: thresholds key absent rather than null. The
    # immutability trigger is lifted only inside this fixture transaction.
    with jobs.engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE simulation_input"
                " DISABLE TRIGGER immutable_simulation_input"
            )
        )
        conn.execute(
            text(
                "UPDATE simulation_input"
                " SET request = request - 'thresholds' WHERE id = :id"
            ),
            {"id": id},
        )
        conn.execute(
            text(
                "ALTER TABLE simulation_input ENABLE TRIGGER immutable_simulation_input"
            )
        )
    detail = catalogue.detail(id)
    assert detail is not None
    assert detail.summary.strategies == ("fixed", "hindsight")
    page = catalogue.page(region=Region.NSW1, start=DAY, end=DAY, strategy="threshold")
    assert page.rows == []


def test_strategy_threshold_matches_configured_rows(
    jobs: SimulationJobs, catalogue: SimulationCatalogue
) -> None:
    jobs.submit(request())  # no thresholds
    jobs.submit(
        SimulationRequest(
            Region.NSW1,
            DAY,
            Site(*[Decimal(1)] * 8),
            EfficiencyInput(Decimal(1), Decimal(1), None),
            Costs(Decimal(0), Decimal(0), Decimal(0)),
            Windows(600, 840, 1020, 1260),
            ThresholdInput(Decimal(10), Decimal(50)),
        )
    )
    page = catalogue.page(region=Region.NSW1, start=DAY, end=DAY, strategy="threshold")
    assert page.total == 1 and len(page.rows) == 1
    assert "threshold" in page.rows[0].strategies
    # fixed/hindsight match every row — they always run.
    assert (
        catalogue.page(region=Region.NSW1, start=DAY, end=DAY, strategy="fixed").total
        == 2
    )
