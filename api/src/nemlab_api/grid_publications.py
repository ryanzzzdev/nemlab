"""Operator grid-publication endpoints — bounded detection runs.

Mounted only when ``nemlab.admin.enabled``; ``OperatorBearer`` authenticates
every ``/api/admin/**`` request before these routes run. Publication is
synchronous: the frozen detectors evaluate at most 31 stored market days, so
no network access or worker round-trip is needed.
"""

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, StringConstraints

from nemlab_api.capabilities import actor_label
from nemlab_api.errors import ApiError, instant
from nemlab_api.validation import IsoDate
from nemlab_core.highlights import HIGHLIGHTS_V2
from nemlab_core.prices import Region
from nemlab_infrastructure.grid.events import (
    EventQuery,
    GridCatalogue,
    Publication,
)

BASE = "/api/admin/v1/grid-publications"


class Submission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    region: Region
    startDay: IsoDate
    endExclusive: IsoDate
    # Publishing detector-v2 event types is an explicit operator choice;
    # absent means the frozen v1 suite.
    detectorSuite: Literal["v1", "v2"] = "v1"
    # Optional caller correlation for reconciling a lost publish response
    # against the attempts read — never deduplicates publications.
    attemptKey: (
        Annotated[str, StringConstraints(min_length=1, max_length=128)] | None
    ) = None


def _actor_label(actor: str | None) -> str | None:
    """Viewer-safe actor: the role label only, never the identity suffix
    (``owner:<id>`` -> ``Owner``, ``operator:<name>`` -> ``Operator``)."""
    return actor_label(actor) if actor else None


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
        "runId": str(publication.run_id) if publication.run_id else None,
        "actor": _actor_label(publication.actor),
        "attemptKey": publication.attempt_key,
    }


def grid_publications_router(catalogue: GridCatalogue) -> APIRouter:
    router = APIRouter()

    @router.post(BASE)
    def publish(request: Request, submission: Submission) -> Response:
        publication = catalogue.publish(
            submission.region,
            submission.startDay,
            submission.endExclusive,
            suite=submission.detectorSuite,
            actor=getattr(request.state, "actor", None),
            attempt_key=submission.attemptKey,
        )
        return JSONResponse(
            _view(publication),
            status_code=201,
            headers={"Location": f"{BASE}/{publication.id}"},
        )

    @router.get(BASE)
    def recent(limit: int = 50) -> list[dict[str, Any]]:
        return [_view(p) for p in catalogue.publications(limit)]

    @router.get(BASE + "/attempts")
    def attempts(request: Request, limit: int = 50) -> list[dict[str, Any]]:
        """Bounded detection-run history — COMPLETE and FAILED attempts with
        actor label and caller correlation for lost-response reconciliation.
        Failure diagnostics are raw exception text, so viewers see them
        redacted."""
        viewer = request.state.viewer
        return [
            {
                "id": str(run.id),
                "region": run.region.name,
                "startDay": str(run.start),
                "endExclusive": str(run.end),
                "detectorVersion": run.detector_version,
                "status": run.status,
                "publicationId": str(run.publication_id)
                if run.publication_id
                else None,
                "diagnostic": None if viewer else run.diagnostic,
                "actor": _actor_label(run.actor),
                "attemptKey": run.attempt_key,
                "createdAt": instant(run.created_at),
            }
            for run in catalogue.attempts(limit)
        ]

    @router.get(BASE + "/{id}")
    def detail(id: UUID) -> dict[str, Any]:
        publication = catalogue.publication(id)
        if publication is None:
            raise ApiError(404, "PUBLICATION_NOT_FOUND", "Publication not found")
        selections, matching, totals, eligible, excluded = catalogue.highlights(
            id, EventQuery()
        )
        return {
            **_view(publication),
            "eventCounts": catalogue.event_counts(id),
            "highlights": {
                "version": HIGHLIGHTS_V2,
                "matching": matching,
                "selected": len(selections),
                "eligible": eligible,
                "excluded": excluded,
                "totals": totals,
            },
        }

    return router
