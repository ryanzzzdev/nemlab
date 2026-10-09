"""Bounded read-only projections over stored simulations (NEM-117).

The catalogue lists scenario/job/result summaries without decoding result
payloads — SQL extracts only the scalars a table needs. Detail decodes one
request and one result at a time. Strategy membership comes from the recorded
request (`thresholds` configured or not; fixed and hindsight always run), so
non-terminal jobs filter honestly. Cursors are keyset positions bound to the
normalised scope fingerprint and a creation-time high-water mark so new
submissions cannot disrupt an in-progress traversal.
"""

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import text

from nemlab_core.comparison import SimulationComparison
from nemlab_core.prices import Region
from nemlab_infrastructure.prices.store import PriceStore
from nemlab_infrastructure.simulations import _read_request, _read_result

STATUSES = ("QUEUED", "RUNNING", "SUCCEEDED", "FAILED")
STRATEGIES = ("fixed", "threshold", "hindsight")
SORTS = ("newest", "oldest")
DEFAULT_LIMIT = 50
MAX_LIMIT = 100
MAX_SCOPE_DAYS = 31

_CURSOR = re.compile(r"^v1\.[A-Za-z0-9_=-]+$")


@dataclass(frozen=True)
class SimulationSummary:
    id: UUID
    status: str
    region: str
    day: date
    created_at: datetime
    finished_at: datetime | None
    capacity_mwh: Decimal
    charge_mw: Decimal
    discharge_mw: Decimal
    strategies: tuple[str, ...]
    attempts: int
    has_result: bool
    diagnostic: str | None


@dataclass(frozen=True)
class CataloguePage:
    rows: list[SimulationSummary]
    counts: dict[str, int]
    total: int
    next_cursor: str | None
    as_of: datetime


@dataclass(frozen=True)
class ScenarioDetail:
    """The recorded request exactly as submitted — never UI defaults."""

    request: dict[str, Any]
    versions: dict[str, Any]


@dataclass(frozen=True)
class ResultSummary:
    """Accounting + solver outcome only; interval arrays stay out."""

    accounting: dict[str, dict[str, float]]
    solver: dict[str, Any]
    created_at: datetime


@dataclass(frozen=True)
class ExecutionFacts:
    status: str
    attempts: int
    available_at: datetime
    diagnostic: str | None
    created_at: datetime
    finished_at: datetime | None


@dataclass(frozen=True)
class Provenance:
    pinned_revision: UUID
    current_revision: UUID | None
    comparison: str  # "matches" | "different" | "unavailable"
    checked_at: datetime


@dataclass(frozen=True)
class SimulationDetail:
    summary: SimulationSummary
    scenario: ScenarioDetail
    result: ResultSummary | None
    execution: ExecutionFacts
    provenance: Provenance


class InvalidCursor(ValueError):
    pass


class InvalidScope(ValueError):
    pass


def _day_bounds(start: date | None, end: date | None) -> tuple[date, date]:
    if start is None or end is None:
        raise InvalidScope("region, start and end are required")
    if end < start:
        raise InvalidScope("end must not precede start")
    if (end - start).days + 1 > MAX_SCOPE_DAYS:
        raise InvalidScope("scope exceeds 31 market days")
    return start, end


def _fingerprint(
    region: Region | None,
    start: date,
    end: date,
    status: str | None,
    strategy: str | None,
    sort: str,
) -> str:
    canonical = "|".join(
        (
            "" if region is None else region.name,
            str(start),
            str(end),
            status or "",
            strategy or "",
            sort,
        )
    )
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _encode_cursor(fingerprint: str, hwm: datetime, row: SimulationSummary) -> str:
    payload = {
        "v": 1,
        "q": fingerprint,
        "h": hwm.isoformat(),
        "k": [row.created_at.isoformat(), str(row.id)],
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return "v1." + base64.urlsafe_b64encode(raw).decode()


def _decode_cursor(raw: str) -> tuple[str, datetime, tuple[datetime, UUID]]:
    if not _CURSOR.fullmatch(raw):
        raise InvalidCursor("malformed cursor")
    try:
        payload = json.loads(base64.urlsafe_b64decode(raw[3:].encode()).decode())
        return (
            payload["q"],
            datetime.fromisoformat(payload["h"]),
            (datetime.fromisoformat(payload["k"][0]), UUID(payload["k"][1])),
        )
    except (ValueError, KeyError, TypeError, UnicodeDecodeError) as failure:
        raise InvalidCursor("malformed cursor") from failure


_FILTERS = """
  AND (CAST(:region AS text) IS NULL OR i.request->>'region' = :region)
  AND (CAST(:start AS date) IS NULL OR (i.request->>'day')::date >= :start)
  AND (CAST(:end AS date) IS NULL OR (i.request->>'day')::date <= :end)
  AND (CAST(:status AS text) IS NULL OR j.status = :status)
  AND (CAST(:strategy AS text) IS NULL OR :strategy IN ('fixed','hindsight')
       OR i.request->>'thresholds' IS NOT NULL)
"""

# Scope counts ignore the status filter — the strip shows "how much of each
# state exists in this selection" even while the table is filtered to one.
_COUNTS = """
SELECT j.status, count(*) FROM simulation_input i
JOIN simulation_job j ON j.id = i.id
WHERE true
  AND (CAST(:region AS text) IS NULL OR i.request->>'region' = :region)
  AND (CAST(:start AS date) IS NULL OR (i.request->>'day')::date >= :start)
  AND (CAST(:end AS date) IS NULL OR (i.request->>'day')::date <= :end)
  AND (CAST(:strategy AS text) IS NULL OR :strategy IN ('fixed','hindsight')
       OR i.request->>'thresholds' IS NOT NULL)
GROUP BY j.status
"""

_SELECT = """
SELECT i.id, j.status, i.request->>'region' AS region,
       (i.request->>'day')::date AS day, i.created_at,
       r.created_at AS finished_at,
       (i.request->'site'->>'capacityMWh')::numeric AS capacity_mwh,
       (i.request->'site'->>'chargeMW')::numeric AS charge_mw,
       (i.request->'site'->>'dischargeMW')::numeric AS discharge_mw,
       (i.request->>'thresholds' IS NOT NULL) AS has_threshold,
       j.attempts, j.available_at, j.diagnostic, j.created_at AS job_created,
       (r.id IS NOT NULL) AS has_result
FROM simulation_input i
JOIN simulation_job j ON j.id = i.id
LEFT JOIN simulation_result r ON r.id = i.id
WHERE true
"""


def _summary(row: sa.engine.Row[Any]) -> SimulationSummary:
    strategies: list[str] = ["fixed", "hindsight"]
    if row.has_threshold:
        strategies.insert(1, "threshold")
    return SimulationSummary(
        id=row.id,
        status=row.status,
        region=row.region,
        day=row.day,
        created_at=row.created_at,
        finished_at=row.finished_at,
        capacity_mwh=row.capacity_mwh,
        charge_mw=row.charge_mw,
        discharge_mw=row.discharge_mw,
        strategies=tuple(strategies),
        attempts=row.attempts,
        has_result=row.has_result,
        diagnostic=row.diagnostic,
    )


def _accounting_summary(
    comparison: SimulationComparison | None,
) -> dict[str, dict[str, float]] | None:
    if comparison is None:
        return None
    out: dict[str, dict[str, float]] = {}
    for name, acc in (
        ("fixed", comparison.fixed_accounting),
        (
            "threshold",
            None if comparison.threshold is None else comparison.threshold.accounting,
        ),
        ("hindsight", comparison.hindsight.accounting),
    ):
        if acc is None:
            continue
        out[name] = {
            "importedMWh": acc.imported_mwh,
            "exportedMWh": acc.exported_mwh,
            "chargingCost": acc.charging_cost,
            "revenue": acc.revenue,
            "fees": acc.fees,
            "degradation": acc.degradation,
            "margin": acc.margin,
            "lossesMWh": acc.losses_mwh,
        }
    return out or None


class SimulationCatalogue:
    def __init__(self, engine: sa.engine.Engine) -> None:
        self.engine = engine
        self.prices = PriceStore(engine)

    def page(
        self,
        *,
        region: Region | None = None,
        start: date | None = None,
        end: date | None = None,
        status: str | None = None,
        strategy: str | None = None,
        sort: str = "newest",
        limit: int = DEFAULT_LIMIT,
        cursor: str | None = None,
    ) -> CataloguePage:
        if sort not in SORTS:
            raise InvalidScope("sort must be newest or oldest")
        if status is not None and status not in STATUSES:
            raise InvalidScope("unknown status filter")
        if strategy is not None and strategy not in STRATEGIES:
            raise InvalidScope("unknown strategy filter")
        if not 1 <= limit <= MAX_LIMIT:
            raise InvalidScope(f"limit must be 1-{MAX_LIMIT}")
        start, end = _day_bounds(start, end)

        scope: dict[str, Any] = {
            "region": None if region is None else region.name,
            "start": start,
            "end": end,
            "status": status,
            "strategy": strategy,
        }
        fingerprint = _fingerprint(region, start, end, status, strategy, sort)
        now = datetime.now(UTC)

        sql = _SELECT + _FILTERS
        position: tuple[datetime, UUID] | None = None
        if cursor is not None:
            bound, hwm, position = _decode_cursor(cursor)
            if bound != fingerprint:
                raise InvalidCursor("cursor belongs to a different scope")
            newest = sort == "newest"
            sql += " AND i.created_at <= :hwm"
            sql += (
                " AND (i.created_at, i.id) < (:ck, :cid)"
                if newest
                else " AND (i.created_at, i.id) > (:ck, :cid)"
            )
            scope["hwm"] = hwm
            scope["ck"] = position[0]
            scope["cid"] = position[1]
        sql += (
            " ORDER BY i.created_at DESC, i.id DESC"
            if sort == "newest"
            else " ORDER BY i.created_at, i.id"
        )
        sql += " LIMIT :limit"
        scope["limit"] = limit + 1

        with self.engine.connect() as conn:
            rows = [_summary(row) for row in conn.execute(text(sql), scope)]
            count_rows = conn.execute(
                text(_COUNTS),
                {
                    "region": scope["region"],
                    "start": scope["start"],
                    "end": scope["end"],
                    "strategy": strategy,
                },
            ).all()

        next_cursor = None
        if len(rows) > limit:
            rows = rows[:limit]
            hwm = now if cursor is None else _decode_cursor(cursor)[1]
            next_cursor = _encode_cursor(fingerprint, hwm, rows[-1])

        counts = {status_name: 0 for status_name in STATUSES}
        for name, count in count_rows:
            counts[name] = count
        return CataloguePage(
            rows=rows,
            counts=counts,
            total=sum(counts.values()),
            next_cursor=next_cursor,
            as_of=now,
        )

    def detail(self, id: UUID) -> SimulationDetail | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT i.id, i.scenario_key, i.request::text,"
                    " i.revision_id, i.versions::text, i.created_at,"
                    " j.status, j.attempts, j.available_at, j.diagnostic,"
                    " j.created_at AS job_created,"
                    " r.result::text, r.created_at AS result_at"
                    " FROM simulation_input i"
                    " JOIN simulation_job j ON j.id = i.id"
                    " LEFT JOIN simulation_result r ON r.id = i.id"
                    " WHERE i.id = :id"
                ),
                {"id": id},
            ).first()
        if row is None:
            return None

        request_doc = json.loads(row.request, parse_float=Decimal, parse_int=Decimal)
        versions_doc = json.loads(row.versions)
        request = _read_request(request_doc)
        comparison = (
            None
            if row.result is None
            else _read_result(
                json.loads(row.result, parse_float=Decimal, parse_int=Decimal)
            )
        )

        strategies: list[str] = ["fixed", "hindsight"]
        if request.thresholds is not None:
            strategies.insert(1, "threshold")
        summary = SimulationSummary(
            id=row.id,
            status=row.status,
            region=request_doc["region"],
            day=date.fromisoformat(request_doc["day"]),
            created_at=row.created_at,
            finished_at=row.result_at,
            capacity_mwh=Decimal(str(request_doc["site"]["capacityMWh"])),
            charge_mw=Decimal(str(request_doc["site"]["chargeMW"])),
            discharge_mw=Decimal(str(request_doc["site"]["dischargeMW"])),
            strategies=tuple(strategies),
            attempts=row.attempts,
            has_result=row.result is not None,
            diagnostic=row.diagnostic,
        )

        result_summary = None
        if comparison is not None:
            h = comparison.hindsight
            result_summary = ResultSummary(
                accounting=_accounting_summary(comparison) or {},
                solver={
                    "status": h.status.name,
                    "objective": h.solver_objective,
                    "upperBound": h.upper_bound,
                    "absoluteGap": h.absolute_gap,
                },
                created_at=row.result_at,
            )

        assert request.region is not None and request.day is not None
        current = self.prices.coverage(request.region, request.day)
        current_revision = None if current is None else current.revision
        comparison_state = (
            "unavailable"
            if current_revision is None
            else "matches"
            if current_revision == row.revision_id
            else "different"
        )
        return SimulationDetail(
            summary=summary,
            scenario=ScenarioDetail(request=request_doc, versions=versions_doc),
            result=result_summary,
            execution=ExecutionFacts(
                status=row.status,
                attempts=row.attempts,
                available_at=row.available_at,
                diagnostic=row.diagnostic,
                created_at=row.job_created,
                finished_at=row.result_at,
            ),
            provenance=Provenance(
                pinned_revision=row.revision_id,
                current_revision=current_revision,
                comparison=comparison_state,
                checked_at=datetime.now(UTC),
            ),
        )
