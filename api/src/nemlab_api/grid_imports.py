"""Operator grid-import endpoints — bounded GridReplay window submissions.

Mounted only when ``nemlab.admin.enabled``; ``OperatorBearer`` authenticates
every ``/api/admin/**`` request before these routes run. No public visitor
surface exists for imports.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, FastAPI, Header, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict

from nemlab_api.errors import ApiError, envelope, instant
from nemlab_api.validation import IsoDate
from nemlab_core.prices import Region
from nemlab_infrastructure.grid.imports import (
    GridImportJob,
    GridImportJobs,
    JobEvent,
    QueueFull,
    RequestKeyConflict,
)

BASE = "/api/admin/v1/grid-imports"


class Submission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    region: Region
    startDay: IsoDate
    endExclusive: IsoDate


def _view(job: GridImportJob) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "region": job.region.name,
        "startDay": str(job.start),
        "endExclusive": str(job.end),
        "nextDay": str(job.next_day),
        "status": job.status.name,
        "attempts": job.attempts,
        "optionalFailures": job.optional_failures,
        "availableAt": instant(job.available_at),
        "diagnostic": job.diagnostic,
    }


def _event(event: JobEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "occurredAt": instant(event.occurred_at),
        "actor": event.actor,
        "action": event.action,
        "diagnostic": event.diagnostic,
    }


def _required(jobs: GridImportJobs, id: UUID) -> GridImportJob:
    job = jobs.find(id)
    if job is None:
        raise ApiError(404, "JOB_NOT_FOUND", "Grid import job not found")
    return job


def grid_imports_router(jobs: GridImportJobs) -> APIRouter:
    router = APIRouter()

    @router.post(BASE)
    def submit(
        request: Request,
        submission: Submission,
        idempotency_key: Annotated[str, Header()],
    ) -> Response:
        id = jobs.submit(
            idempotency_key,
            submission.region,
            submission.startDay,
            submission.endExclusive,
            request.state.actor,
        )
        return JSONResponse(
            _view(_required(jobs, id)),
            status_code=202,
            headers={"Location": f"{BASE}/{id}"},
        )

    @router.get(BASE)
    def recent(limit: int = 50) -> list[dict[str, Any]]:
        return [_view(job) for job in jobs.recent(limit)]

    @router.get(BASE + "/{id}")
    def status(id: UUID) -> dict[str, Any]:
        return _view(_required(jobs, id))

    @router.get(BASE + "/{id}/events")
    def events(id: UUID, after: int = 0, limit: int = 50) -> list[dict[str, Any]]:
        _required(jobs, id)
        return [_event(event) for event in jobs.events(id, after, limit)]

    @router.post(BASE + "/{id}/cancel")
    def cancel(request: Request, id: UUID) -> dict[str, Any]:
        _required(jobs, id)
        jobs.cancel(id, request.state.actor)
        return _view(_required(jobs, id))

    return router


def register_grid_errors(app: FastAPI) -> None:
    """Grid-import exception envelopes — same shape as refresh errors."""

    @app.exception_handler(RequestKeyConflict)
    async def _conflict(_request: Request, _error: RequestKeyConflict) -> Response:
        return envelope(
            "IDEMPOTENCY_CONFLICT",
            "Request key belongs to a different import window",
            409,
        )

    @app.exception_handler(QueueFull)
    async def _full(_request: Request, _error: QueueFull) -> Response:
        return envelope(
            "QUEUE_FULL",
            "Wait for existing grid imports to finish",
            429,
            **{"Retry-After": "30"},
        )
