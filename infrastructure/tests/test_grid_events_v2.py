"""NEM-088/089/090 — detector-v2 publication tests.

Publishes the ``v2`` suite over seeded price/demand revisions and checks
stored v2 events: linked member ids, immutable evidence ``detail``, honest
insufficient-baseline recording, dedupe and corrected-source re-versioning.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
import sqlalchemy as sa
from db_fixture import apply_grid_schema
from test_grid_events import (
    AT,
    DAY,
    DAY2,
    _flat_prices,
    _grid_fetch,
    _seed,
)

from nemlab_core.detectors import (
    DETECTOR_PARAMS,
    DETECTOR_VERSION_V2,
)
from nemlab_core.prices import Region
from nemlab_infrastructure.grid.events import GridCatalogue
from nemlab_infrastructure.grid.store import GridStore


@pytest.fixture
def engine(scratch_db: sa.Engine) -> sa.Engine:
    apply_grid_schema(scratch_db)
    return scratch_db


@pytest.fixture
def catalogue(engine: sa.Engine) -> GridCatalogue:
    return GridCatalogue(engine)


def _v2(catalogue: GridCatalogue, start: date, end: date):
    return catalogue.publish(Region.NSW1, start, end, suite=DETECTOR_VERSION_V2)


def test_v2_suite_rejected_values(catalogue: GridCatalogue) -> None:
    with pytest.raises(ValueError):
        catalogue.publish(Region.NSW1, DAY, DAY2, suite="v3")


def test_reversal_event_published(catalogue: GridCatalogue, engine: sa.Engine) -> None:
    prices = _flat_prices()
    for i in range(10, 13):
        prices[i] = Decimal("-100")
    prices[60] = Decimal("1500")
    _seed(engine, DAY, prices=prices)
    _seed(engine, DAY2)
    publication = _v2(catalogue, DAY, DAY2 + timedelta(days=1))
    events = catalogue.events(publication.id)
    reversal = next(e for e in events if e.type.value == "price_reversal")
    run = next(e for e in events if e.type.value == "negative_price_run")
    assert reversal.detector_version == "v2"
    assert reversal.detector_params == DETECTOR_PARAMS["price_reversal"]
    detail = reversal.detail
    assert detail is not None
    assert detail["trough"] == "-100" and detail["peak"] == "1500"
    assert detail["peakMarketDay"] == DAY.isoformat()
    # member ids resolve to the stored run
    assert str(run.id) in detail["memberIds"]
    # replay snapshot exists and covers the look-ahead window
    replay = catalogue.replay(reversal.id)
    assert replay is not None
    price_days = replay["payload"]["price"]
    assert price_days[DAY.isoformat()][60] == "1500"


def test_episode_published_with_member_ids(
    catalogue: GridCatalogue, engine: sa.Engine
) -> None:
    prices = _flat_prices()
    for i in range(10, 13):
        prices[i] = Decimal("-20")
    prices[13] = Decimal("30")  # one-interval non-negative gap <= 50
    for i in range(14, 18):
        prices[i] = Decimal("-30")
    _seed(engine, DAY, prices=prices)
    _seed(engine, DAY2)
    publication = _v2(catalogue, DAY, DAY2 + timedelta(days=1))
    events = catalogue.events(publication.id)
    episode = next(e for e in events if e.type.value == "negative_price_episode")
    runs = [e for e in events if e.type.value == "negative_price_run"]
    assert len(runs) == 2
    detail = episode.detail
    assert detail is not None
    assert detail["memberCount"] == 2
    assert detail["negativeMinutes"] == 35
    assert detail["gapMinutes"] == 5
    assert detail["spanMinutes"] == 40
    assert {str(r.id) for r in runs} == set(detail["memberIds"])
    assert episode.value == Decimal("-30")  # deepest member trough


def test_unusual_ramp_insufficient_baseline(
    catalogue: GridCatalogue, engine: sa.Engine
) -> None:
    """Without 90 days of demand history the outcome is recorded, not
    claimed — the day coverage reports ``insufficient_baseline``."""
    demand = [Decimal("5000")] * 36 + [Decimal("8000")] * 252
    _seed(engine, DAY, demand=demand)
    publication = _v2(catalogue, DAY, DAY + timedelta(days=1))
    assert publication.coverage[DAY.isoformat()]["unusual_demand_ramp"] == (
        "insufficient_baseline"
    )
    assert all(
        e.type.value != "unusual_demand_ramp" for e in catalogue.events(publication.id)
    )


def test_unusual_ramp_with_baseline_history(
    catalogue: GridCatalogue, engine: sa.Engine
) -> None:
    """90 preceding complete demand days with small ramps: a 3000 MW rise
    clears the P90 and the 1000 MW floor."""
    start = DAY - timedelta(days=90)
    # baseline: every day rises 100 MW over the window
    baseline_demand = [Decimal("5000")] * 36 + [Decimal("5100")] * 252
    for offset in range(90):
        _seed(engine, start + timedelta(days=offset), demand=list(baseline_demand))
    big = [Decimal("5000")] * 36 + [Decimal("8000")] * 252
    _seed(engine, DAY, demand=big)
    publication = _v2(catalogue, DAY, DAY + timedelta(days=1))
    assert publication.coverage[DAY.isoformat()]["unusual_demand_ramp"] == "unusual"
    events = catalogue.events(publication.id)
    unusual = next(e for e in events if e.type.value == "unusual_demand_ramp")
    ramp = next(e for e in events if e.type.value == "demand_ramp")
    detail = unusual.detail
    assert detail is not None
    assert detail["riseMw"] == "3000"
    assert detail["completeDays"] == 90
    assert detail["quantile"] == "P90"
    assert detail["quantileValue"] == "100"
    assert str(ramp.id) in detail["memberIds"]
    # 90 baseline revisions pinned in the evidence
    assert len(detail["baselineRevisions"]) == 90


def test_v2_dedupe_and_detail_reversion(
    catalogue: GridCatalogue, engine: sa.Engine
) -> None:
    """Identical inputs dedupe; a baseline correction re-versions the event
    because its evidence detail changed."""
    start = DAY - timedelta(days=90)
    baseline_demand = [Decimal("5000")] * 36 + [Decimal("5100")] * 252
    for offset in range(90):
        _seed(engine, start + timedelta(days=offset), demand=list(baseline_demand))
    big = [Decimal("5000")] * 36 + [Decimal("8000")] * 252
    _seed(engine, DAY, demand=big)
    end = DAY + timedelta(days=1)
    first = _v2(catalogue, DAY, end)
    first_ids = {e.id for e in catalogue.events(first.id)}
    second = _v2(catalogue, DAY, end)
    second_ids = {e.id for e in catalogue.events(second.id)}
    assert first_ids == second_ids  # identical inputs dedupe

    # Correct one baseline day's demand -> different evidence manifest.
    corrected = [Decimal("5000")] * 36 + [Decimal("5200")] * 252
    GridStore(engine).save(_grid_fetch(start, corrected, AT + timedelta(minutes=1)))
    third = _v2(catalogue, DAY, end)
    third_events = catalogue.events(third.id)
    unusual_new = next(e for e in third_events if e.type.value == "unusual_demand_ramp")
    unusual_old = next(
        e for e in catalogue.events(first.id) if e.type.value == "unusual_demand_ramp"
    )
    assert unusual_new.id != unusual_old.id
    assert unusual_new.version == 2
    assert unusual_old.superseded
    # the old version's evidence stays reproducible
    assert unusual_old.detail is not None
    assert unusual_old.detail["baselineRevisions"] != (
        unusual_new.detail["baselineRevisions"] if unusual_new.detail else None
    )


def test_v1_publication_has_no_v2_events(
    catalogue: GridCatalogue, engine: sa.Engine
) -> None:
    """The v1 suite never emits v2 types — publishing them is explicit."""
    prices = _flat_prices()
    for i in range(10, 13):
        prices[i] = Decimal("-100")
    prices[60] = Decimal("1500")
    _seed(engine, DAY, prices=prices)
    _seed(engine, DAY2)
    publication = catalogue.publish(Region.NSW1, DAY, DAY2 + timedelta(days=1))
    types = {e.type.value for e in catalogue.events(publication.id)}
    assert types <= {"negative_price_run", "price_spike", "demand_ramp"}
    assert DAY.isoformat() in publication.coverage
    assert "unusual_demand_ramp" not in publication.coverage[DAY.isoformat()]
