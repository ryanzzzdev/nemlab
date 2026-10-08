"""Public GridReplay catalogue and replay endpoints.

Read-only over published, immutable event versions — requests never trigger
imports or detection, and superseded event ids stay reproducible. The list
endpoint paginates through the region's pinned publication under a validated
sort; ``/highlights`` ranks the whole publication, never just the first page.
Cursors are versioned: v2 cursors bind the publication, the normalised query
and the sort tuple; legacy v1 cursors (publication + position only) still
work for the unchanged newest-first query shape.
"""

import base64
import hashlib
import json
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, Response

from nemlab_api.errors import ApiError, instant
from nemlab_api.validation import IsoDate
from nemlab_core import decimal_text
from nemlab_core.detectors import EventType
from nemlab_core.highlights import HIGHLIGHTS_V2
from nemlab_core.prices import Region
from nemlab_infrastructure.grid.events import (
    EventQuery,
    GridCatalogue,
    Publication,
    StoredEvent,
)

BASE = "/api/v1/events"
NO_STORE = {"Cache-Control": "no-store"}
DEFAULT_PAGE = 24
MAX_PAGE = 100

Sort = Literal["newest", "oldest", "longest", "deepest", "highest", "largest_rise"]

# Types whose duration is the elapsed span between endpoint observations,
# not a count of qualifying intervals.
_OBSERVATION_SPAN = {EventType.DEMAND_RAMP, EventType.UNUSUAL_DEMAND_RAMP}


def _duration_minutes(event: StoredEvent) -> int:
    if event.type in _OBSERVATION_SPAN:
        return (event.interval_count - 1) * 5
    return event.interval_count * 5


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
        "durationMinutes": _duration_minutes(event),
        "value": decimal_text.to_plain_string(event.value),
        "edgeIncomplete": event.edge_incomplete,
        "version": event.version,
        "superseded": event.superseded,
        "coverage": event.coverage,
        "detail": event.detail,
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


def _decimal(value: str | None, name: str) -> Decimal | None:
    if value is None:
        return None
    parsed = decimal_text.parse(value)
    if not decimal_text.within_decimal_limits(parsed):
        raise ValueError(f"{name} exceeds the decimal field bounds")
    return parsed


def _fingerprint(query: EventQuery) -> str:
    normalized = {
        "type": query.event_type.value if query.event_type else None,
        "from": str(query.start) if query.start else None,
        "to": str(query.end) if query.end else None,
        "sort": query.sort,
        "minDurationMinutes": query.min_duration_minutes,
        "valueGte": (
            decimal_text.to_plain_string(query.value_gte)
            if query.value_gte is not None
            else None
        ),
        "valueLte": (
            decimal_text.to_plain_string(query.value_lte)
            if query.value_lte is not None
            else None
        ),
    }
    return hashlib.sha256(
        json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]


def _primary(sort: str, event: StoredEvent) -> str | None:
    if sort in ("newest", "oldest"):
        return None
    if sort == "longest":
        return str(event.interval_count)
    return decimal_text.to_plain_string(event.value)


def _cursor_v2(
    publication: Publication,
    query: EventQuery,
    event: StoredEvent,
    fingerprint: str,
) -> str:
    payload = {
        "v": 2,
        "p": str(publication.id),
        "q": fingerprint,
        "k": [
            _primary(query.sort, event),
            instant(event.start_at),
            str(event.id),
        ],
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return "v2." + base64.urlsafe_b64encode(raw).decode()


def _parse_cursor(
    raw: str,
) -> tuple[UUID, str | None, tuple[Decimal | None, datetime, UUID]]:
    """Decode a cursor to (publication id, fingerprint, sort tuple)."""
    if raw.startswith("v2."):
        try:
            payload = json.loads(base64.urlsafe_b64decode(raw[3:].encode()).decode())
            key = payload["k"]
            return (
                UUID(payload["p"]),
                payload["q"],
                (
                    Decimal(key[0]) if key[0] is not None else None,
                    datetime.fromisoformat(key[1]),
                    UUID(key[2]),
                ),
            )
        except (ValueError, KeyError, TypeError, UnicodeDecodeError) as failure:
            raise ValueError("malformed cursor") from failure
    try:
        decoded = base64.urlsafe_b64decode(raw).decode()
        return (
            UUID(decoded[:36]),
            None,
            (None, datetime.fromisoformat(decoded[37:-37]), UUID(decoded[-36:])),
        )
    except (ValueError, UnicodeDecodeError) as failure:
        raise ValueError("malformed cursor") from failure


def events_router(catalogue: GridCatalogue) -> APIRouter:
    router = APIRouter()

    def resolve_publication(region: Region, pin: UUID | None) -> Publication:
        if pin is not None:
            publication = catalogue.publication(pin)
            if publication is None:
                raise ApiError(
                    404,
                    "PUBLICATION_NOT_FOUND",
                    "The pinned publication no longer exists",
                )
            if publication.region is not region:
                raise ValueError("Pinned publication belongs to another region")
            return publication
        publication = catalogue.current_publication(region)
        if publication is None:
            raise ApiError(
                404,
                "CATALOGUE_NOT_PUBLISHED",
                "No published catalogue for this region",
            )
        return publication

    def build_query(
        type: EventType | None,
        from_: IsoDate | None,
        to: IsoDate | None,
        sort: Sort,
        min_duration: int | None,
        value_gte: str | None,
        value_lte: str | None,
    ) -> EventQuery:
        query = EventQuery(
            event_type=type,
            start=from_,
            end=to,
            sort=sort,
            min_duration_minutes=min_duration,
            value_gte=_decimal(value_gte, "valueGte"),
            value_lte=_decimal(value_lte, "valueLte"),
        )
        query.validate()
        return query

    def scope_view(query: EventQuery) -> dict[str, Any]:
        return {
            "type": query.event_type.value if query.event_type else None,
            "from": str(query.start) if query.start else None,
            "to": str(query.end) if query.end else None,
            "sort": query.sort,
            "minDurationMinutes": query.min_duration_minutes,
            "valueGte": (
                decimal_text.to_plain_string(query.value_gte)
                if query.value_gte is not None
                else None
            ),
            "valueLte": (
                decimal_text.to_plain_string(query.value_lte)
                if query.value_lte is not None
                else None
            ),
        }

    @router.get(BASE + "/highlights")
    def highlights(
        region: Region,
        type: Annotated[EventType | None, Query()] = None,
        from_: Annotated[IsoDate | None, Query(alias="from")] = None,
        to: Annotated[IsoDate | None, Query(alias="to")] = None,
        sort: Sort = "newest",
        minDurationMinutes: Annotated[int | None, Query(ge=0)] = None,
        valueGte: str | None = None,
        valueLte: str | None = None,
        publication: UUID | None = None,
    ) -> Response:
        query = build_query(
            type, from_, to, sort, minDurationMinutes, valueGte, valueLte
        )
        pinned = resolve_publication(region, publication)
        selections, matching, totals, eligible, excluded = catalogue.highlights(
            pinned.id, query
        )
        items = [
            {
                **_item(event),
                "selectedBy": selection.selected_by.value,
                "reasons": [
                    {
                        "code": reason.reason.value,
                        "rank": reason.rank,
                        "population": reason.population,
                    }
                    for reason in selection.reasons
                ],
            }
            for event, selection in selections
        ]
        return JSONResponse(
            {
                "publication": _publication(pinned),
                "selectionVersion": HIGHLIGHTS_V2,
                "scope": scope_view(query),
                "matchingTotal": matching,
                "typeTotals": totals,
                "eligibleCount": eligible,
                "excludedCount": excluded,
                "highlights": items,
            },
            headers=NO_STORE,
        )

    @router.get(BASE)
    def list_events(
        region: Region,
        type: Annotated[EventType | None, Query()] = None,
        from_: Annotated[IsoDate | None, Query(alias="from")] = None,
        to: Annotated[IsoDate | None, Query(alias="to")] = None,
        sort: Sort = "newest",
        minDurationMinutes: Annotated[int | None, Query(ge=0)] = None,
        valueGte: str | None = None,
        valueLte: str | None = None,
        publication: UUID | None = None,
        limit: Annotated[int, Query(ge=1, le=MAX_PAGE)] = DEFAULT_PAGE,
        cursor: str | None = None,
    ) -> Response:
        query = build_query(
            type, from_, to, sort, minDurationMinutes, valueGte, valueLte
        )
        fingerprint = _fingerprint(query)
        position = None
        if cursor is not None:
            pinned, bound, position = _parse_cursor(cursor)
            if publication is not None and publication != pinned:
                raise ValueError("cursor and publication pin disagree")
            resolved = resolve_publication(region, pinned)
            if bound is None:
                # Legacy v1 cursor: publication + position only — accepted
                # under the unchanged newest-first, unfiltered query shape.
                if (
                    sort != "newest"
                    or minDurationMinutes is not None
                    or valueGte is not None
                    or valueLte is not None
                ):
                    raise ValueError(
                        "legacy cursor is only valid for the newest-first"
                        " unfiltered query"
                    )
            elif bound != fingerprint:
                raise ValueError("cursor does not match this query")
        else:
            resolved = resolve_publication(region, publication)
        events, has_more = catalogue.catalogue_events(
            resolved.id, query, limit, position
        )
        matching, totals = catalogue.catalogue_totals(resolved.id, query)
        next_cursor = (
            _cursor_v2(resolved, query, events[-1], fingerprint)
            if has_more and events
            else None
        )
        return JSONResponse(
            {
                "publication": _publication(resolved),
                "events": [_item(e) for e in events],
                "nextCursor": next_cursor,
                "matchingTotal": matching,
                "typeTotals": totals,
            },
            headers=NO_STORE,
        )

    @router.get(BASE + "/{id}")
    def detail(id: UUID) -> dict[str, Any]:
        event = catalogue.event(id)
        if event is None:
            raise ApiError(404, "EVENT_NOT_FOUND", "Event not found")
        return _detail(catalogue, event)

    @router.get(BASE + "/{id}/preview")
    def preview(id: UUID) -> Response:
        event = catalogue.event(id)
        if event is None:
            raise ApiError(404, "EVENT_NOT_FOUND", "Event not found")
        result = catalogue.preview(id)
        if result is None:
            raise ApiError(
                404,
                "PREVIEW_NOT_FOUND",
                "No preview could be built from the stored snapshot",
            )
        return JSONResponse(result, headers=NO_STORE)

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
