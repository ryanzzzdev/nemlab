"""NEM-055 grid observation persistence and provider validation tests.

Integration tests run against a throwaway ``nemlab_test_*`` database per
test on the server named by ``NEMLAB_DB_URL`` and skip when unreachable.
"""

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
import sqlalchemy as sa
from db_fixture import apply_grid_schema

from nemlab_core.prices import NEM_OFFSET, Region
from nemlab_infrastructure.grid.batch import Metric
from nemlab_infrastructure.grid.source import (
    GridFetch,
    parse_market,
    parse_power,
)
from nemlab_infrastructure.grid.store import GridStore
from nemlab_infrastructure.prices.batch import Kind

DAY = date(2023, 9, 4)
AT = datetime(2026, 9, 17, tzinfo=UTC)
REGION = Region.NSW1


@pytest.fixture
def store(scratch_db: sa.Engine) -> GridStore:
    apply_grid_schema(scratch_db)
    return GridStore(scratch_db)


def _day_rows(value: object = 5000.0, gaps: tuple[int, ...] = ()) -> list[list[object]]:
    """288 source-label rows 00:00..23:55 plus a next-day boundary row."""
    start = datetime(2023, 9, 4, tzinfo=NEM_OFFSET)
    rows = [
        [(start + timedelta(minutes=5 * i)).isoformat(), value]
        for i in range(288)
        if i not in gaps
    ]
    rows.append([(start + timedelta(days=1)).isoformat(), value])
    return rows


def _entry(metric: str, rows: list[list[object]], fueltech: str | None = None) -> dict:
    columns = {"region": "NSW1"}
    if fueltech:
        columns["fueltech"] = fueltech
    return {
        "network_code": "NEM",
        "metric": metric,
        "interval": "5m",
        "unit": "MW",
        "results": [{"columns": columns, "data": rows}],
    }


def _body(*entries: dict) -> str:
    return json.dumps({"success": True, "version": "4.0", "data": list(entries)})


def _market_body(**overrides: object) -> str:
    entries = []
    for metric in ("demand", "flow_imports", "flow_exports"):
        entries.append(_entry(metric, overrides.get(metric, _day_rows())))  # type: ignore[arg-type]
    return _body(*entries)


def _fetch(body: str, *, power: bool = False, at: datetime = AT) -> GridFetch:
    parse = parse_power if power else parse_market
    return parse(REGION, DAY, body, at)


# -- provider parsing ---------------------------------------------------------


def test_parse_market_complete() -> None:
    fetch = _fetch(_market_body())
    assert len(fetch.series) == 3
    assert all(b.complete() for b in fetch.series)
    assert {b.metric for b in fetch.series} == set(
        (Metric.DEMAND, Metric.FLOW_IMPORTS, Metric.FLOW_EXPORTS)
    )
    assert all(b.series == "" for b in fetch.series)
    assert fetch.source_version == "4.0"


def test_parse_market_missing_metric_is_absent_series() -> None:
    body = _body(
        _entry("demand", _day_rows()),
        _entry("flow_imports", _day_rows()),
    )
    fetch = _fetch(body)
    by_metric = {b.metric: b for b in fetch.series}
    assert by_metric[Metric.DEMAND].complete()
    absent = by_metric[Metric.FLOW_EXPORTS]
    assert absent.count(Kind.MISSING) == 288


def test_parse_power_fueltechs() -> None:
    body = _body(
        {
            "network_code": "NEM",
            "metric": "power",
            "interval": "5m",
            "unit": "MW",
            "results": [
                {
                    "columns": {"region": "NSW1", "fueltech": "wind"},
                    "data": _day_rows(123.4),
                },
                {
                    "columns": {"region": "NSW1", "fueltech": "coal_black"},
                    "data": _day_rows(-8.5),
                },
            ],
        }
    )
    fetch = _fetch(body, power=True)
    assert {b.series for b in fetch.series} == {"wind", "coal_black"}
    signed = next(b for b in fetch.series if b.series == "coal_black")
    assert signed.slots[0].value == Decimal("-8.5")


def test_parse_null_vs_zero() -> None:
    rows = _day_rows()
    rows[0][1] = None
    rows[1][1] = 0
    fetch = _fetch(_market_body(demand=rows))
    demand = next(b for b in fetch.series if b.metric is Metric.DEMAND)
    assert demand.slots[0].kind is Kind.SOURCE_NULL
    assert demand.slots[1].kind is Kind.VALUE
    assert demand.slots[1].value == Decimal("0")


def test_parse_gap_row_is_missing() -> None:
    rows = _day_rows(gaps=(10,))
    fetch = _fetch(_market_body(demand=rows))
    demand = next(b for b in fetch.series if b.metric is Metric.DEMAND)
    assert demand.slots[10].kind is Kind.MISSING
    assert demand.count(Kind.MISSING) == 1


def test_parse_empty_data_is_all_missing() -> None:
    body = _body(
        _entry("demand", []),
        _entry("flow_imports", _day_rows()),
        _entry("flow_exports", _day_rows()),
    )
    fetch = _fetch(body)
    demand = next(b for b in fetch.series if b.metric is Metric.DEMAND)
    assert demand.count(Kind.MISSING) == 288


@pytest.mark.parametrize(
    "entry",
    [
        dict(_entry("demand", _day_rows()), unit="$/MWh"),  # wrong unit
        dict(_entry("demand", _day_rows()), interval="30m"),  # wrong interval
        {
            "network_code": "NEM",
            "metric": "demand",
            "interval": "5m",
            "unit": "MW",
            "results": [
                {"columns": {"region": "NSW1"}, "data": _day_rows()},
                {"columns": {"region": "NSW1"}, "data": _day_rows()},
            ],
        },  # duplicate result for a single-series metric
    ],
)
def test_parse_rejects_bad_entry(entry: dict) -> None:
    with pytest.raises(ValueError):
        _fetch(_body(entry))


def test_parse_rejects_duplicate_timestamp() -> None:
    rows = _day_rows()
    rows.append(rows[5])
    with pytest.raises(ValueError, match="Invalid OE"):
        _fetch(_market_body(demand=rows))


def test_parse_rejects_off_grid_timestamp() -> None:
    rows = _day_rows()
    rows[3][0] = "2023-09-04T01:03:00+10:00"  # not a 5m boundary
    with pytest.raises(ValueError):
        _fetch(_market_body(demand=rows))


def test_parse_rejects_nonnumeric_value() -> None:
    rows = _day_rows()
    rows[2][1] = "5000"
    with pytest.raises(ValueError):
        _fetch(_market_body(demand=rows))


def test_parse_rejects_bool_value() -> None:
    rows = _day_rows()
    rows[2][1] = True
    with pytest.raises(ValueError):
        _fetch(_market_body(demand=rows))


def test_parse_rejects_nan_literal() -> None:
    body = _market_body().replace("5000.0", "NaN", 1)
    with pytest.raises(ValueError):
        _fetch(body)


def test_parse_rejects_wrong_region() -> None:
    entry = _entry("demand", _day_rows())
    entry["results"][0]["columns"]["region"] = "QLD1"
    with pytest.raises(ValueError):
        _fetch(
            _body(
                entry,
                _entry("flow_imports", _day_rows()),
                _entry("flow_exports", _day_rows()),
            )
        )


def test_parse_rejects_unrequested_metric() -> None:
    body = _body(
        _entry("demand", _day_rows()),
        _entry("flow_imports", _day_rows()),
        _entry("flow_exports", _day_rows()),
        _entry("price", _day_rows()),
    )
    with pytest.raises(ValueError):
        _fetch(body)


def test_parse_power_rejects_missing_power() -> None:
    with pytest.raises(ValueError):
        _fetch(_body(_entry("demand", _day_rows())), power=True)


# -- store --------------------------------------------------------------------


def _save_market(store: GridStore, body: str | None = None, at: datetime = AT) -> dict:
    return store.save(_fetch(body or _market_body(), at=at))


def test_schema_objects(store: GridStore) -> None:
    with store.engine.connect() as conn:
        tables = {
            r[0]
            for r in conn.execute(
                sa.text(
                    "SELECT table_name FROM information_schema.tables"
                    " WHERE table_schema='public'"
                )
            )
        }
    assert {"grid_revision", "grid_current", "grid_import_attempt"} <= tables


def test_save_and_read_back(store: GridStore) -> None:
    revisions = _save_market(store)
    assert len(revisions) == 3
    batch = store.batch(REGION, Metric.DEMAND, "", DAY)
    assert batch is not None and batch.complete()
    assert batch.slots[0].value == Decimal("5000")
    values = store.values(REGION, Metric.DEMAND, "", DAY)
    assert values is not None and len(values) == 288 and values[0] == Decimal("5000")


def test_coverage_counts_and_keys(store: GridStore) -> None:
    _save_market(store, _market_body(demand=_day_rows(gaps=(5,))))
    cov = store.coverage(REGION, DAY)
    assert (Metric.DEMAND, "") in cov
    assert cov[(Metric.DEMAND, "")].missing == 1
    assert cov[(Metric.DEMAND, "")].complete is False


def test_idempotent_same_content(store: GridStore) -> None:
    first = _save_market(store)
    second = _save_market(store, at=AT + timedelta(hours=1))
    assert first == second  # same revisions, deduped by content hash
    with store.engine.connect() as conn:
        count = conn.execute(sa.text("SELECT count(*) FROM grid_revision")).scalar_one()
    assert count == 3  # no duplicates across two identical saves


def test_correction_creates_new_revision(store: GridStore) -> None:
    first = _save_market(store)
    rows = _day_rows(value=7777.7)
    second = _save_market(store, _market_body(demand=rows), at=AT + timedelta(hours=1))
    assert second[(Metric.DEMAND, "")] != first[(Metric.DEMAND, "")]
    assert second[(Metric.FLOW_IMPORTS, "")] == first[(Metric.FLOW_IMPORTS, "")]
    # Current moved to the correction.
    batch = store.batch(REGION, Metric.DEMAND, "", DAY)
    assert batch is not None and batch.slots[0].value == Decimal("7777.7")
    # The superseded revision still reads back exactly.
    old = store.revision(first[(Metric.DEMAND, "")])
    assert old.slots[0].value == Decimal("5000")


def test_stale_fetch_does_not_move_current(store: GridStore) -> None:
    _save_market(store, _market_body(demand=_day_rows(7777.7)), at=AT)
    _save_market(store, _market_body(demand=_day_rows(1.0)), at=AT - timedelta(hours=1))
    batch = store.batch(REGION, Metric.DEMAND, "", DAY)
    assert batch is not None and batch.slots[0].value == Decimal("7777.7")


def test_missing_series_vs_all_missing(store: GridStore) -> None:
    # Power was never fetched -> key absent entirely.
    _save_market(store)
    cov = store.coverage(REGION, DAY)
    assert (Metric.POWER, "wind") not in cov
    # Market response lacking flow_exports stored an explicit all-MISSING row.
    body = _body(_entry("demand", _day_rows()), _entry("flow_imports", _day_rows()))
    store.save(_fetch(body, at=AT + timedelta(hours=1)))
    cov = store.coverage(REGION, DAY)
    exports = cov[(Metric.FLOW_EXPORTS, "")]
    assert exports.missing == 288 and exports.valid == 0


def test_record_failure_and_history(store: GridStore) -> None:
    store.record_failure(
        REGION, DAY, ("demand", "flow_imports", "flow_exports"), AT, "HTTP_503"
    )
    _save_market(store, at=AT + timedelta(seconds=1))
    history = store.history(REGION, DAY)
    assert [a.status for a in history] == ["FAILED", "COMPLETE"]
    assert history[0].revision_count == 0 and history[0].diagnostic == "HTTP_503"
    assert history[1].revision_count == 3


def test_incomplete_attempt_status(store: GridStore) -> None:
    store.save(_fetch(_market_body(demand=_day_rows(gaps=(100, 101)))))
    history = store.history(REGION, DAY)
    assert history[0].status == "INCOMPLETE"
    assert history[0].revision_count == 3


def test_revision_immutable(store: GridStore) -> None:
    revisions = _save_market(store)
    rid = revisions[(Metric.DEMAND, "")]
    with (
        store.engine.begin() as conn,
        pytest.raises(sa.exc.DBAPIError, match="immutable grid record"),
    ):
        conn.execute(
            sa.text("UPDATE grid_revision SET valid_count=0 WHERE id=:id"),
            {"id": rid},
        )


def test_consistent_revision_read(store: GridStore) -> None:
    revisions = _save_market(store)
    rid = revisions[(Metric.DEMAND, "")]
    _save_market(
        store, _market_body(demand=_day_rows(9999.9)), at=AT + timedelta(hours=1)
    )
    pinned = store.revision(rid)
    assert pinned.slots[0].value == Decimal("5000")  # unchanged by correction
    assert pinned.metric is Metric.DEMAND and pinned.series == ""


def test_coverage_range(store: GridStore) -> None:
    _save_market(store)
    cov = store.coverage_range(REGION, Metric.DEMAND, "", DAY, DAY + timedelta(days=1))
    assert DAY in cov and cov[DAY].valid == 288
    with pytest.raises(ValueError, match="1-31 days"):
        store.coverage_range(REGION, Metric.DEMAND, "", DAY, DAY + timedelta(days=40))


def test_batch_roundtrip_preserves_exact_decimals(store: GridStore) -> None:
    # Raw long-decimal literal in the JSON text — parse_float=Decimal keeps
    # every digit, and storage must return it unchanged.
    body = _market_body().replace("5000.0", "326.50009000000000001", 1)
    _save_market(store, body)
    batch = store.batch(REGION, Metric.DEMAND, "", DAY)
    assert batch is not None
    assert batch.slots[0].value == Decimal("326.50009000000000001")


def test_series_keys(store: GridStore) -> None:
    _save_market(store)
    keys = store.series_keys(REGION, DAY)
    assert (Metric.DEMAND, "") in keys and len(keys) == 3
