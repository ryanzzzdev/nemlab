"""Publication-scoped highlight selection — ``highlights-v1``/``v2``.

Selection ranks the *eligible* events of one pinned publication — never the
first page of a feed — using exact stored values, per-reason candidate lists
and deterministic diversity caps. There is deliberately no mixed-unit score:
every reason keeps its own units and its rank is reported truthfully (a
candidate skipped by a cap keeps its real rank).

``highlights-v2`` adds the detector-v2 event types and suppresses the simple
constituents of a selected compound/classified event inside the selection
only — All events still exposes every original record.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from nemlab_core.detectors import EventType

HIGHLIGHTS_V1 = "highlights-v1"
HIGHLIGHTS_V2 = "highlights-v2"
MAX_HIGHLIGHTS = 8
MAX_PER_DAY = 2


class Reason(StrEnum):
    HIGHEST_PRICE = "highest_price"
    LONGEST_NEGATIVE_RUN = "longest_negative_run"
    DEEPEST_NEGATIVE_PRICE = "deepest_negative_price"
    LARGEST_DEMAND_RISE = "largest_demand_rise"
    UNUSUAL_DEMAND_RISE = "unusual_demand_rise"
    LARGEST_PRICE_REVERSAL = "largest_price_reversal"
    WIDEST_NEGATIVE_EPISODE = "widest_negative_episode"


@dataclass(frozen=True)
class Candidate:
    """The ranking inputs for one eligible stored event."""

    id: UUID
    type: EventType
    market_day: object  # date — ordering does not inspect it beyond equality
    start_at: datetime
    interval_count: int
    value: Decimal
    # Identity of simple events this event subsumes inside a highlights
    # selection (underlying ramp, linked run, episode members). Keyed by
    # (type, start_at) so suppression survives id minting order.
    linked: tuple[tuple[EventType, datetime], ...] = ()


@dataclass(frozen=True)
class RankedReason:
    reason: Reason
    rank: int  # 1-based position in the reason's candidate list
    population: int  # eligible candidates of the reason's event type


@dataclass(frozen=True)
class Selection:
    candidate: Candidate
    reasons: tuple[RankedReason, ...]
    selected_by: Reason = field(compare=False)


def _desc_id(a: Candidate, b: Candidate) -> int:
    return -1 if str(a.id) > str(b.id) else (1 if str(a.id) < str(b.id) else 0)


def _key_value_desc(c: Candidate) -> tuple[object, ...]:
    # Ties: latest start, then highest immutable id — the frozen order.
    return (-c.value, -c.start_at.timestamp(), -c.id.int)


def _lists(events: list[Candidate], version: str) -> dict[Reason, list[Candidate]]:
    runs = [e for e in events if e.type is EventType.NEGATIVE_PRICE_RUN]
    spikes = [e for e in events if e.type is EventType.PRICE_SPIKE]
    ramps = [e for e in events if e.type is EventType.DEMAND_RAMP]
    lists: dict[Reason, list[Candidate]] = {
        Reason.HIGHEST_PRICE: sorted(spikes, key=_key_value_desc),
        Reason.LONGEST_NEGATIVE_RUN: sorted(
            runs,
            key=lambda c: (
                -c.interval_count,
                c.value,
                -c.start_at.timestamp(),
                -c.id.int,
            ),
        ),
        Reason.DEEPEST_NEGATIVE_PRICE: sorted(
            runs,
            key=lambda c: (
                c.value,
                -c.interval_count,
                -c.start_at.timestamp(),
                -c.id.int,
            ),
        ),
        Reason.LARGEST_DEMAND_RISE: sorted(ramps, key=_key_value_desc),
    }
    if version == HIGHLIGHTS_V2:
        unusual = [e for e in events if e.type is EventType.UNUSUAL_DEMAND_RAMP]
        reversals = [e for e in events if e.type is EventType.PRICE_REVERSAL]
        episodes = [e for e in events if e.type is EventType.NEGATIVE_PRICE_EPISODE]
        lists[Reason.UNUSUAL_DEMAND_RISE] = sorted(unusual, key=_key_value_desc)
        lists[Reason.LARGEST_PRICE_REVERSAL] = sorted(reversals, key=_key_value_desc)
        lists[Reason.WIDEST_NEGATIVE_EPISODE] = sorted(
            episodes,
            key=lambda c: (
                -c.interval_count,
                c.value,
                -c.start_at.timestamp(),
                -c.id.int,
            ),
        )
    return lists


# Fixed round-robin priority, frozen per selection version.
_ORDER_V1 = (
    Reason.HIGHEST_PRICE,
    Reason.LONGEST_NEGATIVE_RUN,
    Reason.LARGEST_DEMAND_RISE,
    Reason.DEEPEST_NEGATIVE_PRICE,
)
_ORDER_V2 = (
    Reason.HIGHEST_PRICE,
    Reason.LARGEST_PRICE_REVERSAL,
    Reason.WIDEST_NEGATIVE_EPISODE,
    Reason.LONGEST_NEGATIVE_RUN,
    Reason.UNUSUAL_DEMAND_RISE,
    Reason.LARGEST_DEMAND_RISE,
    Reason.DEEPEST_NEGATIVE_PRICE,
)

_TYPE_CAP_V1 = {
    EventType.PRICE_SPIKE: 2,
    EventType.DEMAND_RAMP: 2,
    EventType.NEGATIVE_PRICE_RUN: 4,
}
_TYPE_CAP_V2 = {
    **_TYPE_CAP_V1,
    EventType.UNUSUAL_DEMAND_RAMP: 2,
    EventType.PRICE_REVERSAL: 2,
    EventType.NEGATIVE_PRICE_EPISODE: 2,
}

_REASON_TYPE = {
    Reason.HIGHEST_PRICE: EventType.PRICE_SPIKE,
    Reason.LONGEST_NEGATIVE_RUN: EventType.NEGATIVE_PRICE_RUN,
    Reason.DEEPEST_NEGATIVE_PRICE: EventType.NEGATIVE_PRICE_RUN,
    Reason.LARGEST_DEMAND_RISE: EventType.DEMAND_RAMP,
    Reason.UNUSUAL_DEMAND_RISE: EventType.UNUSUAL_DEMAND_RAMP,
    Reason.LARGEST_PRICE_REVERSAL: EventType.PRICE_REVERSAL,
    Reason.WIDEST_NEGATIVE_EPISODE: EventType.NEGATIVE_PRICE_EPISODE,
}


def select(
    events: list[Candidate],
    event_type: EventType | None = None,
    version: str = HIGHLIGHTS_V2,
) -> list[Selection]:
    """Round-robin selection with type/day caps and truthful ranks.

    With a type filter only that type's lists participate and its cap still
    applies. Compound v2 events suppress their linked simple constituents for
    the duration of the selection; suppressed events keep their true ranks if
    reached through another list.
    """
    if version not in (HIGHLIGHTS_V1, HIGHLIGHTS_V2):
        raise ValueError(f"unknown selection version: {version}")
    lists = _lists(events, version)
    order: tuple[Reason, ...] = _ORDER_V2 if version == HIGHLIGHTS_V2 else _ORDER_V1
    caps = _TYPE_CAP_V2 if version == HIGHLIGHTS_V2 else _TYPE_CAP_V1
    if event_type is not None:
        order = tuple(r for r in order if _REASON_TYPE[r] is event_type)

    chosen: list[Selection] = []
    chosen_ids: set[UUID] = set()
    chosen_keys: set[tuple[EventType, datetime]] = set()
    suppressed: set[tuple[EventType, datetime]] = set()
    per_type: dict[EventType, int] = {}
    per_day: dict[object, int] = {}
    positions = {reason: 0 for reason in order}

    def fits(candidate: Candidate) -> bool:
        if (
            candidate.id in chosen_ids
            or (
                candidate.type,
                candidate.start_at,
            )
            in chosen_keys
        ):
            return False
        if (candidate.type, candidate.start_at) in suppressed:
            return False
        if per_type.get(candidate.type, 0) >= caps.get(candidate.type, 0):
            return False
        return per_day.get(candidate.market_day, 0) < MAX_PER_DAY

    while len(chosen) < MAX_HIGHLIGHTS:
        added = False
        for reason in order:
            if len(chosen) >= MAX_HIGHLIGHTS:
                break
            listing = lists[reason]
            index = positions[reason]
            while index < len(listing) and not fits(listing[index]):
                index += 1
            positions[reason] = index
            if index >= len(listing):
                continue
            candidate = listing[index]
            positions[reason] = index + 1
            chosen_ids.add(candidate.id)
            chosen_keys.add((candidate.type, candidate.start_at))
            per_type[candidate.type] = per_type.get(candidate.type, 0) + 1
            per_day[candidate.market_day] = per_day.get(candidate.market_day, 0) + 1
            suppressed.update(candidate.linked)
            reasons = tuple(
                RankedReason(
                    r,
                    lists[r].index(candidate) + 1,
                    len(lists[r]),
                )
                for r in order
                if candidate.type is _REASON_TYPE[r] and candidate in lists[r]
            )
            chosen.append(
                Selection(candidate=candidate, reasons=reasons, selected_by=reason)
            )
            added = True
        if not added:
            break
    return chosen
