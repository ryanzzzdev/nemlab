"""Load-operation endpoints — resumable bounded owner dispatch (NEM-102).

Mounted only when ``nemlab.admin.enabled``; ``AdminAccess`` enforces
``ops.write`` on mutations and ``ops.read`` on state reads. Dispatch is
explicit per call (no worker-side scheduler): each POST submits at most
one <=31-day chunk; queue caps answer ``backpressured`` without moving
the operation. Pausing never cancels queued children and nothing here
publishes.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict

from nemlab_api.capabilities import actor_label
from nemlab_api.errors import ApiError, instant
from nemlab_api.validation import IsoDate
from nemlab_core.prices import Region
from nemlab_infrastructure.load_operations import (
    LoadChild,
    LoadConflict,
    LoadNotFound,
    LoadOperation,
    LoadOperations,
)

BASE = "/api/admin/v1/load-operations"


class Begin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    region: Region
    startDay: IsoDate
    endExclusive: IsoDate


def _view(op: LoadOperation, viewer: bool = False) -> dict[str, Any]:
    return {
        "id": str(op.id),
        "region": op.region.name,
        "startDay": str(op.start),
        "endExclusive": str(op.end),
        "status": op.status,
        "phase": op.phase,
        "nextDay": str(op.next_day),
        "actor": actor_label(op.actor) if viewer else op.actor,
        "createdAt": instant(op.created_at),
        "updatedAt": instant(op.updated_at),
    }


def _child(child: LoadChild, states: dict[UUID, dict[str, object]]) -> dict[str, Any]:
    return {
        "phase": child.phase,
        "requestKey": child.request_key,
        "startDay": str(child.start),
        "endExclusive": str(child.end),
        "submittedAt": instant(child.created_at),
        "jobs": [
            {"id": str(job_id), **states.get(job_id, {"status": "UNKNOWN"})}
            for job_id in child.job_ids
        ],
    }


def _conflict() -> ApiError:
    return ApiError(
        409,
        "OPERATION_CONFLICT",
        "Operation paused, dispatched or moved — refresh its state",
    )


def load_operations_router(operations: LoadOperations) -> APIRouter:
    router = APIRouter()

    @router.post(BASE)
    def begin(request: Request, body: Begin) -> Response:
        op = operations.begin(
            body.region,
            body.startDay,
            body.endExclusive,
            request.state.actor,
        )
        return JSONResponse(
            _view(op),
            status_code=201,
            headers={"Location": f"{BASE}/{op.id}"},
        )

    @router.get(BASE)
    def recent(request: Request, limit: int = 50) -> list[dict[str, Any]]:
        return [_view(op, request.state.viewer) for op in operations.recent(limit)]

    @router.get(BASE + "/{id}")
    def detail(request: Request, id: UUID) -> dict[str, Any]:
        op = operations.get(id)
        if op is None:
            raise ApiError(404, "OPERATION_NOT_FOUND", "Load operation not found")
        states = operations.job_states(id)
        return {
            **_view(op, request.state.viewer),
            "children": [_child(child, states) for child in operations.children(id)],
        }

    @router.post(BASE + "/{id}/dispatch")
    def dispatch(request: Request, id: UUID) -> dict[str, Any]:
        try:
            outcome = operations.dispatch(id, request.state.actor)
        except LoadNotFound:
            raise ApiError(
                404, "OPERATION_NOT_FOUND", "Load operation not found"
            ) from None
        except LoadConflict:
            raise _conflict() from None
        body: dict[str, Any] = {"outcome": outcome.kind}
        if outcome.child is not None:
            body["child"] = _child(outcome.child, {})
        return body

    @router.post(BASE + "/{id}/pause")
    def pause(request: Request, id: UUID) -> dict[str, Any]:
        try:
            op = operations.pause(id)
        except LoadNotFound:
            raise ApiError(
                404, "OPERATION_NOT_FOUND", "Load operation not found"
            ) from None
        except LoadConflict:
            raise _conflict() from None
        return _view(op)

    @router.post(BASE + "/{id}/resume")
    def resume(request: Request, id: UUID) -> dict[str, Any]:
        try:
            op = operations.resume(id)
        except LoadNotFound:
            raise ApiError(
                404, "OPERATION_NOT_FOUND", "Load operation not found"
            ) from None
        except LoadConflict:
            raise _conflict() from None
        return _view(op)

    return router
