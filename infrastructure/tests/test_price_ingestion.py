"""Ports the Java ``PriceIngestionTest`` — OE parsing, immutable revision
persistence, freshness fencing, resumable backfill and bounded HTTP retries,
against real PostgreSQL (throwaway ``nemlab_test_*`` database per test).
"""

import contextlib
import json
import threading
import urllib.parse
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import sqlalchemy as sa
from db_fixture import REPO_ROOT, apply_schema

from nemlab_core.prices import NEM_OFFSET, Region
from nemlab_infrastructure.prices import (
    Fetch,
    Kind,
    OePriceSource,
    PriceBackfill,
    PriceBatch,
    PriceStore,
    Slot,
    hash,
)
from nemlab_infrastructure.prices.source import Failure, parse

DAY = date(2023, 9, 11)
AT = datetime(2026, 9, 17, tzinfo=UTC)


def CLOCK() -> datetime:
    return AT


REGION = Region.NSW1

BODY = (
    REPO_ROOT / "docs/project/evidence/oe-validation/historical-price-response.json"
).read_text()


def sample() -> Fetch:
    return parse(REGION, DAY, BODY, AT)


def changed(base: Fetch, slot: int, value: Slot, at: datetime) -> Fetch:
    slots = list(base.batch.slots)
    slots[slot] = value
    return Fetch(
        PriceBatch(base.batch.region, base.batch.day, tuple(slots)),
        at,
        hash("changed" + repr(value)),
        "test-1",
    )


@pytest.fixture
def store(scratch_db: sa.Engine) -> PriceStore:
    apply_schema(scratch_db)
    return PriceStore(scratch_db)


def _scalar(store: PriceStore, sql: str, **params: object) -> object:
    with store.engine.connect() as conn:
        return conn.execute(sa.text(sql), params).scalar()


def test_content_hash_matches_java_fixtures() -> None:
    """Frozen parity fixture pins the exact PriceBatch.contentHash values."""
    fixtures = json.loads(
        (
            REPO_ROOT
            / "docs/project/evidence/python-rebuild/fixtures/parity-fixtures.json"
        ).read_text()
    )
    for entry in fixtures["priceDays"]:
        lines = (
            (
                REPO_ROOT
                / f"reference/java/core/src/test/resources/prices/{entry['file']}"
            )
            .read_text()
            .splitlines()
        )
        slots = tuple(
            Slot(Kind.VALUE, Decimal(line.split(",")[1])) for line in lines[1:]
        )
        batch = PriceBatch(
            Region[entry["region"]],
            date.fromisoformat(entry["day"]),
            slots,
        )
        assert batch.content_hash() == entry["contentHash"], entry["day"]
        assert batch.count(Kind.VALUE) == entry["valid"]
        assert batch.count(Kind.MISSING) == entry["missing"]
        assert batch.count(Kind.SOURCE_NULL) == entry["sourceNull"]


def test_fixture_boundary_and_exact_prices() -> None:
    batch = sample().batch
    assert batch.complete()
    assert len(batch.slots) == 288
    prices = batch.to_price_day()
    assert prices.intervals[0].start == datetime(2023, 9, 11, tzinfo=NEM_OFFSET)
    assert prices.intervals[-1].end == datetime(2023, 9, 12, tzinfo=NEM_OFFSET)
    assert sum(1 for s in batch.slots if s.price is not None and s.price < 0) == 6
    assert sum(1 for s in batch.slots if s.price is not None and s.price == 0) == 2


def test_imports_idempotent_and_snapshots_survive_corrections(
    store: PriceStore,
) -> None:
    first = sample()
    revision = store.save(first)
    snapshot = store.snapshot(revision)
    assert store.save(first) == revision
    assert _scalar(store, "SELECT count(*) FROM price_revision") == 1
    correction = changed(
        first, 0, Slot(Kind.VALUE, Decimal("123.456789")), AT + timedelta(seconds=1)
    )
    second = store.save(correction)
    assert second != revision
    coverage = store.coverage(REGION, DAY)
    assert coverage is not None and coverage.revision == second
    assert store.snapshot_prices(snapshot) == first.batch.to_price_day()
    assert store.revision(second).slots[0].price == Decimal("123.456789")
    assert len(store.history(REGION, DAY)) == 3
    assert all(a.response_hash for a in store.history(REGION, DAY))
    with pytest.raises(sa.exc.DatabaseError), store.engine.begin() as conn:
        conn.execute(
            sa.text(
                "UPDATE price_revision SET valid_count=287, missing_count=1"
                " WHERE id=:id"
            ),
            {"id": revision},
        )
    with pytest.raises(sa.exc.DatabaseError), store.engine.begin() as conn:
        conn.execute(
            sa.text("DELETE FROM price_snapshot WHERE id=:id"),
            {"id": snapshot},
        )


def test_older_fetch_cannot_overwrite_and_revert_reuses_revision(
    store: PriceStore,
) -> None:
    original = sample()
    a = store.save(original)
    changed_fetch = changed(
        original, 0, Slot(Kind.VALUE, Decimal(0)), AT + timedelta(seconds=10)
    )
    b = store.save(changed_fetch)
    store.save(original)  # older retrieved_at loses
    coverage = store.coverage(REGION, DAY)
    assert coverage is not None and coverage.revision == b
    store.save(
        Fetch(
            original.batch,
            AT + timedelta(seconds=20),
            original.response_hash,
            original.source_version,
        )
    )
    coverage = store.coverage(REGION, DAY)
    assert coverage is not None and coverage.revision == a
    assert _scalar(store, "SELECT count(*) FROM price_revision") == 2


def test_missing_null_and_zero_stay_distinct_and_cannot_snapshot(
    store: PriceStore,
) -> None:
    incomplete = changed(sample(), 0, Slot(Kind.MISSING, None), AT)
    incomplete = changed(incomplete, 1, Slot(Kind.SOURCE_NULL, None), AT)
    revision = store.save(incomplete)
    coverage = store.coverage(REGION, DAY)
    assert coverage is not None
    assert (coverage.valid, coverage.missing, coverage.source_null) == (286, 1, 1)
    with pytest.raises(ValueError):
        store.revision(revision).to_price_day()
    with pytest.raises(sa.exc.DatabaseError):
        store.snapshot(revision)
    assert store.coverage(REGION, DAY + timedelta(days=1)) is None


def test_crash_restart_resumes_from_persisted_next_day(store: PriceStore) -> None:
    id = store.create_backfill(REGION, DAY, DAY + timedelta(days=2), CLOCK)
    calls = 0

    def failing(region: Region, day: date) -> Fetch:
        nonlocal calls
        calls += 1
        if day == DAY + timedelta(days=1):
            raise OSError("secret response text must not persist")
        return sample()

    source = _FnSource(failing)
    runner = PriceBackfill(store, source, CLOCK)
    assert runner.step(id)
    assert not runner.step(id)
    task = store.backfill(id)
    assert task.next == DAY + timedelta(days=1)
    assert task.status == "PAUSED"
    assert task.diagnostic is not None and "secret" not in task.diagnostic
    resumed = PriceBackfill(
        PriceStore(store.engine),
        _FnSource(
            lambda region, day: Fetch(
                PriceBatch(region, day, sample().batch.slots),
                AT,
                hash("day2"),
                "test-1",
            )
        ),
        CLOCK,
    )
    assert resumed.step(id)
    assert not resumed.step(id)
    assert store.backfill(id).status == "COMPLETE"
    assert _scalar(store, "SELECT count(*) FROM price_revision") == 2


def test_incomplete_day_pauses_without_advancing(store: PriceStore) -> None:
    id = store.create_backfill(REGION, DAY, DAY + timedelta(days=1), CLOCK)
    fetch = changed(sample(), 0, Slot(Kind.MISSING, None), AT)
    assert not PriceBackfill(store, _FnSource(lambda r, d: fetch), CLOCK).step(id)
    assert store.backfill(id).next == DAY
    assert store.backfill(id).status == "PAUSED"
    repaired = Fetch(
        sample().batch,
        AT + timedelta(seconds=1),
        sample().response_hash,
        sample().source_version,
    )
    assert PriceBackfill(store, _FnSource(lambda r, d: repaired), CLOCK).step(id)
    assert store.backfill(id).status == "COMPLETE"


def test_data_and_checkpoint_rollback_together(store: PriceStore) -> None:
    id = store.create_backfill(REGION, DAY, DAY + timedelta(days=1), CLOCK)
    with store.engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE FUNCTION test_fail_checkpoint() RETURNS trigger"
            " LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'injected'; END $$"
        )
        conn.exec_driver_sql(
            "CREATE TRIGGER test_checkpoint BEFORE UPDATE ON price_backfill"
            " FOR EACH ROW EXECUTE FUNCTION test_fail_checkpoint()"
        )
    try:
        with pytest.raises(sa.exc.DatabaseError):
            store.commit_day(id, DAY, sample())
        assert _scalar(store, "SELECT count(*) FROM price_revision") == 0
        assert _scalar(store, "SELECT count(*) FROM price_import_attempt") == 0
        assert store.backfill(id).next == DAY
    finally:
        with store.engine.begin() as conn:
            conn.exec_driver_sql("DROP TRIGGER test_checkpoint ON price_backfill")
            conn.exec_driver_sql("DROP FUNCTION test_fail_checkpoint()")


def test_stale_checkpoint_and_unbounded_dates_rejected(store: PriceStore) -> None:
    id = store.create_backfill(REGION, DAY, DAY + timedelta(days=1), CLOCK)
    store.commit_day(id, DAY, sample())
    with pytest.raises(ValueError):
        store.commit_day(id, DAY, sample())
    with pytest.raises(ValueError):
        store.create_backfill(REGION, DAY, DAY + timedelta(days=32), CLOCK)
    with pytest.raises(ValueError):
        store.create_backfill(REGION, date(2021, 9, 30), date(2021, 10, 1), CLOCK)
    with pytest.raises(ValueError):
        store.create_backfill(REGION, date(2026, 9, 17), date(2026, 9, 18), CLOCK)


class _FnSource:
    def __init__(self, fn: Callable[[Region, date], Fetch]) -> None:
        self._fn = fn

    def fetch(self, region: Region, day: date) -> Fetch:
        return self._fn(region, day)


# -- OE parser and HTTP adapter ----------------------------------------------


def test_parser_rejects_bad_metadata_duplicates_and_malformed() -> None:
    with pytest.raises(ValueError):
        parse(Region.QLD1, DAY, BODY, AT)
    with pytest.raises(ValueError):
        parse(REGION, DAY, BODY.replace("$/MWh", "MW"), AT)
    root = json.loads(BODY)
    rows = root["data"][0]["results"][0]["data"]
    rows.append(rows[1])
    with pytest.raises(ValueError):
        parse(REGION, DAY, json.dumps(root), AT)


def test_parser_preserves_missing_and_explicit_null() -> None:
    root = json.loads(BODY)
    rows = root["data"][0]["results"][0]["data"]
    rows.pop(1)
    rows[1][1] = None
    parsed = parse(REGION, DAY, json.dumps(root), AT).batch
    assert parsed.slots[0].kind is Kind.MISSING
    assert parsed.slots[1].kind is Kind.SOURCE_NULL
    assert parsed.count(Kind.VALUE) == 286
    with pytest.raises(ValueError):
        parse(REGION, DAY, BODY.replace("00:05:00+10:00", "00:06:00+10:00"), AT)


@contextlib.contextmanager
def _http_server(
    handler: Callable[[BaseHTTPRequestHandler], None],
) -> Iterator[ThreadingHTTPServer]:
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            handler(self)

        def log_message(self, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


def _respond(
    handler: BaseHTTPRequestHandler,
    status: int,
    body: bytes,
    retry_after: str | None = None,
) -> None:
    handler.send_response(status)
    if retry_after:
        handler.send_header("Retry-After", retry_after)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    with contextlib.suppress(BrokenPipeError, ConnectionResetError):
        handler.wfile.write(body)


def test_http_adapter_bounds_retries_and_never_echoes_secret() -> None:
    requests = 0
    sleeps: list[int] = []
    queries: list[str] = []

    def handler(h: BaseHTTPRequestHandler) -> None:
        nonlocal requests
        requests += 1
        queries.append(urllib.parse.urlparse(h.path).query)
        if requests == 1:
            _respond(h, 429, b"do-not-log-response", retry_after="2")
        else:
            _respond(h, 200, BODY.encode())

    with _http_server(handler) as server:
        source = OePriceSource(
            "test-secret",
            endpoint=f"http://127.0.0.1:{server.server_port}/prices",
            clock=CLOCK,
            sleeper=sleeps.append,
        )
        assert source.fetch(REGION, DAY).batch.complete()
    assert requests == 2
    assert sleeps == [2000]
    assert "date_end=2023-09-12T00:05:00" in urllib.parse.unquote(queries[0])
    assert "test-secret" not in queries[0]


def test_http_errors_bounded_and_sanitised() -> None:
    for status, expected_calls in ((401, 1), (503, 3), (429, 3)):
        calls = 0

        def handler(h: BaseHTTPRequestHandler, status: int = status) -> None:
            nonlocal calls
            calls += 1
            _respond(h, status, b"secret-body")

        with _http_server(handler) as server:
            source = OePriceSource(
                "test-secret",
                endpoint=f"http://127.0.0.1:{server.server_port}/",
                clock=CLOCK,
                sleeper=lambda ms: None,
            )
            with pytest.raises(Failure) as ex:
                source.fetch(REGION, DAY)
            assert ex.value.code == f"HTTP_{status}"
            assert "secret" not in str(ex.value)
            assert calls == expected_calls


def test_oversized_response_cancelled_with_finite_retry_budget() -> None:
    calls = 0

    def handler(h: BaseHTTPRequestHandler) -> None:
        nonlocal calls
        calls += 1
        _respond(h, 200, b"x" * 2_000_100)

    with _http_server(handler) as server:
        source = OePriceSource(
            "test-secret",
            endpoint=f"http://127.0.0.1:{server.server_port}/",
            clock=CLOCK,
            sleeper=lambda ms: None,
        )
        with pytest.raises(Failure) as ex:
            source.fetch(REGION, DAY)
        assert ex.value.code == "TRANSPORT_RETRIES_EXHAUSTED"
        assert calls <= 3


def test_concurrent_imports_remain_idempotent(store: PriceStore) -> None:
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(4) as pool:
        revisions = set(pool.map(lambda _i: store.save(sample()), range(4)))
    assert len(revisions) == 1
    assert _scalar(store, "SELECT count(*) FROM price_import_attempt") == 4


def test_operator_status_includes_safe_failure_code(store: PriceStore) -> None:
    id = store.create_backfill(REGION, DAY, DAY + timedelta(days=1), CLOCK)

    def failing(r: Region, d: date) -> Fetch:
        raise Failure("HTTP_401")

    assert not PriceBackfill(store, _FnSource(failing), CLOCK).step(id)
    assert store.backfill(id).diagnostic == "HTTP_401"
    attempt = store.history(REGION, DAY)[0]
    assert attempt.diagnostic == "HTTP_401"
    assert attempt.status == "FAILED"
