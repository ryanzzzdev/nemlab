"""Operator grid-publication endpoints — bounded detection runs.

Mounted only when ``nemlab.admin.enabled``; ``OperatorBearer`` authenticates
every ``/api/admin/**`` request before these routes run. Publication is
synchronous: the frozen detectors evaluate at most 31 stored market days, so
no network access or worker round-trip is needed.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict

from nemlab_api.errors import ApiError, instant
from nemlab_api.validation import IsoDate
from nemlab_core.prices import Region
from nemlab_infrastructure.grid.events import GridCatalogue, Publication

BASE = "/api/admin/v1/grid-publications"


class Submission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    region: Region
    startDay: IsoDate
    endExclusive: IsoDate


def _view(publication: Publication) -> dict[str, Any]:
    return {
        "id": str(publication.id),
        "region": publication.region.name,
        "startDay": str(publication.start),
        "endExclusive": str(publication.end),
        "detectorVersion": publication.detector_version,
        "eventCount": publication.event_count,
        "coverage": publication.coverage,
        "createdAt": instant(publication.created_at),
    }


def grid_publications_router(catalogue: GridCatalogue) -> APIRouter:
    router = APIRouter()

    @router.post(BASE)
    def publish(submission: Submission) -> Response:
        publication = catalogue.publish(
            submission.region, submission.startDay, submission.endExclusive
        )
        return JSONResponse(
            _view(publication),
            status_code=201,
            headers={"Location": f"{BASE}/{publication.id}"},
        )

    @router.get(BASE)
    def recent(limit: int = 50) -> list[dict[str, Any]]:
        return [_view(p) for p in catalogue.publications(limit)]

    @router.get(BASE + "/{id}")
    def detail(id: UUID) -> dict[str, Any]:
        publication = catalogue.publication(id)
        if publication is None:
            raise ApiError(404, "PUBLICATION_NOT_FOUND", "Publication not found")
        return _view(publication)

    return router
