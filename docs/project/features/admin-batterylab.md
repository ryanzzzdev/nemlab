# BatteryLab inspection in Admin

Date: 2026-10-09. Status: Accepted direction; implementation defaults selected under delegated authority. Planned, not implemented. [Decision 026](../decisions/026-admin-batterylab-inspection.md); [NEM-117–123](../backlog.md#nem-117).

## Outcome and boundaries

Make Data Operations useful for both products: shared price coverage, GridReplay observations/publications and BatteryLab stored simulations. Add **Simulations** alongside Coverage, Loads & Jobs and Publications inside the delivered desktop workspace; retain Access separately. Reuse the dense table, shared scope, inspector, help and role boundaries from [desktop redesign](admin-desktop-redesign.md). No new app or duplicate scenario builder.

This slice is inspection, diagnosis and provenance. No Admin simulation submit, cancel, retry, delete, bulk export or automatic rerun; the current job state machine has no cancellation contract. Existing owner price-refresh controls remain available with their normal bounds. No reads trigger refreshes, computation or publication. Existing public simulation submit/status/result contracts and saved URLs remain compatible.

## Inspected baseline

`simulation_input` stores the unique scenario key, request JSON, price revision, version JSON and creation time. `simulation_job` has QUEUED/RUNNING/SUCCEEDED/FAILED, attempts, availability, lease and a safe diagnostic code. `simulation_result` stores immutable result JSON and creation time. Inputs/results reject updates/deletes. A logical simulation is deduplicated by normalised scenario, pinned price revision and versions; one stored record is not one visitor or one submission.

The public API reads status/result by ID but has no catalogue. Result payloads contain full prices and dispatch series, so a catalogue must not fetch that payload for every row. Older scenarios can have no threshold result. Existing tables do not establish a complete per-attempt timeline, terminal failure timestamp or elapsed solver runtime. Never infer runtime from result creation minus input creation (that includes queue time and retries).

## Data Operations scope and navigation

Add `view=simulations` and `selection=simulation:<uuid>` using the existing selection encoding. The shared region and inclusive NEM market-date range filter the scenario's market day, not its submission time. Preserve the current <=31-day workspace scope; do not silently widen every other tab. Display “Simulations for [region / market dates]”. Creation timestamps are separately labelled with timezone, sortable newest/oldest. No creation-date filter in the first slice.

Status and strategy filters belong to this view and survive Back/Forward. Strategy filter means **contains a result/configuration for** fixed schedule, price threshold or hindsight; rows may contain multiple strategies. It must not invent a single chosen strategy for a comparison. Invalid filters get recoverable errors. Clear incompatible selection when applied scope changes; opening a direct ID outside scope keeps its inspector with “Outside this selection”, without rewriting the scope or performing a submission.

Coverage day inspector gains “View simulations for this day”; simulation inspector gains “Inspect price coverage” preserving return state. Detail links use opaque IDs only, no personal information. Empty state distinguishes “No stored simulations in this selection” from missing price data. Do not show zero failures or counts if the request failed.

## Simulations table

Default columns: status, market day, created time, battery capacity (MWh), charge/discharge power (MW), included strategies, attempts, result availability and shortened ID. Region may be omitted as a redundant column when the shared scope fixes it. Optional columns: per-strategy margin (AUD), model version, pinned revision comparison state, and finished time when actually known. All decimals remain exact API strings; UI rounding is presentation only with full values accessible.

Use whole-query backend filtering/sorting and bounded keyset pagination: default 50, maximum 100 rows, deterministic `createdAt,id` newest/oldest order. Full exact UUID lookup uses the detail route; no unbounded free-text search. No profit-based ranking or global profitability dashboard in this slice. Summary strip shows counts by current state and total in the same selection, calculated without per-row result loads. Label snapshots/refreshed time: job status can change during pagination; counts are current observations, not an immutable archive snapshot. On Refresh, reset cursor; deduplicate appended IDs and handle rows leaving a status filter honestly. Bind cursor to normalised scope/filter/sort and a creation-time high-water mark so new submissions do not disrupt traversal; this does not freeze mutable status.

At 1440×900 standard density retain at least 10 rows with a useful inspector/activity area. Reuse existing column visibility, density and pane preferences; no public-style cards or new large chart gallery.

## Inspector

Four tabs, all read-only for both owner and viewer:

1. **Scenario**: region/day; battery capacity and charge/discharge ratings; initial/final state and efficiency representation; schedule windows; threshold parameters when present; fees/degradation and other stored cost/site constraints. Render the recorded request, not current UI defaults. Units and fixed NEM time conventions are explicit. Unknown legacy fields say “Not recorded”.
2. **Results**: strategy comparison table with charging cost, revenue, fees, degradation, net margin, imported/exported energy and losses. Successful proven results only; queued/running/failed states explain absence. Hindsight is labelled a perfect-information benchmark, not a forecast. A missing threshold result is “Not included in this saved simulation”, not zero. Show available solver outcome/quality fields with units and methodology, not raw diagnostic text. **Open in BatteryLab** opens `/batterylab?simulation=<id>` for the complete charts; no auto-run and no parameter reconstruction that could use newer prices. Keep this action disabled/unavailable where a saved result cannot be opened meaningfully.
3. **Execution**: actual state, attempts, next eligible retry time when applicable, safe failure reason and recorded lifecycle events. Distinguish retry waiting from RUNNING, queue age from compute duration and incomplete historical evidence from current execution. No fake percentage progress. Terminal outcomes/fencing remain worker-owned. Lower activity pane can show this simulation's recorded events, but do not fetch/poll twice through separate components.
4. **Provenance**: pinned price revision, current stored revision, comparison checked-at time; request/model/fixed/hindsight/threshold/solver versions where recorded; market offset/interval conventions. State “Matches current stored prices”, “Different from current stored prices”, or “Current revision unavailable”. A different revision is not an invalid result or proof of changed profit. Preserve historical values and never recompute them while reading. Distinguish current stored price coverage from the pinned complete snapshot that made this simulation possible.

An unsupported historical result encoding shows a bounded “Stored format not supported by this reader” state with available metadata. It must not break the entire list or invent a result. Format compatibility is checked against Java-era, Python and threshold-optional records.

## Shared price coverage and readiness

Extend the existing Coverage view to make prices a first-class shared input, with a visible “BatteryLab + GridReplay” explanation. Join bounded existing stored-price coverage reads with grid coverage; do not infer price completeness from grid imports. Reuse an existing API if it meets the contract before adding an Admin projection.

Day states: complete stored price day, incomplete, missing or unavailable. Display interval/valid-price counts and current revision where supported. “Ready for BatteryLab input” means the stored-price completeness rules permit preparation; it does not guarantee worker availability or feasibility of every scenario. Keep computation/service availability separate. Grid metrics can be absent while BatteryLab price input is ready. A public visitor refresh job is not a stored simulation and must not appear as one.

Owner may open the existing price refresh action with explicit region/day scope; viewer sees explanation only. Reuse existing submission bounds/deduplication. If the available load drawer always imports grid data too, do not label that as a price-only refresh: add a focused price-only action using the already supported endpoint, with tests. Link from that result to the relevant refresh job. Completion of a refresh updates coverage, never an old simulation.

## Permissions and discovery boundary

New catalogue/detail/event reads require an explicit `simulations.read` capability, granted to owner and approved viewer. Legacy automation does not acquire archive discovery implicitly; keep its existing operational grants unchanged unless separately requested. Anonymous/applicant/revoked/expired sessions are denied. Viewer receives an explicit allowlisted schema, not raw ORM objects or stored JSON. No user identity, IP, request headers, hashes used as dedupe keys, claim/lease tokens, raw exceptions, credentials or provider URLs. Execution actors use generic role labels if needed. Owner does not need raw secrets either.

Catalogue discovery exposes more than possession of an individual public link. For the present project, accepted viewer scope is sanitized system-wide simulation scenarios/results within bounded queries; do not infer ownership of records that have no submitter relation. Do not add submitter attribution from logs. If future scenarios add personal/confidential fields or ownership, revisit visibility before extending these DTOs. Shared prices and model inputs are educational data, not a visitor activity analytics feature. Grant revocation clears cached list/detail/event data on the next failed session/read; browser prefetch must not bypass capability checks.

## Backend read contract

Proposed paths (freeze in OpenAPI before frontend integration):

- `GET /api/admin/v1/simulations?region=&from=&to=&status=&strategy=&sort=&limit=&cursor=` returns bounded safe summaries, next cursor, selected-scope state counts and as-of metadata. Inclusive dates match workspace conventions; validate status/strategy combinations and <=31 completed market days. Absent status/strategy means all; no unsupported combined multi-sort.
- `GET /api/admin/v1/simulations/{id}` returns safe scenario, result summary, execution facts and provenance, without full interval arrays. Unknown ID 404; not-yet-successful simulation still has a valid inspection record.
- `GET /api/admin/v1/simulations/{id}/events` returns bounded chronological lifecycle pages, with explicit recording-start/historical-completeness metadata.

Use storage-level projection of necessary JSON scalars or a measured summary projection, not N+1 full result decoding. Default/maximum page limits and query indexes are tested. Add only indexes/projections justified by representative EXPLAIN/query measurements, including legacy JSON shape compatibility. Detail may load one stored result to produce its small summary; the listing may not. Current revision comparison is a read-only join and does not change the pinned input. Contract generation/captures and the frontend client are part of delivery; no manual edits to generated types.

## Future execution evidence

Add an append-only simulation lifecycle table for future transitions: created/queued, claimed, retry scheduled, lease recovery, succeeded and failed. Record timestamp, attempt number, safe diagnostic code and applicable elapsed evidence; no secrets. Persist events in the same transaction as authoritative state changes, using existing fencing. Rejected stale completions must not create successful history events. Deduplicated submissions do not create another queued event or imply another execution.

For historical jobs, show known created/result timestamps and current attempt count, explicitly “Detailed execution history was not recorded”. Do not backfill invented claim/failure events. Jobs already running at migration may produce partial history; mark it accordingly. Compute attempt duration only when a matching recorded start/end exists, and label it worker attempt duration, not pure solver CPU time. Successful result timestamp can support end-to-end latency if labelled including queue/retries. Retain lifecycle events alongside simulation records in this slice; revisit operational retention in M7 without deleting immutable market evidence.

## Delivery and acceptance

NEM-117 safe catalogue/detail/provenance queries → NEM-119 HTTP/contract after NEM-118 lifecycle recording → NEM-120 desktop simulation inspector. NEM-121 shared price coverage builds against the same read contracts and existing refresh APIs. NEM-122 explains both product pipelines and preserves routing/polling. NEM-123 performs integrated and visual acceptance. Backend query/lifecycle work can proceed independently; no subagent delegation is implied.

Acceptance fixtures: queued/running/succeeded/failed; retry/recovery and stale claim; duplicate scenario; identical timestamp cursor ties; threshold absent/present; legacy/version mismatch; empty day; changed/current/unavailable price revision; partial historical execution; missing grid but complete price day. Corrected-price test proves saved accounting/revision and public saved link unchanged after refresh. Query tests prove full-scope filters/counts, bounded responses, invalid cursors, no per-row result fan-out and exact money strings.

Security matrix covers all three routes for owner/viewer/automation/anonymous/applicant/expired/revoked; malicious/unknown IDs and nested fields cannot bypass projection. Browser checks cover scope restoration, direct out-of-scope ID, comparison rows, provenance, refreshing running status, hidden-pane polling shutdown, viewer/no-write affordances and safe external product navigation. Live API/worker/PostgreSQL journey covers a real stored scenario through the inspector to public BatteryLab, without submitting merely to inspect.

Record screenshots at 1280×720,1440×900,1920×1080 with light/dark/auto, density/keyboard/200% zoom. Run relevant backend lifecycle/contract tests, frontend format/check and dedicated Admin plus public regression tests. Existing completed M6/redesign evidence remains historical; this new product coverage is separately open M6 scope. No implementation, account creation, source imports or runtime verification is performed by this plan.
