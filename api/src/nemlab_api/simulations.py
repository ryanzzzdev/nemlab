"""``/api/v1/simulations`` — ports the Java ``SimulationController`` +
``SimulationJson`` strict decimal-string boundary.

Submit is deduplicated on the scenario key; days without stored prices trigger
a bounded visitor refresh and return ``PRICE_REFRESH_PENDING`` rather than a
dead end. Results expose only the public projection — claim tokens, lease
fields and solver internals stay private.
"""

import json
import re
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.responses import JSONResponse

from nemlab_api.errors import instant, simulation_error
from nemlab_core import decimal_text
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
from nemlab_infrastructure.jobs import RefreshJobService
from nemlab_infrastructure.simulations import Job, SimulationJobs

NO_STORE = {"Cache-Control": "no-store"}
MAX_BODY = 16_384
_ID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_DECIMAL = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?")

# Diagnostics the public status projection may expose verbatim.
_PUBLIC_FAILURES = {
    "LEASE_EXPIRED",
    "WORKER_STOPPED",
    "SIMULATION_DEADLINE_EXCEEDED",
    "SIMULATION_PROCESS_FAILED",
    "INVALID_CHILD_RESULT",
    "UNSUPPORTED_SIMULATION_VERSION",
    "SOLVER_FEASIBLE_NOT_PROVEN",
    "SOLVER_NO_SOLUTION",
    "SOLVER_INFEASIBLE",
    "SOLVER_FAILED_VALIDATION",
    "SOLVER_ERROR",
}


class SimulationRouteError(Exception):
    """Controller-scoped signal exceptions (Java's nested classes)."""

    def __init__(
        self, status: int, code: str, message: str, field: str, reason: str
    ) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.message = message
        self.field = field
        self.reason = reason


# -- strict request parsing (``SimulationJson``) ------------------------------------


def _invalid(field: str, code: str) -> Invalid:
    return Invalid(field, code)


def _malformed() -> SimulationRouteError:
    return SimulationRouteError(
        400,
        "INVALID_REQUEST",
        "Use the documented JSON fields and identifiers",
        "request",
        "INVALID_FORMAT",
    )


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """``StreamReadFeature.STRICT_DUPLICATE_DETECTION``."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _malformed()
        result[key] = value
    return result


def _object(value: Any, path: str, *allowed: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _invalid(path, "REQUIRED_OBJECT")
    for field in value:
        if field not in allowed:
            raise _invalid(path, "UNKNOWN_FIELD")
    return value


def _string(value: Any, field: str) -> str:
    if value is None:
        raise _invalid(field, "REQUIRED")
    if not isinstance(value, str):
        raise _invalid(field, "STRING_REQUIRED")
    return value


def _decimal(obj: dict[str, Any], path: str, field: str) -> Decimal:
    value = _string(obj.get(field), f"{path}.{field}")
    if len(value) > 80 or not _DECIMAL.fullmatch(value):
        raise _invalid(f"{path}.{field}", "INVALID_DECIMAL")
    return Decimal(value)


def _optional_leg(obj: dict[str, Any], field: str) -> Decimal | None:
    return _decimal(obj, "efficiency", field) if field in obj else None


def _minute(obj: dict[str, Any], field: str) -> int:
    value = obj.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise _invalid(f"windows.{field}", "INTEGER_REQUIRED")
    return value


def parse_request(body: bytes) -> SimulationRequest:
    """Strict decimal-string boundary; core owns physical validation."""
    try:
        root = json.loads(body, object_pairs_hook=_no_duplicates)
    except SimulationRouteError:
        raise
    except Exception:
        raise _malformed() from None
    root = _object(
        root,
        "request",
        "region",
        "day",
        "site",
        "efficiency",
        "costs",
        "windows",
        "thresholds",
    )
    site = _object(
        root.get("site"),
        "site",
        "capacityMWh",
        "minimumMWh",
        "maximumMWh",
        "initialMWh",
        "chargeMW",
        "dischargeMW",
        "importLimitMW",
        "exportLimitMW",
    )
    efficiency = _object(
        root.get("efficiency"), "efficiency", "charge", "discharge", "roundTrip"
    )
    costs = _object(
        root.get("costs"),
        "costs",
        "importFee",
        "exportFee",
        "degradationPerExportedMWh",
    )
    windows = _object(
        root.get("windows"),
        "windows",
        "chargeStart",
        "chargeEnd",
        "dischargeStart",
        "dischargeEnd",
    )
    thresholds = root.get("thresholds")
    threshold_input = None
    if thresholds is not None:
        thresholds = _object(thresholds, "thresholds", "chargeBelow", "dischargeAbove")
        threshold_input = ThresholdInput(
            _decimal(thresholds, "thresholds", "chargeBelow"),
            _decimal(thresholds, "thresholds", "dischargeAbove"),
        )
    try:
        region = Region[_string(root.get("region"), "region")]
    except KeyError:
        raise _invalid("region", "INVALID_VALUE") from None
    day_text = _string(root.get("day"), "day")
    try:
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", day_text):
            raise ValueError
        day = date.fromisoformat(day_text)
    except ValueError:
        raise _invalid("day", "INVALID_VALUE") from None
    return SimulationRequest(
        region,
        day,
        Site(
            *(
                _decimal(site, "site", field)
                for field in (
                    "capacityMWh",
                    "minimumMWh",
                    "maximumMWh",
                    "initialMWh",
                    "chargeMW",
                    "dischargeMW",
                    "importLimitMW",
                    "exportLimitMW",
                )
            )
        ),
        EfficiencyInput(
            _optional_leg(efficiency, "charge"),
            _optional_leg(efficiency, "discharge"),
            _optional_leg(efficiency, "roundTrip"),
        ),
        Costs(
            _decimal(costs, "costs", "importFee"),
            _decimal(costs, "costs", "exportFee"),
            _decimal(costs, "costs", "degradationPerExportedMWh"),
        ),
        Windows(
            _minute(windows, "chargeStart"),
            _minute(windows, "chargeEnd"),
            _minute(windows, "dischargeStart"),
            _minute(windows, "dischargeEnd"),
        ),
        threshold_input,
    )


# -- router -------------------------------------------------------------------------


def _path(id: UUID) -> str:
    return f"/api/v1/simulations/{id}"


def _view(job: Job) -> dict[str, Any]:
    failure = job.diagnostic
    if failure is not None and failure not in _PUBLIC_FAILURES:
        failure = "SIMULATION_FAILED"
    return {
        "id": str(job.id),
        "status": job.status,
        "attempts": job.attempts,
        "failureCode": failure,
        "statusUrl": _path(job.id),
        "resultUrl": _path(job.id) + "/result",
    }


def _identifier(value: str) -> UUID:
    if not _ID.fullmatch(value):
        raise _invalid("id", "INVALID_VALUE")
    return UUID(value)


def _plain(value: Decimal | None) -> str | None:
    return None if value is None else decimal_text.to_plain_string(value)


def _inputs(request: SimulationRequest) -> dict[str, Any]:
    s = request.site
    e = request.efficiency
    c = request.costs
    w = request.windows
    assert s is not None and e is not None and c is not None and w is not None
    inputs: dict[str, Any] = {
        "region": request.region.name if request.region else None,
        "day": str(request.day),
        "site": {
            name: _plain(getattr(s, field))
            for name, field in (
                ("capacityMWh", "capacity_mwh"),
                ("minimumMWh", "minimum_mwh"),
                ("maximumMWh", "maximum_mwh"),
                ("initialMWh", "initial_mwh"),
                ("chargeMW", "charge_mw"),
                ("dischargeMW", "discharge_mw"),
                ("importLimitMW", "import_limit_mw"),
                ("exportLimitMW", "export_limit_mw"),
            )
        },
        "efficiency": {
            "charge": _plain(e.charge),
            "discharge": _plain(e.discharge),
        },
        "costs": {
            "importFee": _plain(c.import_fee),
            "exportFee": _plain(c.export_fee),
            "degradationPerExportedMWh": _plain(c.degradation_per_exported_mwh),
        },
        "windows": {
            "chargeStart": w.charge_start,
            "chargeEnd": w.charge_end,
            "dischargeStart": w.discharge_start,
            "dischargeEnd": w.discharge_end,
        },
    }
    t = request.thresholds
    if t is not None:
        inputs["thresholds"] = {
            "chargeBelow": _plain(t.charge_below),
            "dischargeAbove": _plain(t.discharge_above),
        }
    return inputs


def _dispatch_view(dispatch: Any) -> dict[str, Any]:
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


def _accounting_view(accounting: Any) -> dict[str, Any]:
    return {
        "importedMWh": accounting.imported_mwh,
        "exportedMWh": accounting.exported_mwh,
        "chargingCost": accounting.charging_cost,
        "revenue": accounting.revenue,
        "fees": accounting.fees,
        "degradation": accounting.degradation,
        "margin": accounting.margin,
        "lossesMWh": accounting.losses_mwh,
    }


def simulations_router(jobs: SimulationJobs, refreshes: RefreshJobService) -> APIRouter:
    router = APIRouter()

    @router.post("/api/v1/simulations")
    async def submit(request: Request) -> Response:
        content_type = request.headers.get("content-type")
        media = (
            "" if content_type is None else content_type.split(";")[0].strip().lower()
        )
        if not (
            media == "application/json"
            or (media.startswith("application/") and media.endswith("+json"))
        ):
            raise SimulationRouteError(
                415,
                "UNSUPPORTED_CONTENT_TYPE",
                "Send application/json",
                "request",
                "CONTENT_TYPE",
            )
        body = await request.body()
        if len(body) > MAX_BODY:
            raise SimulationRouteError(
                413,
                "REQUEST_TOO_LARGE",
                "JSON body must not exceed 16384 bytes",
                "request",
                "TOO_LARGE",
            )
        parsed = parse_request(body)
        try:
            id = jobs.submit(parsed)
        except Invalid as invalid:
            if invalid.code not in (
                "PRICE_DAY_UNAVAILABLE",
                "PRICE_DAY_INCOMPLETE",
            ):
                raise
            # Coverage failure: the day itself is valid but unfetched; eligible
            # days trigger a bounded, deduplicated visitor refresh.
            assert parsed.region is not None and parsed.day is not None
            refreshes.submit_visitor(parsed.region, parsed.day)
            raise SimulationRouteError(
                409,
                "PRICE_REFRESH_PENDING",
                "Stored prices for this day are being fetched",
                "day",
                "PRICE_REFRESH_PENDING",
            ) from invalid
        job = jobs.find(id)
        if job is None:
            raise SimulationRouteError(
                404, "SIMULATION_NOT_FOUND", "Simulation not found", "id", "NOT_FOUND"
            )
        pending = job.status in ("QUEUED", "RUNNING")
        headers = {**NO_STORE, "Location": _path(job.id)}
        if pending:
            headers["Retry-After"] = "2"
        return JSONResponse(
            _view(job), status_code=202 if pending else 200, headers=headers
        )

    @router.get("/api/v1/simulations/{id}")
    def status(id: str) -> Response:
        job = jobs.find(_identifier(id))
        if job is None:
            raise SimulationRouteError(
                404, "SIMULATION_NOT_FOUND", "Simulation not found", "id", "NOT_FOUND"
            )
        return JSONResponse(_view(job), headers=NO_STORE)

    @router.get("/api/v1/simulations/{id}/result")
    def result(id: str) -> Response:
        identifier = _identifier(id)
        job = jobs.find(identifier)
        if job is None:
            raise SimulationRouteError(
                404, "SIMULATION_NOT_FOUND", "Simulation not found", "id", "NOT_FOUND"
            )
        if job.status == "FAILED":
            raise SimulationRouteError(
                409,
                "SIMULATION_FAILED",
                "No proven comparison is available; inspect job status",
                "id",
                "FAILED",
            )
        result = jobs.result(identifier) if job.status == "SUCCEEDED" else None
        if result is None:
            raise SimulationRouteError(
                409,
                "RESULT_NOT_READY",
                "Poll simulation status for completion",
                "id",
                "NOT_READY",
            )
        input = jobs.input(identifier)
        h = result.hindsight
        if h.status.name != "OPTIMAL" or h.dispatch is None or h.accounting is None:
            raise SimulationRouteError(
                409,
                "SIMULATION_FAILED",
                "No proven comparison is available; inspect job status",
                "id",
                "FAILED",
            )
        t = result.threshold
        v = input.versions
        body = {
            "id": str(identifier),
            "inputs": _inputs(input.request),
            "priceRevision": str(jobs.price_revision(identifier)),
            "versions": {
                "request": v.request,
                "model": v.model,
                "fixed": v.fixed,
                "hindsight": v.hindsight,
                "solver": v.solver,
                "executionProfile": v.execution_profile,
                "limits": {
                    "milliseconds": v.limits.milliseconds,
                    "iterations": v.limits.iterations,
                },
            },
            "marketOffset": "+10:00",
            "intervalSeconds": 300,
            "intervalLabel": "END",
            "units": {
                "energy": "MWh",
                "power": "MW",
                "money": "AUD",
                "price": "AUD/MWh",
            },
            "prices": [
                {
                    "start": instant(i.start),
                    "end": instant(i.end),
                    "price": _plain(i.price),
                }
                for i in input.prices.intervals
            ],
            "fixed": {
                "dispatch": _dispatch_view(result.fixed_dispatch),
                "accounting": _accounting_view(result.fixed_accounting),
            },
            "hindsight": {
                "dispatch": _dispatch_view(h.dispatch),
                "accounting": _accounting_view(h.accounting),
            },
            "threshold": (
                None
                if t is None
                else {
                    "version": t.version,
                    "thresholds": {
                        "chargeBelow": _plain(t.thresholds.charge_below),
                        "dischargeAbove": _plain(t.thresholds.discharge_above),
                    },
                    "dispatch": _dispatch_view(t.dispatch),
                    "accounting": _accounting_view(t.accounting),
                }
            ),
            "solver": {
                "status": h.status.name,
                "objective": h.solver_objective,
                "upperBound": h.upper_bound,
                "absoluteGap": h.absolute_gap,
            },
        }
        return JSONResponse(body, headers=NO_STORE)

    return router


# -- error advice (``SimulationErrors``) ----------------------------------------------


def register_simulation_errors(app: FastAPI) -> None:
    """Simulation-scoped handlers; shared exceptions (storage, refresh queue
    saturation) branch on path inside ``errors.py``."""
    from nemlab_infrastructure.jobs import (
        RefreshAttemptsExhausted,
        VisitorLimited,
    )
    from nemlab_infrastructure.simulations import QueueFull as SimulationQueueFull

    @app.exception_handler(SimulationRouteError)
    async def _route(_request: Request, error: SimulationRouteError) -> Response:
        headers = {"Retry-After": "30"} if error.code == "PRICE_REFRESH_PENDING" else {}
        return simulation_error(
            error.status,
            error.code,
            error.message,
            error.field,
            error.reason,
            **headers,
        )

    @app.exception_handler(Invalid)
    async def _invalid_request(_request: Request, error: Invalid) -> Response:
        coverage = error.code in ("PRICE_DAY_UNAVAILABLE", "PRICE_DAY_INCOMPLETE")
        return simulation_error(
            409 if coverage else 400,
            error.code if coverage else "INVALID_REQUEST",
            "Check scenario fields and complete stored price coverage",
            error.field,
            error.code,
        )

    @app.exception_handler(SimulationQueueFull)
    async def _full(_request: Request, _error: Exception) -> Response:
        return simulation_error(
            429,
            "QUEUE_FULL",
            "Wait for pending simulations to finish",
            "request",
            "QUEUE_FULL",
            **{"Retry-After": "5"},
        )

    @app.exception_handler(RefreshAttemptsExhausted)
    async def _exhausted(
        _request: Request, _error: RefreshAttemptsExhausted
    ) -> Response:
        return simulation_error(
            409,
            "PRICE_REFRESH_FAILED",
            "Stored prices could not be fetched for this day; try again later",
            "day",
            "PRICE_REFRESH_FAILED",
        )

    @app.exception_handler(VisitorLimited)
    async def _limited(_request: Request, _error: VisitorLimited) -> Response:
        return simulation_error(
            429,
            "VISITOR_REFRESH_LIMIT",
            "Too many price fetches are pending",
            "request",
            "VISITOR_REFRESH_LIMIT",
            **{"Retry-After": "60"},
        )
