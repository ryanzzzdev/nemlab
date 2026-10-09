"""Admin simulation-inspection endpoints — bounded read projections (NEM-119).

Mounted only when ``nemlab.admin.enabled``; ``AdminAccess`` enforces
``ops.read`` on every request, so owner and viewer sessions share the same
sanitised views while automation bearers and applicants are denied. Reads
are pure projections — they never trigger refresh, computation or
publication, and no submitter identity exists to expose.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import Response

from nemlab_api.errors import ApiError, instant
from nemlab_api.validation import IsoDate
from nemlab_core import decimal_text
from nemlab_core.prices import Region
from nemlab_infrastructure.simulation_catalogue import (
    InvalidCursor,
    InvalidScope,
    SimulationCatalogue,
    SimulationDetail,
    SimulationSummary,
)
from nemlab_infrastructure.simulations import _encode

BASE = "/api/admin/v1/simulations"


def _json(payload: Any, status: int = 200) -> Response:
    """Exact encoding — decimals stay plain numbers, no float rounding."""
    return Response(
        content=_encode(payload), media_type="application/json", status_code=status
    )


def _summary(row: SimulationSummary) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "status": row.status,
        "region": row.region,
        "day": str(row.day),
        "createdAt": instant(row.created_at),
        "finishedAt": None if row.finished_at is None else instant(row.finished_at),
        "capacityMWh": decimal_text.to_plain_string(row.capacity_mwh),
        "chargeMW": decimal_text.to_plain_string(row.charge_mw),
        "dischargeMW": decimal_text.to_plain_string(row.discharge_mw),
        "strategies": list(row.strategies),
        "attempts": row.attempts,
        "hasResult": row.has_result,
        "diagnostic": row.diagnostic,
    }


def _detail(detail: SimulationDetail) -> dict[str, Any]:
    e = detail.execution
    p = detail.provenance
    return {
        "simulation": _summary(detail.summary),
        "scenario": {
            "request": detail.scenario.request,
            "versions": detail.scenario.versions,
        },
        "result": (
            None
            if detail.result is None
            else {
                "accounting": detail.result.accounting,
                "solver": detail.result.solver,
                "createdAt": instant(detail.result.created_at),
            }
        ),
        "execution": {
            "status": e.status,
            "attempts": e.attempts,
            "availableAt": instant(e.available_at),
            "diagnostic": e.diagnostic,
            "createdAt": instant(e.created_at),
            "finishedAt": None if e.finished_at is None else instant(e.finished_at),
        },
        "lifecycle": {
            "recorded": detail.lifecycle.recorded,
            "events": [
                {
                    "kind": ev.kind,
                    "attempt": ev.attempt,
                    "diagnostic": ev.diagnostic,
                    "availableAt": (
                        None if ev.available_at is None else instant(ev.available_at)
                    ),
                    "createdAt": instant(ev.created_at),
                    "attemptMs": ev.attempt_ms,
                }
                for ev in detail.lifecycle.events
            ],
        },
        "provenance": {
            "pinnedRevision": str(p.pinned_revision),
            "currentRevision": (
                None if p.current_revision is None else str(p.current_revision)
            ),
            "comparison": p.comparison,
            "checkedAt": instant(p.checked_at),
        },
    }


def simulation_catalogue_router(catalogue: SimulationCatalogue) -> APIRouter:
    router = APIRouter()

    @router.get(BASE)
    def page(
        region: Region,
        startDay: IsoDate,
        endDay: IsoDate,
        status: str | None = None,
        strategy: str | None = None,
        sort: str = "newest",
        limit: int = 50,
        cursor: str | None = None,
    ) -> Response:
        try:
            page = catalogue.page(
                region=region,
                start=startDay,
                end=endDay,
                status=status,
                strategy=strategy,
                sort=sort,
                limit=limit,
                cursor=cursor,
            )
        except InvalidCursor as error:
            raise ApiError(400, "INVALID_CURSOR", str(error)) from None
        except InvalidScope as error:
            raise ApiError(400, "INVALID_SCOPE", str(error)) from None
        return _json(
            {
                "rows": [_summary(row) for row in page.rows],
                "counts": page.counts,
                "total": page.total,
                "nextCursor": page.next_cursor,
                "asOf": instant(page.as_of),
            }
        )

    @router.get(BASE + "/{id}")
    def detail(id: UUID) -> Response:
        found = catalogue.detail(id)
        if found is None:
            raise ApiError(404, "SIMULATION_NOT_FOUND", "Simulation not found")
        return _json(_detail(found))

    return router
