# 020 — GridReplay v1 scope, detectors and fixture contract

Date: 2026-10-02. Status: Accepted (delegated stack authority exercised for
NEM-054; user may amend). Task: [NEM-054](../backlog.md#nem-054). Evidence:
[September 2023 coverage](../evidence/m5-coverage/findings.md).

## Catalogue scope

- Region: **NSW1 only**. Initial catalogue window: **2023-09-01 .. 2023-09-30**
  (30 market days). Verified: every required series is complete 288/288 on all
  30 days; all three detector types have real events in the window.
- Imports are operator-controlled and bounded — **maximum 31 market days per
  import request**, matching the price-backfill bound. No automatic sweep.
- Replay response bound: **maximum 7 market days** per replay window (event
  start day through end day plus context; longer events keep a full summary
  card but serve bounded day windows from the same snapshot).
- Catalogue page size: **default 24, maximum 100**, cursor pagination pinned
  to a publication.

## Frozen detector definitions (detector version `v1`)

All detectors scan **interval-end-labelled 5-minute price** or
**source-labelled 5-minute demand** sequences on the NEM market-day grid
(UTC+10, no DST). Missing means absent row *or* null value — both terminate
qualifying runs.

### Negative-price run (`negative_price_run`)

- Qualifying interval: price **strictly < 0** AUD/MWh.
- Event: ≥ **3 consecutive** qualifying intervals (≥ 15 min).
- Terminators: any nonnegative value, missing/null interval, non-5-minute
  step, or source-window edge.
- Event value: duration (minutes) and minimum price.
- Cross-midnight: scanned as one continuous sequence; a run owns its **start
  market day**; date-range filters include events overlapping the range.
- Chunk/edge policy: a chunk boundary never closes a run (detector
  continuation state is preserved across import chunks). A run touching the
  available source window's left/right edge is **edge-incomplete** — in v1 it
  is recorded with `edge_incomplete=true` and excluded from "complete events"
  claims; it is not truncated and presented as complete.

### Price spike (`price_spike`)

- Qualifying interval: price **strictly > 1000** AUD/MWh (illustrative
  detector setting, not a market price cap).
- Event: ≥ 1 qualifying interval; **contiguous** qualifying intervals group
  into one event; any non-qualifying/missing interval ends the group.
- Event value: duration and peak price. Same ownership/edge rules as
  negative-price runs.

### Scheduled-demand ramp (`demand_ramp`)

- Candidate window: **36 five-minute steps** (3 hours); compare `d[i+36] − d[i]`.
- A candidate is evaluable only when **all 37 observations** in the window are
  present numeric values.
- Eligible windows have both endpoints inside the same NEM market day's
  00:00–24:00 context: `i` in `[0, 287]`, `i+36 ≤ 287` — i.e., start indices
  0..251.
- Event: **at most one per market day** — the maximum positive change. Ties
  choose the earliest start. A complete day with no positive change has no
  event. A day with any missing observation in an eligible window publishes
  **no** daily-largest claim (`insufficient coverage`) — never a best-effort
  ramp.

## Event identity and versioning

- Logical identity: `(region, event_type, detector_version, detector_params,
  start_interval_end_instant)`. `detector_params` is the canonical JSON of the
  frozen parameters (thresholds, lengths) — identical to the
  `SimulationRequest` canonicalisation convention.
- An event is computed against a **fixed set of source revisions**
  (`source_revisions` manifest). Re-running detection on identical inputs
  deduplicates; a source correction produces a **new immutable event version**
  (`supersedes` link) and a new catalogue publication; old event IDs remain
  reproducible.
- Catalogue publications are atomic — readers never see a half-updated run.

## Stored shapes (contract for NEM-055–058)

- `event`: id, region, type, detector_version, detector_params (canonical
  JSON), start/end instants (interval-end, UTC+10 market semantics), start
  market day, summary (duration_minutes, extreme value, ramp MW — per type),
  source_revisions, coverage {evaluated, missing, edge_incomplete}, status.
- `replay manifest` (immutable): event id + version, day window, series list
  each with {metric, unit, source revision, timestamp_semantics
  (`interval_end` | `source_label`), grid state per day}. **Snapshots
  materialise the exact observed values** — replay reproducibility must not
  depend on retention of source series. Provenance records which revisions
  the snapshot was built from.
- Public API (NEM-059 freezes into `openapi.json`): `GET /api/v1/events`,
  `GET /api/v1/events/{id}`, `GET /api/v1/events/{id}/replay` with explicit
  empty/missing/expired states.

## Fixtures

`fixtures/gridreplay/` holds hand-labelled detector inputs using
run-length encoding (documented in its README): complete day, gap-interrupted
run, cross-midnight run, sub-threshold runs, exact-threshold boundary
(0 and 1000 do not qualify), ramp ties/insufficient-coverage, and no-event
days. **Synthetic labels are honest** — fixtures state they are synthetic;
real provenance stays in stored data.

## Exclusions and remaining gaps

- Renewable-peak detector: deferred (denominator/storage/rooftop methodology
  unvalidated — BLK-005).
- Battery regional totals, named interconnectors, causal annotations: out.
- Rooftop solar displayable only as a labelled resampled estimate.
- Retention policy for old event versions: NEM-055/058 must record the chosen
  bound; not frozen here.
- Cross-check of detector output on the real month is a NEM-057 verification
  step, not a scope question.
