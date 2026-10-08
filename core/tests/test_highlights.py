"""NEM-084 — publication-scoped highlight selection tests.

Hand-labelled candidate lists verify the frozen ``highlights-v1``/``v2``
rules: per-reason exact-value ranking, deterministic ties, per-type/per-day
caps, deduplication with preserved multi-reason ranks, and v2 compound
suppression inside the selection only.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from nemlab_core.detectors import EventType
from nemlab_core.highlights import (
    HIGHLIGHTS_V1,
    HIGHLIGHTS_V2,
    MAX_HIGHLIGHTS,
    Candidate,
    Reason,
    select,
)

DAY = date(2023, 9, 4)
T0 = datetime(2023, 9, 3, 14, 0, tzinfo=UTC)


def _id(n: int) -> UUID:
    return UUID(int=n)


def _candidate(
    n: int,
    type: EventType,
    *,
    count: int = 1,
    value: str = "0",
    start_hours: float = 0.0,
    day: date = DAY,
    linked: tuple[tuple[EventType, datetime], ...] = (),
) -> Candidate:
    return Candidate(
        id=_id(n),
        type=type,
        market_day=day,
        start_at=T0 + timedelta(days=(day - DAY).days, hours=start_hours),
        interval_count=count,
        value=Decimal(value),
        linked=linked,
    )


def _run(n: int, **kw: object) -> Candidate:
    return _candidate(n, EventType.NEGATIVE_PRICE_RUN, **kw)  # type: ignore[arg-type]


def _spike(n: int, **kw: object) -> Candidate:
    return _candidate(n, EventType.PRICE_SPIKE, **kw)  # type: ignore[arg-type]


def _ramp(n: int, **kw: object) -> Candidate:
    return _candidate(n, EventType.DEMAND_RAMP, **kw)  # type: ignore[arg-type]


def test_empty_selection() -> None:
    assert select([]) == []


def test_top_of_each_reason_round_robins() -> None:
    """One candidate per list: each is selected once, in priority order."""
    spike = _spike(1, value="1500")
    run = _run(2, count=6, value="-40", day=DAY + timedelta(days=1))
    ramp = _ramp(3, count=37, value="600", day=DAY + timedelta(days=2))
    selected = select([ramp, run, spike], version=HIGHLIGHTS_V1)
    assert [s.candidate.id for s in selected] == [spike.id, run.id, ramp.id]
    assert selected[0].selected_by is Reason.HIGHEST_PRICE
    assert selected[1].selected_by is Reason.LONGEST_NEGATIVE_RUN


def test_reason_ranking_uses_exact_values() -> None:
    cheap = _run(1, count=10, value="-0.01")
    deep = _run(2, count=3, value="-400", day=DAY + timedelta(days=1))
    longest = _run(3, count=40, value="-5", day=DAY + timedelta(days=2))
    selections = select([cheap, deep, longest], version=HIGHLIGHTS_V1)
    by_id = {s.candidate.id: s for s in selections}
    # longest list ranks by interval_count then depth
    longest_reason = next(
        r for r in by_id[longest.id].reasons if r.reason is Reason.LONGEST_NEGATIVE_RUN
    )
    assert longest_reason.rank == 1 and longest_reason.population == 3
    # the deepest run keeps BOTH reasons with their own units
    deep_reasons = {r.reason: r for r in by_id[deep.id].reasons}
    assert deep_reasons[Reason.DEEPEST_NEGATIVE_PRICE].rank == 1
    assert deep_reasons[Reason.LONGEST_NEGATIVE_RUN].rank == 3


def test_deterministic_ties_start_desc_then_id_desc() -> None:
    # Same type + start is one logical event, so the id tiebreak is a
    # total-order safety net — assert it on the candidate list directly.
    from nemlab_core.highlights import _lists

    older = _spike(1, value="1500", start_hours=1)
    newer_low_id = _spike(2, value="1500", start_hours=3)
    newer_high_id = _spike(9, value="1500", start_hours=3)
    ordering = _lists([older, newer_low_id, newer_high_id], HIGHLIGHTS_V1)[
        Reason.HIGHEST_PRICE
    ]
    assert [c.id for c in ordering] == [
        newer_high_id.id,
        newer_low_id.id,
        older.id,
    ]
    selections = select([older, newer_low_id, newer_high_id], version=HIGHLIGHTS_V1)
    order = [s.candidate.id for s in selections]
    assert order[0] == newer_high_id.id


def test_per_day_cap_scans_down_the_list() -> None:
    """A top candidate blocked by the day cap does not end the list's turn —
    the next eligible candidate on the same list is still considered."""
    run_day1_a = _run(1, count=20, day=DAY)
    ramp_day1 = _ramp(2, count=37, value="500", day=DAY)
    run_day1_b = _run(3, count=19, day=DAY)
    run_day2 = _run(4, count=5, day=DAY + timedelta(days=1))
    selections = select(
        [run_day1_a, ramp_day1, run_day1_b, run_day2], version=HIGHLIGHTS_V1
    )
    selected = {s.candidate.id for s in selections}
    # day1 fills with the top run + ramp; run_day1_b is day-capped; run_day2 joins
    assert selected == {run_day1_a.id, ramp_day1.id, run_day2.id}


def test_per_type_cap() -> None:
    runs = [
        _run(i, count=30 - i, value="-10", day=DAY + timedelta(days=i))
        for i in range(1, 8)
    ]
    selections = select(runs, version=HIGHLIGHTS_V1)
    assert len(selections) == 4  # run type cap binds


def test_max_eight_cards_without_filler() -> None:
    """A thin publication returns fewer than eight truthful cards."""
    spikes = [
        _spike(i, value=str(2000 - i), day=DAY + timedelta(days=i)) for i in range(1, 6)
    ]
    selections = select(spikes, version=HIGHLIGHTS_V1)
    assert len(selections) <= MAX_HIGHLIGHTS
    assert all(s.candidate.type is EventType.PRICE_SPIKE for s in selections)
    assert len(selections) == 2  # spike type cap, not padded with filler


def test_dedupe_same_logical_event() -> None:
    """Two ids for one logical event (type + start) select only once."""
    a = _run(1, count=10, value="-30")
    dup = _run(2, count=10, value="-30", start_hours=0.0)
    assert a.start_at == dup.start_at
    selections = select([a, dup], version=HIGHLIGHTS_V1)
    ids = [s.candidate.id for s in selections]
    assert len(set(ids)) == len(ids)
    assert sum(1 for i in ids if i in (a.id, dup.id)) == 1


def test_type_filter_restricts_lists_but_keeps_cap() -> None:
    runs = [
        _run(i, count=40 - i, value="-20", day=DAY + timedelta(days=i))
        for i in range(1, 9)
    ]
    selections = select(
        runs, event_type=EventType.NEGATIVE_PRICE_RUN, version=HIGHLIGHTS_V1
    )
    assert len(selections) == 4  # run cap applies under the type filter
    assert all(s.candidate.type is EventType.NEGATIVE_PRICE_RUN for s in selections)


def test_unknown_version_rejected() -> None:
    with pytest.raises(ValueError):
        select([], version="highlights-v0")


def test_v2_episode_suppresses_member_runs() -> None:
    member1 = _run(1, count=6, value="-20")
    member2 = _run(2, count=5, value="-30", start_hours=1)
    episode = _candidate(
        3,
        EventType.NEGATIVE_PRICE_EPISODE,
        count=14,
        value="-30",
        day=DAY + timedelta(days=1),
        linked=(
            (EventType.NEGATIVE_PRICE_RUN, member1.start_at),
            (EventType.NEGATIVE_PRICE_RUN, member2.start_at),
        ),
    )
    selections = select([member1, member2, episode], version=HIGHLIGHTS_V2)
    selected = {s.candidate.id for s in selections}
    assert episode.id in selected
    assert member1.id not in selected and member2.id not in selected


def test_v2_reversal_suppresses_its_run_but_run_list_still_ranks() -> None:
    run_a = _run(1, count=8, value="-50", start_hours=0)
    run_b = _run(2, count=12, value="-60", start_hours=3, day=DAY + timedelta(days=1))
    reversal = _candidate(
        3,
        EventType.PRICE_REVERSAL,
        count=40,
        value="1800",
        start_hours=0,
        day=DAY + timedelta(days=2),
        linked=((EventType.NEGATIVE_PRICE_RUN, run_a.start_at),),
    )
    selections = select([run_a, run_b, reversal], version=HIGHLIGHTS_V2)
    selected = {s.candidate.id for s in selections}
    assert reversal.id in selected
    assert run_a.id not in selected  # suppressed by the selected reversal
    assert run_b.id in selected  # unrelated run still selected


def test_v2_unusual_ramp_suppresses_underlying_ramp() -> None:
    ramp = _ramp(1, count=37, value="1500", start_hours=2)
    unusual = _candidate(
        2,
        EventType.UNUSUAL_DEMAND_RAMP,
        count=37,
        value="1500",
        start_hours=2,
        linked=((EventType.DEMAND_RAMP, ramp.start_at),),
    )
    selections = select([ramp, unusual], version=HIGHLIGHTS_V2)
    selected = {s.candidate.id for s in selections}
    assert unusual.id in selected and ramp.id not in selected


def test_v1_selection_ignores_v2_types() -> None:
    episode = _candidate(1, EventType.NEGATIVE_PRICE_EPISODE, count=10, value="-5")
    run = _run(2, count=9, value="-7", day=DAY + timedelta(days=1))
    selections = select([episode, run], version=HIGHLIGHTS_V1)
    assert all(
        s.candidate.type is not EventType.NEGATIVE_PRICE_EPISODE for s in selections
    )
    assert run.id in {s.candidate.id for s in selections}
