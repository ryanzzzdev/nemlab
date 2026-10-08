"""Operator refresh endpoints — Java ``AdminRefreshController`` + ``AdminErrors``.

Mounted only when ``nemlab.admin.enabled``; the ``OperatorBearer`` middleware
authenticates every ``/api/admin/**`` request before these routes run, so the
actor here is always the server-derived ``operator:<name>`` — client-supplied
actor headers are never read.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict

from nemlab_api.errors import ApiError, instant
from nemlab_api.validation import IsoDate
from nemlab_core.prices import Region
from nemlab_infrastructure.jobs import JobEvent, RefreshJob, RefreshJobService

BASE = "/api/admin/v1/price-refreshes"


class DaySubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    region: Region
    day: IsoDate


class WindowSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    region: Region
    startDay: IsoDate
    endExclusive: IsoDate


Submission = DaySubmission | WindowSubmission


def _view(job: RefreshJob) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "region": job.region.name,
        "day": str(job.day),
        "status": job.status.name,
        "attempts": job.attempts,
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


def _required(jobs: RefreshJobService, id: UUID) -> RefreshJob:
    job = jobs.find(id)
    if job is None:
        raise ApiError(404, "JOB_NOT_FOUND", "Refresh job not found")
    return job


def admin_router(jobs: RefreshJobService) -> APIRouter:
    router = APIRouter()

    @router.post(BASE)
    def submit(
        request: Request,
        submission: Submission,
        idempotency_key: Annotated[str, Header()],
    ) -> Response:
        if isinstance(submission, WindowSubmission):
            ids = jobs.submit_window(
                idempotency_key,
                submission.region,
                submission.startDay,
                submission.endExclusive,
                request.state.actor,
            )
            return JSONResponse(
                {"jobs": [_view(_required(jobs, id)) for id in ids]},
                status_code=202,
            )
        id = jobs.submit(
            idempotency_key, submission.region, submission.day, request.state.actor
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
