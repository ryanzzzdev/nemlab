"""NEM-058 versioned event publication and replay snapshot tests.

Runs against a throwaway ``nemlab_test_*`` database per test on the server
named by ``NEMLAB_DB_URL`` and skips when unreachable.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
import sqlalchemy as sa
from db_fixture import apply_grid_schema

from nemlab_core.detectors import DETECTOR_PARAMS, DETECTOR_VERSION
from nemlab_core.prices import Region
from nemlab_infrastructure.grid.batch import GridBatch, Metric
from nemlab_infrastructure.grid.batch import Slot as GridSlot
from nemlab_infrastructure.grid.events import GridCatalogue
from nemlab_infrastructure.grid.source import GridFetch
from nemlab_infrastructure.grid.store import GridStore
from nemlab_infrastructure.prices.batch import Kind, PriceBatch, hash
from nemlab_infrastructure.prices.batch import Slot as PriceSlot
from nemlab_infrastructure.prices.source import Fetch
from nemlab_infrastructure.prices.store import PriceStore

REGION = Region.NSW1
DAY = date(2023, 9, 4)
DAY2 = date(2023, 9, 5)
AT = datetime(2026, 9, 17, tzinfo=UTC)


@pytest.fixture
def engine(scratch_db: sa.Engine) -> sa.Engine:
    apply_grid_schema(scratch_db)
    return scratch_db


@pytest.fixture
def catalogue(engine: sa.Engine) -> GridCatalogue:
    return GridCatalogue(engine)


def _price_fetch(day: date, values: list[Decimal | None], at: datetime = AT) -> Fetch:
    slots = tuple(
        PriceSlot(Kind.VALUE if v is not None else Kind.MISSING, v) for v in values
    )
    return Fetch(
        PriceBatch(REGION, day, slots), at, hash(f"price-{day}-{values[0]}-{at}"), "t-1"
    )


def _grid_fetch(
    day: date,
    demand: list[Decimal | None] | None = None,
    at: datetime = AT,
) -> GridFetch:
    """One market fetch with demand + both flow series."""

    def slots(values: list[Decimal | None]) -> tuple[GridSlot, ...]:
        return tuple(
            GridSlot(Kind.VALUE if v is not None else Kind.MISSING, v) for v in values
        )

    flat = [Decimal("12")] * 288
    batches = [
        GridBatch(
            REGION, Metric.DEMAND, "", day, slots(demand or [Decimal("5000")] * 288)
        ),
        GridBatch(REGION, Metric.FLOW_IMPORTS, "", day, slots(flat)),
        GridBatch(REGION, Metric.FLOW_EXPORTS, "", day, slots(flat)),
    ]
    return GridFetch(tuple(batches), at, hash(f"grid-{day}-{at}"), "t-1")


def _flat_prices(value: str = "50") -> list[Decimal | None]:
    return [Decimal(value)] * 288


def _seed(
    engine: sa.Engine,
    day: date,
    prices: list[Decimal | None] | None = None,
    demand: list[Decimal | None] | None = None,
    at: datetime = AT,
) -> None:
    PriceStore(engine).save(_price_fetch(day, prices or _flat_prices(), at))
    GridStore(engine).save(_grid_fetch(day, demand, at))


# -- detection and publication -------------------------------------------------


def test_publish_flat_days_no_events(
    catalogue: GridCatalogue, engine: sa.Engine
) -> None:
    _seed(engine, DAY)
    publication = catalogue.publish(REGION, DAY, DAY + timedelta(days=1))
    assert publication.event_count == 0
    assert publication.coverage[DAY.isoformat()]["price"]["missing"] == 0
    assert publication.coverage[DAY.isoformat()]["demand_ramp"] == "none"
    current = catalogue.current(REGION, DAY, DAY + timedelta(days=1))
    assert current is not None and current.id == publication.id


def test_negative_run_and_spike_events(
    catalogue: GridCatalogue, engine: sa.Engine
) -> None:
    prices = _flat_prices()
    prices[10] = prices[11] = prices[12] = Decimal("-7")
    prices[100] = Decimal("1500")
    _seed(engine, DAY, prices=prices)
    publication = catalogue.publish(REGION, DAY, DAY + timedelta(days=1))
    events = catalogue.events(publication.id)
    run = next(e for e in events if e.type.value == "negative_price_run")
    assert run.interval_count == 3 and run.value == Decimal("-7")
    # position 10 interval-end = NEM 00:55 on the market day = 14:55 UTC prior
    assert run.start_at == datetime(2023, 9, 3, 14, 55, tzinfo=UTC)
    assert run.market_day == DAY
    spike = next(e for e in events if e.type.value == "price_spike")
    assert spike.interval_count == 1 and spike.value == Decimal("1500")
    assert spike.detector_params == DETECTOR_PARAMS["price_spike"]
    assert spike.detector_version == DETECTOR_VERSION


def test_cross_midnight_run_owned_by_start_day(
    catalogue: GridCatalogue, engine: sa.Engine
) -> None:
    day1 = _flat_prices()
    day2 = _flat_prices()
    for i in range(280, 288):
        day1[i] = Decimal("-3")
    for i in range(0, 4):
        day2[i] = Decimal("-3")
    _seed(engine, DAY, prices=day1)
    _seed(engine, DAY2, prices=day2)
    publication = catalogue.publish(REGION, DAY, DAY2 + timedelta(days=1))
    events = catalogue.events(publication.id)
    runs = [e for e in events if e.type.value == "negative_price_run"]
    assert len(runs) == 1
    run = runs[0]
    assert run.market_day == DAY and run.interval_count == 12
    # last member = position 3 on DAY2; interval-end NEM 00:20 = UTC 14:20 DAY
    assert run.end_at == datetime(2023, 9, 4, 14, 20, tzinfo=UTC)


def test_demand_ramp_event(catalogue: GridCatalogue, engine: sa.Engine) -> None:
    demand = [Decimal("5000")] * 36 + [Decimal("5600")] * 252
    _seed(engine, DAY, demand=demand)
    publication = catalogue.publish(REGION, DAY, DAY + timedelta(days=1))
    events = catalogue.events(publication.id)
    ramp = next(e for e in events if e.type.value == "demand_ramp")
    assert ramp.interval_count == 37 and ramp.value == Decimal("600")
    assert ramp.source_revisions["demand"][DAY.isoformat()]


def test_late_price_arrival_reversions_context_snapshot(
    catalogue: GridCatalogue, engine: sa.Engine
) -> None:
    """A demand ramp pins no price revision when price was never imported.
    A later price import changes the replay context, so republication must
    mint a new event version whose snapshot carries the price series —
    detector inputs alone cannot dedupe a context drift."""
    demand = [Decimal("5000")] * 36 + [Decimal("5600")] * 252
    GridStore(engine).save(_grid_fetch(DAY, demand))  # grid only, no price
    end = DAY + timedelta(days=1)
    first = catalogue.publish(REGION, DAY, end)
    ramp = next(e for e in catalogue.events(first.id) if e.type.value == "demand_ramp")
    old_replay = catalogue.replay(ramp.id)
    assert old_replay is not None
    assert old_replay["manifest"]["series"][0]["days"] == {DAY.isoformat(): None}
    assert "price" not in old_replay["payload"]

    PriceStore(engine).save(
        _price_fetch(DAY, _flat_prices(), AT + timedelta(minutes=1))
    )
    second = catalogue.publish(REGION, DAY, end)
    updated = next(
        e for e in catalogue.events(second.id) if e.type.value == "demand_ramp"
    )
    assert updated.id != ramp.id and updated.version == 2
    new_replay = catalogue.replay(updated.id)
    assert new_replay is not None
    assert new_replay["payload"]["price"][DAY.isoformat()][0] == "50"


def test_incomplete_demand_withholds_ramp(
    catalogue: GridCatalogue, engine: sa.Engine
) -> None:
    demand = [Decimal("5000")] * 36 + [Decimal("5600")] * 251 + [None]
    _seed(engine, DAY, demand=demand)
    publication = catalogue.publish(REGION, DAY, DAY + timedelta(days=1))
    assert publication.coverage[DAY.isoformat()]["demand_ramp"] == (
        "insufficient_coverage"
    )
    assert all(e.type.value != "demand_ramp" for e in catalogue.events(publication.id))


def test_missing_day_records_coverage_no_events(
    catalogue: GridCatalogue,
) -> None:
    publication = catalogue.publish(REGION, DAY, DAY + timedelta(days=1))
    day = publication.coverage[DAY.isoformat()]
    assert day["price"]["missing"] == 288
    assert day["demand"]["missing"] == 288
    assert publication.event_count == 0


def test_edge_incomplete_run_recorded(
    catalogue: GridCatalogue, engine: sa.Engine
) -> None:
    # Run open at the window's right edge: last 4 positions negative.
    prices = _flat_prices()
    for i in range(284, 288):
        prices[i] = Decimal("-2")
    _seed(engine, DAY, prices=prices)
    publication = catalogue.publish(REGION, DAY, DAY + timedelta(days=1))
    events = catalogue.events(publication.id)
    run = next(e for e in events if e.type.value == "negative_price_run")
    assert run.edge_incomplete is True
    assert run.coverage["edge_incomplete"] is True


def test_publication_bounds(catalogue: GridCatalogue) -> None:
    with pytest.raises(ValueError):
        catalogue.publish(REGION, DAY, DAY)
    with pytest.raises(ValueError):
        catalogue.publish(REGION, DAY, DAY + timedelta(days=32))


# -- versioning ----------------------------------------------------------------


def test_rerun_dedupes_events(catalogue: GridCatalogue, engine: sa.Engine) -> None:
    prices = _flat_prices()
    prices[10] = prices[11] = prices[12] = Decimal("-7")
    _seed(engine, DAY, prices=prices)
    end = DAY + timedelta(days=1)
    first = catalogue.publish(REGION, DAY, end)
    second = catalogue.publish(REGION, DAY, end)
    first_events = catalogue.events(first.id)
    second_events = catalogue.events(second.id)
    assert {e.id for e in first_events} == {e.id for e in second_events}
    assert all(e.version == 1 for e in second_events)
    current = catalogue.current(REGION, DAY, end)
    assert current is not None and current.id == second.id
    with engine.connect() as conn:
        publications = conn.execute(
            sa.text("SELECT count(*) FROM grid_publication")
        ).scalar_one()
    assert publications == 2


def test_correction_supersedes_event(
    catalogue: GridCatalogue, engine: sa.Engine
) -> None:
    prices = _flat_prices()
    prices[10] = prices[11] = prices[12] = Decimal("-7")
    _seed(engine, DAY, prices=prices)
    end = DAY + timedelta(days=1)
    first = catalogue.publish(REGION, DAY, end)
    original = next(
        e for e in catalogue.events(first.id) if e.type.value == "negative_price_run"
    )
    # Correction: deepen the trough — a new price revision for the same day.
    corrected = _flat_prices()
    corrected[10] = corrected[11] = corrected[12] = Decimal("-9")
    PriceStore(engine).save(_price_fetch(DAY, corrected, AT + timedelta(minutes=1)))
    second = catalogue.publish(REGION, DAY, end)
    updated = next(
        e for e in catalogue.events(second.id) if e.type.value == "negative_price_run"
    )
    assert updated.id != original.id
    assert updated.version == 2 and updated.value == Decimal("-9")
    # The superseded version and its replay remain reproducible.
    assert any(e.id == original.id and e.superseded for e in catalogue.events(first.id))
    old_replay = catalogue.replay(original.id)
    assert old_replay is not None
    price_values = old_replay["payload"]["price"][DAY.isoformat()]
    assert price_values[10] == "-7"
    new_replay = catalogue.replay(updated.id)
    assert new_replay is not None
    assert new_replay["payload"]["price"][DAY.isoformat()][10] == "-9"


def test_replay_manifest_pins_revisions_and_bounds(
    catalogue: GridCatalogue, engine: sa.Engine
) -> None:
    prices = _flat_prices()
    prices[10] = prices[11] = prices[12] = Decimal("-7")
    _seed(engine, DAY, prices=prices)
    publication = catalogue.publish(REGION, DAY, DAY + timedelta(days=1))
    event = next(
        e
        for e in catalogue.events(publication.id)
        if e.type.value == "negative_price_run"
    )
    replay = catalogue.replay(event.id)
    assert replay is not None
    manifest = replay["manifest"]
    assert manifest["event_id"] == str(event.id)
    assert manifest["window"]["end_exclusive"] == (DAY + timedelta(days=1)).isoformat()
    price_series = next(s for s in manifest["series"] if s["metric"] == "price")
    assert price_series["grid"] == "interval_end"
    assert price_series["days"][DAY.isoformat()] is not None
    assert len(replay["payload"]["price"][DAY.isoformat()]) == 288
    assert catalogue.replay(event.id) == replay  # immutable, reproducible


def test_replay_unknown_event_returns_none(catalogue: GridCatalogue) -> None:
    import uuid

    assert catalogue.replay(uuid.uuid4()) is None


# -- immutability and atomicity -------------------------------------------------


def test_event_replay_publication_immutable(
    catalogue: GridCatalogue, engine: sa.Engine
) -> None:
    _seed(engine, DAY)
    publication = catalogue.publish(REGION, DAY, DAY + timedelta(days=1))
    with pytest.raises(sa.exc.DBAPIError), engine.begin() as conn:
        conn.execute(
            sa.text("UPDATE grid_publication SET coverage='{}' WHERE id=:id"),
            {"id": publication.id},
        )


def test_failure_rolls_back_and_records_run(
    catalogue: GridCatalogue, engine: sa.Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    prices = _flat_prices()
    prices[10] = prices[11] = prices[12] = Decimal("-7")
    _seed(engine, DAY, prices=prices)
    monkeypatch.setattr(
        catalogue,
        "_materialise_replay",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    with pytest.raises(RuntimeError, match="boom"):
        catalogue.publish(REGION, DAY, DAY + timedelta(days=1))
    with engine.connect() as conn:
        assert (
            conn.execute(sa.text("SELECT count(*) FROM grid_event")).scalar_one() == 0
        )
        assert (
            conn.execute(
                sa.text("SELECT count(*) FROM grid_catalogue_current")
            ).scalar_one()
            == 0
        )
        status = conn.execute(
            sa.text("SELECT status FROM grid_detection_run")
        ).scalar_one()
    assert status == "FAILED"


def test_detection_run_audited_on_success(
    catalogue: GridCatalogue, engine: sa.Engine
) -> None:
    _seed(engine, DAY)
    publication = catalogue.publish(REGION, DAY, DAY + timedelta(days=1))
    with engine.connect() as conn:
        row = conn.execute(
            sa.text("SELECT status, publication_id FROM grid_detection_run")
        ).one()
    assert row.status == "COMPLETE"
    assert row.publication_id == publication.id
