"""Immutable simulation inputs, fenced jobs and saved results — ports Java
``ScenarioPreparation`` + ``SimulationJobs`` onto the V3 schema.

Short database transactions; computation always runs outside them. The stored
``request``/``versions``/``result`` JSON documents keep the Jackson field
shapes byte-compatible so Java-era rows read back unchanged.
"""

import json
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import text

from nemlab_core import decimal_text, hindsight
from nemlab_core.accounting import Accounting
from nemlab_core.comparison import SimulationComparison, ThresholdResult, validate
from nemlab_core.dispatch import Dispatch, Interval, Limit
from nemlab_core.fixed import FIXED_VERSION, MODEL_VERSION
from nemlab_core.hindsight import Limits, Outcome, Status
from nemlab_core.prices import PriceDay, Region
from nemlab_core.request import (
    REQUEST_VERSION,
    Costs,
    EfficiencyInput,
    Invalid,
    Normalised,
    SimulationRequest,
    Site,
    ThresholdInput,
    Windows,
)
from nemlab_core.threshold import Thresholds
from nemlab_infrastructure.prices.batch import hash
from nemlab_infrastructure.prices.store import PriceStore

QUEUE_LOCK = 735_040
MAX_PENDING_JOBS = 100
MAX_ATTEMPTS = 3
LEASE_SECONDS = 60
RETRY_SECONDS_PER_ATTEMPT = 5
EXECUTION_PROFILE = "ordered-comparison-v1"

_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,79}")


class StaleClaim(RuntimeError):
    pass


class QueueFull(RuntimeError):
    pass


class UnsupportedVersion(RuntimeError):
    pass


@dataclass(frozen=True)
class Versions:
    request: str
    model: str
    fixed: str
    hindsight: str
    solver: str
    execution_profile: str
    limits: Limits

    @classmethod
    def current(cls) -> "Versions":
        return cls(
            REQUEST_VERSION,
            MODEL_VERSION,
            FIXED_VERSION,
            hindsight.VERSION,
            hindsight.SOLVER,
            EXECUTION_PROFILE,
            Limits.standard(),
        )

    def canonical(self) -> str:
        return "\n".join(
            (
                self.request,
                self.model,
                self.fixed,
                self.hindsight,
                self.solver,
                self.execution_profile,
                str(self.limits.milliseconds),
                str(self.limits.iterations),
            )
        )


@dataclass(frozen=True)
class Prepared:
    key: str
    parameters: Normalised
    price_revision: UUID
    prices: PriceDay
    versions: Versions


def prepare(
    prices: PriceStore, request: SimulationRequest | None, today: date | None = None
) -> Prepared:
    """Read-only input capture — never rereads ``price_current``."""
    if request is None:
        raise Invalid("request", "REQUIRED")
    parameters = request.normalise(today)
    assert request.region is not None and request.day is not None
    coverage = prices.coverage(request.region, request.day)
    if coverage is None:
        raise Invalid("day", "PRICE_DAY_UNAVAILABLE")
    revision = prices.revision(coverage.revision)
    if not revision.complete():
        raise Invalid("day", "PRICE_DAY_INCOMPLETE")
    versions = Versions.current()
    key = hash(
        parameters.canonical()
        + "\n"
        + str(coverage.revision)
        + "\n"
        + versions.canonical()
    )
    return Prepared(
        key, parameters, coverage.revision, revision.to_price_day(), versions
    )


# -- JSON codec: Jackson record shapes, decimal-exact -------------------------


def _encode(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Decimal):
        return decimal_text.to_plain_string(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, dict):
        items = (json.dumps(k) + ":" + _encode(v) for k, v in value.items())
        return "{" + ",".join(items) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_encode(v) for v in value) + "]"
    raise TypeError(f"cannot encode {type(value)}")


def _d(value: Decimal | None) -> Decimal:
    assert value is not None
    return value


def _request_json(values: SimulationRequest) -> dict[str, Any]:
    """The normalised ``SimulationRequest`` record shape."""
    s = values.site
    e = values.efficiency
    c = values.costs
    w = values.windows
    t = values.thresholds
    assert s is not None and e is not None and c is not None and w is not None
    return {
        "region": values.region.name if values.region else None,
        "day": str(values.day),
        "site": {
            "capacityMWh": s.capacity_mwh,
            "minimumMWh": s.minimum_mwh,
            "maximumMWh": s.maximum_mwh,
            "initialMWh": s.initial_mwh,
            "chargeMW": s.charge_mw,
            "dischargeMW": s.discharge_mw,
            "importLimitMW": s.import_limit_mw,
            "exportLimitMW": s.export_limit_mw,
        },
        "efficiency": {
            "charge": e.charge,
            "discharge": e.discharge,
            "roundTrip": e.round_trip,
        },
        "costs": {
            "importFee": c.import_fee,
            "exportFee": c.export_fee,
            "degradationPerExportedMWh": c.degradation_per_exported_mwh,
        },
        "windows": {
            "chargeStart": w.charge_start,
            "chargeEnd": w.charge_end,
            "dischargeStart": w.discharge_start,
            "dischargeEnd": w.discharge_end,
        },
        "thresholds": (
            None
            if t is None
            else {
                "chargeBelow": t.charge_below,
                "dischargeAbove": t.discharge_above,
            }
        ),
    }


def _read_request(doc: dict[str, Any]) -> SimulationRequest:
    """Tolerates historical shapes: ``thresholds`` absent or null."""
    s = doc["site"]
    e = doc["efficiency"]
    c = doc["costs"]
    w = doc["windows"]
    t = doc.get("thresholds")
    return SimulationRequest(
        Region[doc["region"]],
        date.fromisoformat(doc["day"]),
        Site(
            s["capacityMWh"],
            s["minimumMWh"],
            s["maximumMWh"],
            s["initialMWh"],
            s["chargeMW"],
            s["dischargeMW"],
            s["importLimitMW"],
            s["exportLimitMW"],
        ),
        EfficiencyInput(e["charge"], e["discharge"], e.get("roundTrip")),
        Costs(c["importFee"], c["exportFee"], c["degradationPerExportedMWh"]),
        Windows(
            int(w["chargeStart"]),
            int(w["chargeEnd"]),
            int(w["dischargeStart"]),
            int(w["dischargeEnd"]),
        ),
        None if t is None else ThresholdInput(t["chargeBelow"], t["dischargeAbove"]),
    )


def _versions_json(versions: Versions) -> dict[str, Any]:
    return {
        "request": versions.request,
        "model": versions.model,
        "fixed": versions.fixed,
        "hindsight": versions.hindsight,
        "solver": versions.solver,
        "executionProfile": versions.execution_profile,
        "limits": {
            "milliseconds": versions.limits.milliseconds,
            "iterations": versions.limits.iterations,
        },
    }


def _read_versions(doc: dict[str, Any]) -> Versions:
    return Versions(
        doc["request"],
        doc["model"],
        doc["fixed"],
        doc["hindsight"],
        doc["solver"],
        doc["executionProfile"],
        Limits(doc["limits"]["milliseconds"], doc["limits"]["iterations"]),
    )


def _dispatch_json(dispatch: Dispatch) -> dict[str, Any]:
    return {
        "intervals": [
            {
                "importedMWh": i.imported_mwh,
                "exportedMWh": i.exported_mwh,
                "endingEnergyMWh": i.ending_energy_mwh,
            }
            for i in dispatch.intervals
        ],
        "limitingReason": dispatch.limiting_reason.name,
    }


def _read_dispatch(doc: dict[str, Any]) -> Dispatch:
    return Dispatch(
        tuple(
            Interval(i["importedMWh"], i["exportedMWh"], i["endingEnergyMWh"])
            for i in doc["intervals"]
        ),
        Limit[doc["limitingReason"]],
    )


def _accounting_json(a: Accounting) -> dict[str, Any]:
    return {
        "importedMWh": a.imported_mwh,
        "exportedMWh": a.exported_mwh,
        "chargingCost": a.charging_cost,
        "revenue": a.revenue,
        "fees": a.fees,
        "degradation": a.degradation,
        "margin": a.margin,
        "lossesMWh": a.losses_mwh,
    }


def _read_accounting(doc: dict[str, Any]) -> Accounting:
    return Accounting(
        doc["importedMWh"],
        doc["exportedMWh"],
        doc["chargingCost"],
        doc["revenue"],
        doc["fees"],
        doc["degradation"],
        doc["margin"],
        doc["lossesMWh"],
    )


def _decimal(value: float | int | str) -> Decimal:
    return Decimal(str(value))


def _result_json(result: SimulationComparison) -> dict[str, Any]:
    h = result.hindsight
    t = result.threshold
    return {
        "fixedDispatch": _dispatch_json(result.fixed_dispatch),
        "fixedAccounting": _accounting_json(result.fixed_accounting),
        "hindsight": {
            "status": h.status.name,
            "solverState": h.solver_state,
            "certificateState": h.certificate_state,
            "dispatch": None if h.dispatch is None else _dispatch_json(h.dispatch),
            "accounting": (
                None if h.accounting is None else _accounting_json(h.accounting)
            ),
            "solverObjective": h.solver_objective,
            "upperBound": h.upper_bound,
            "absoluteGap": h.absolute_gap,
            "elapsedNanos": h.elapsed_nanos,
            "limits": {
                "milliseconds": h.limits.milliseconds,
                "iterations": h.limits.iterations,
            },
            "diagnostic": h.diagnostic,
        },
        "threshold": (
            None
            if t is None
            else {
                "version": t.version,
                "thresholds": {
                    "chargeBelow": t.thresholds.charge_below,
                    "dischargeAbove": t.thresholds.discharge_above,
                },
                "dispatch": _dispatch_json(t.dispatch),
                "accounting": _accounting_json(t.accounting),
            }
        ),
    }


def _read_result(doc: dict[str, Any]) -> SimulationComparison:
    """Reads current and Java-era (two-strategy, threshold-absent) rows."""
    h = doc["hindsight"]
    t = doc.get("threshold")
    dispatch = h.get("dispatch")
    accounting = h.get("accounting")
    return SimulationComparison(
        _read_dispatch(doc["fixedDispatch"]),
        _read_accounting(doc["fixedAccounting"]),
        Outcome(
            Status[h["status"]],
            h["solverState"],
            h["certificateState"],
            None if dispatch is None else _read_dispatch(dispatch),
            None if accounting is None else _read_accounting(accounting),
            h["solverObjective"],
            h["upperBound"],
            h["absoluteGap"],
            h["elapsedNanos"],
            Limits(h["limits"]["milliseconds"], h["limits"]["iterations"]),
            h["diagnostic"],
        ),
        None
        if t is None
        else ThresholdResult(
            t["version"],
            Thresholds(
                _decimal(t["thresholds"]["chargeBelow"]),
                _decimal(t["thresholds"]["dischargeAbove"]),
            ),
            _read_dispatch(t["dispatch"]),
            _read_accounting(t["accounting"]),
        ),
    )


# -- jobs service ---------------------------------------------------------------


@dataclass(frozen=True)
class Job:
    id: UUID
    status: str
    attempts: int
    token: UUID | None
    lease_until: datetime | None
    diagnostic: str | None


@dataclass(frozen=True)
class Input:
    key: str
    request: SimulationRequest
    prices: PriceDay
    versions: Versions

    def parameters(self) -> Normalised:
        """Re-normalise the stored request — supported versions only."""
        if self.versions != Versions.current():
            raise UnsupportedVersion()
        parameters = self.request.normalise()
        if (
            self.prices.region is not self.request.region
            or self.prices.date != self.request.day
        ):
            raise ValueError("price day mismatch")
        return parameters


def _job(row: sa.engine.Row[Any]) -> Job:
    return Job(
        row.id,
        row.status,
        row.attempts,
        row.claim_token,
        row.lease_until,
        row.diagnostic,
    )


class SimulationJobs:
    def __init__(self, engine: sa.engine.Engine) -> None:
        self.engine = engine
        self.prices = PriceStore(engine)

    def submit(self, request: SimulationRequest) -> UUID:
        prepared = prepare(self.prices, request)
        with self.engine.begin() as conn:
            self._lock_queue(conn)
            existing = conn.execute(
                text("SELECT id FROM simulation_input WHERE scenario_key = :key"),
                {"key": prepared.key},
            ).first()
            if existing is not None:
                return UUID(str(existing.id))
            pending: int = conn.execute(
                text(
                    "SELECT count(*) FROM simulation_job"
                    " WHERE status IN ('QUEUED','RUNNING')"
                )
            ).scalar_one()
            if pending >= MAX_PENDING_JOBS:
                raise QueueFull()
            id = uuid.uuid4()
            conn.execute(
                text(
                    "INSERT INTO simulation_input"
                    " (id, scenario_key, revision_id, request, versions)"
                    " VALUES (:id, :key, :rev, CAST(:request AS jsonb),"
                    " CAST(:versions AS jsonb))"
                ),
                {
                    "id": id,
                    "key": prepared.key,
                    "rev": prepared.price_revision,
                    "request": _encode(_request_json(prepared.parameters.values)),
                    "versions": _encode(_versions_json(prepared.versions)),
                },
            )
            conn.execute(
                text("INSERT INTO simulation_job(id, status) VALUES (:id, 'QUEUED')"),
                {"id": id},
            )
            return id

    def claim(self) -> Job | None:
        """One simulation at a time; expired leases recycle first."""
        with self.engine.begin() as conn:
            self._lock_queue(conn)
            expired = conn.execute(
                text(
                    "SELECT * FROM simulation_job WHERE status = 'RUNNING'"
                    " AND lease_until <= clock_timestamp() FOR UPDATE"
                )
            ).all()
            for row in expired:
                self._retry(conn, _job(row), "LEASE_EXPIRED", True, True)
            running: int = conn.execute(
                text("SELECT count(*) FROM simulation_job WHERE status = 'RUNNING'")
            ).scalar_one()
            if running > 0:
                return None
            ready = conn.execute(
                text(
                    "SELECT * FROM simulation_job WHERE status = 'QUEUED'"
                    " AND available_at <= clock_timestamp()"
                    " ORDER BY available_at, created_at, id LIMIT 1 FOR UPDATE"
                )
            ).first()
            if ready is None:
                return None
            conn.execute(
                text(
                    "UPDATE simulation_job SET status = 'RUNNING',"
                    " attempts = attempts + 1, claim_token = :token,"
                    " lease_until = clock_timestamp() + interval '60 seconds'"
                    " WHERE id = :id"
                ),
                {"token": uuid.uuid4(), "id": ready.id},
            )
            return self._find(conn, ready.id)

    def find(self, id: UUID) -> Job | None:
        with self.engine.connect() as conn:
            return self._find(conn, id)

    def _find(self, conn: sa.Connection, id: UUID) -> Job | None:
        row = conn.execute(
            text("SELECT * FROM simulation_job WHERE id = :id"), {"id": id}
        ).first()
        return None if row is None else _job(row)

    def price_revision(self, id: UUID) -> UUID:
        with self.engine.connect() as conn:
            return conn.execute(
                text("SELECT revision_id FROM simulation_input WHERE id = :id"),
                {"id": id},
            ).scalar_one()

    _INPUT_COLUMNS = (
        "SELECT id, scenario_key, request::text, revision_id, versions::text"
        " FROM simulation_input"
    )

    def input(self, id: UUID) -> Input:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(self._INPUT_COLUMNS + " WHERE id = :id"), {"id": id}
            ).one()
        request = _read_request(
            json.loads(row.request, parse_float=Decimal, parse_int=Decimal)
        )
        return Input(
            row.scenario_key,
            request,
            self.prices.revision(row.revision_id).to_price_day(),
            _read_versions(json.loads(row.versions)),
        )

    def result(self, id: UUID) -> SimulationComparison | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT result::text FROM simulation_result WHERE id = :id"),
                {"id": id},
            ).first()
        return None if row is None else _read_result(json.loads(row.result))

    def complete(self, id: UUID, token: UUID, result: SimulationComparison) -> None:
        """Validate + publish atomically; only OPTIMAL becomes SUCCEEDED."""
        with self.engine.begin() as conn:
            self._require_live(conn, id, token)
            input = self._input(conn, id)
            validate(result, input.parameters(), input.prices, input.versions.limits)
            conn.execute(
                text(
                    "INSERT INTO simulation_result(id, result)"
                    " VALUES (:id, CAST(:result AS jsonb))"
                ),
                {"id": id, "result": _encode(_result_json(result))},
            )
            optimal = result.hindsight.status is hindsight.Status.OPTIMAL
            self._finish(
                conn,
                id,
                token,
                "SUCCEEDED" if optimal else "FAILED",
                None if optimal else f"SOLVER_{result.hindsight.status.name}",
            )

    def fail(self, id: UUID, token: UUID, code: str, retryable: bool) -> None:
        if not _CODE.fullmatch(code):
            raise ValueError("safe diagnostic code required")
        with self.engine.begin() as conn:
            self._retry(
                conn, self._require_live(conn, id, token), code, retryable, False
            )

    # -- internals ------------------------------------------------------------

    def _input(self, conn: sa.Connection, id: UUID) -> Input:
        row = conn.execute(
            text(self._INPUT_COLUMNS + " WHERE id = :id"), {"id": id}
        ).one()
        request = _read_request(
            json.loads(row.request, parse_float=Decimal, parse_int=Decimal)
        )
        return Input(
            row.scenario_key,
            request,
            self.prices.revision(row.revision_id).to_price_day(),
            _read_versions(json.loads(row.versions)),
        )

    def _require_live(self, conn: sa.Connection, id: UUID, token: UUID | None) -> Job:
        if token is None:
            raise StaleClaim()
        row = conn.execute(
            text(
                "SELECT * FROM simulation_job WHERE id = :id"
                " AND status = 'RUNNING' AND claim_token = :token"
                " AND lease_until > clock_timestamp() FOR UPDATE"
            ),
            {"id": id, "token": token},
        ).first()
        if row is None:
            raise StaleClaim()
        return _job(row)

    def _retry(
        self,
        conn: sa.Connection,
        job: Job,
        code: str,
        retryable: bool,
        expired: bool,
    ) -> None:
        state = "QUEUED" if retryable and job.attempts < MAX_ATTEMPTS else "FAILED"
        changed = conn.execute(
            text(
                "UPDATE simulation_job SET status = :state, diagnostic = :code,"
                " claim_token = NULL, lease_until = NULL,"
                " available_at = clock_timestamp()"
                " + make_interval(secs => :delay)"
                " WHERE id = :id AND claim_token = :token"
                " AND (:expired OR lease_until > clock_timestamp())"
            ),
            {
                "state": state,
                "code": code,
                "delay": RETRY_SECONDS_PER_ATTEMPT * job.attempts,
                "id": job.id,
                "token": job.token,
                "expired": expired,
            },
        ).rowcount
        if changed != 1:
            raise StaleClaim()

    def _finish(
        self,
        conn: sa.Connection,
        id: UUID,
        token: UUID,
        state: str,
        diagnostic: str | None,
    ) -> None:
        changed = conn.execute(
            text(
                "UPDATE simulation_job SET status = :state, diagnostic = :diag,"
                " claim_token = NULL, lease_until = NULL"
                " WHERE id = :id AND status = 'RUNNING' AND claim_token = :token"
                " AND lease_until > clock_timestamp()"
            ),
            {"state": state, "diag": diagnostic, "id": id, "token": token},
        ).rowcount
        if changed != 1:
            raise StaleClaim()

    def _lock_queue(self, conn: sa.Connection) -> None:
        conn.execute(text("SELECT pg_advisory_xact_lock(:lock)"), {"lock": QUEUE_LOCK})
