"""Public GridReplay catalogue and replay endpoints.

Read-only over published, immutable event versions — requests never trigger
imports or detection, and superseded event ids stay reproducible. The list
endpoint paginates newest-first through the region's current publication;
a cursor pins that publication so a republish cannot shift an in-progress
page sequence.
"""

import base64
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, Response

from nemlab_api.errors import ApiError, instant
from nemlab_api.validation import IsoDate
from nemlab_core import decimal_text
from nemlab_core.detectors import EventType
from nemlab_core.prices import Region
from nemlab_infrastructure.grid.events import GridCatalogue, Publication, StoredEvent

BASE = "/api/v1/events"
NO_STORE = {"Cache-Control": "no-store"}
DEFAULT_PAGE = 24
MAX_PAGE = 100


def _publication(publication: Publication) -> dict[str, Any]:
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


def _item(event: StoredEvent) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "region": event.region.name,
        "type": event.type.value,
        "detectorVersion": event.detector_version,
        "marketDay": str(event.market_day),
        "startAt": instant(event.start_at),
        "endAt": instant(event.end_at),
        "intervalCount": event.interval_count,
        "durationMinutes": event.interval_count * 5,
        "value": decimal_text.to_plain_string(event.value),
        "edgeIncomplete": event.edge_incomplete,
        "version": event.version,
        "superseded": event.superseded,
        "coverage": event.coverage,
    }


def _detail(catalogue: GridCatalogue, event: StoredEvent) -> dict[str, Any]:
    window = catalogue.replay_window(event.id)
    return {
        **_item(event),
        "detectorParams": event.detector_params,
        "sourceRevisions": event.source_revisions,
        "replay": None
        if window is None
        else {"startDay": str(window[0]), "endExclusive": str(window[1])},
    }


def _parse_cursor(raw: str) -> tuple[UUID, datetime, UUID]:
    try:
        decoded = base64.urlsafe_b64decode(raw).decode()
        return (
            UUID(decoded[:36]),
            datetime.fromisoformat(decoded[37:-37]),
            UUID(decoded[-36:]),
        )
    except (ValueError, UnicodeDecodeError) as failure:
        raise ValueError("malformed cursor") from failure


def _cursor(publication: Publication, event: StoredEvent) -> str:
    raw = f"{publication.id}:{event.start_at.isoformat()}:{event.id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def events_router(catalogue: GridCatalogue) -> APIRouter:
    router = APIRouter()

    @router.get(BASE)
    def list_events(
        region: Region,
        type: Annotated[EventType | None, Query()] = None,
        from_: Annotated[IsoDate | None, Query(alias="from")] = None,
        to: Annotated[IsoDate | None, Query(alias="to")] = None,
        limit: Annotated[int, Query(ge=1, le=MAX_PAGE)] = DEFAULT_PAGE,
        cursor: str | None = None,
    ) -> Response:
        if (from_ is None) != (to is None) or (
            from_ is not None and to is not None and from_ > to
        ):
            raise ValueError("from/to must be a complete inclusive range")
        if cursor is not None:
            pinned, mark, last = _parse_cursor(cursor)
            publication = catalogue.publication(pinned)
            if publication is None:
                raise ApiError(
                    404,
                    "PUBLICATION_NOT_FOUND",
                    "The pinned publication no longer exists",
                )
            position = (mark, last)
        else:
            current = catalogue.current_publication(region)
            if current is None:
                raise ApiError(
                    404,
                    "CATALOGUE_NOT_PUBLISHED",
                    "No published catalogue for this region",
                )
            publication, position = current, None
        events, has_more = catalogue.catalogue_events(
            publication.id, type, from_, to, limit, position
        )
        next_cursor = _cursor(publication, events[-1]) if has_more and events else None
        return JSONResponse(
            {
                "publication": _publication(publication),
                "events": [_item(e) for e in events],
                "nextCursor": next_cursor,
            },
            headers=NO_STORE,
        )

    @router.get(BASE + "/{id}")
    def detail(id: UUID) -> dict[str, Any]:
        event = catalogue.event(id)
        if event is None:
            raise ApiError(404, "EVENT_NOT_FOUND", "Event not found")
        return _detail(catalogue, event)

    @router.get(BASE + "/{id}/replay")
    def replay(
        id: UUID,
        startDay: IsoDate | None = None,
        endExclusive: IsoDate | None = None,
    ) -> Response:
        event = catalogue.event(id)
        if event is None:
            raise ApiError(404, "EVENT_NOT_FOUND", "Event not found")
        snapshot = catalogue.replay(id, startDay, endExclusive)
        if snapshot is None:
            raise ApiError(404, "REPLAY_NOT_FOUND", "No replay snapshot for this event")
        return JSONResponse(
            {
                "event": _detail(catalogue, event),
                "manifest": snapshot["manifest"],
                "payload": snapshot["payload"],
            },
            headers=NO_STORE,
        )

    return router
