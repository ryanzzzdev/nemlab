# GridReplay

Updated: 2026-10-02 — NEM-054 froze the initial catalogue (NSW1, September 2023 — verified complete on all required series) and the three v1 detector definitions; see [decision 020](../decisions/020-gridreplay-scope-and-detectors.md), the [coverage evidence](../evidence/m5-coverage/findings.md) and `fixtures/gridreplay/`. Renewable peaks and battery aggregation remain deferred.

Status: M5 delivery plan drafted; demo fidelity is accepted. Detector defaults and initial catalogue coverage are frozen by decision 020; nothing below is implemented yet.

## Visitor outcome

Discover an interesting historical NEM period, inspect aligned evidence, and open its region/day in BatteryLab. Start with one validated region and a bounded catalogue period, expanding only after coverage checks.

## Original detector candidates (superseded by the delivery recommendation below)

Three initial detector candidates:

| Event | Proposed definition to refine before implementation |
| --- | --- |
| Negative-price run | Consecutive complete intervals below zero; gaps end a run. |
| Price spike | A configurable documented price threshold; contiguous qualifying intervals grouped deterministically. |
| Renewable peak | A documented regional renewable metric and threshold/ranking over complete coverage; requires validated metric semantics. |

Numeric thresholds, minimum durations, grouping and ranking are not settled. If renewable coverage is insufficient, assess a validated demand-ramp event as a replacement and record the scope decision before building it. Do not fabricate renewable share from mismatched component series.

Catalogue cards show type, region, market time, duration/value, evidence coverage and methodology. Filter by region, date range and event type. Replay opens a bounded context window with synchronised price, demand, generation-by-technology and validated regional flow charts. A play/pause/scrub cursor moves across the same intervals. Facility changes may be shown only where facility data passed validation; they are supporting observations, not proof of causation.

## Correctness and provenance

Store event detector version, parameters, source revision and evaluated coverage. Repeated detection on identical inputs produces the same logical events without duplicates. Recompute revised periods deliberately while preserving version context for saved investigations.

Document how events cross day boundaries and avoid counting the same event twice in overlapping ingestion windows. Missing intervals interrupt qualifying runs and invalidate unsupported rankings. A label such as longest this month requires complete coverage of that comparison scope or an explicit available-data qualification.

Display regional imports/exports using verified signs and definitions. Named interconnector animations, trip attribution, bidding causes and constraint explanations are outside initial scope without additional evidence.

## Acceptance criteria

- Hand-labelled fixtures verify each detector's boundaries, ties, thresholds, missing intervals and overlap deduplication.
- A replay can be reproduced from its detector/data version and all chart timestamps agree.
- Empty catalogue, missing optional metrics and unavailable periods have clear UI states.
- A catalogue-to-replay-to-BatteryLab journey passes browser checks; cross-midnight events identify the selected simulation day explicitly.
- Public event statements describe observations and their evidence without asserting unverified causes.

Execution is split into [NEM-054–NEM-064](../backlog.md#m5-delivery-tasks) under the NEM-018 and NEM-019 packages. Data prerequisites: [data foundation](data-foundation.md), [BLK-003](../blockers.md#blk-003), [BLK-005](../blockers.md#blk-005).

## Data-validation constraints from M1

The [grid gate](../evidence/oe-validation/grid-gate.md) supports an observation-time replay for the sample days. Shared cursor positions must not imply identical measurement windows. Regional battery totals, curtailment-based events and renewable-peak detection require additional methodology checks before implementation; individual provider series can remain contextual with explicit labels. Keep the three-event target, but settle the third detector using the proposed fallback or validated renewable methodology in NEM-018.

## Exploration demo

A static mock-data page at [docs/demos/gridreplay/index.html](../../demos/gridreplay/index.html) sketches the catalogue, filters, synchronised replay cursor and catalogue→replay→BatteryLab navigation for discussion. It runs a seeded synthetic NSW1 generator with no backend; the detector parameters, thresholds and provisional renewable/ramp definitions shown are illustrative, not accepted definitions, and the page is not a design commitment for NEM-018.

On 2026-09-24 the user selected this mock as the visual reference: full-width layout, compact catalogue/panels and amber accents, with the dark palette as reference. This supersedes the visual-design caveat above, but does not accept the illustrative detector definitions. [Decision 018](../decisions/018-product-layouts-and-appearance.md) adds shared Light/Dark/Auto support; explicit preferences apply consistently across products and Auto follows the device. NEM-042 adds the full-width empty-state shell; catalogue/replay integration remains NEM-018.

## Public shell implementation

NEM-043 implements the accepted layout revision after reviewing the real pages (2026-09-24): GridReplay uses a centered workspace capped at 1440px, with the same centered header/navigation as BatteryLab and consistent responsive gutters. This supersedes the full-width choice above; the mock's panel style, amber accents and theme support remain. See [decision 018](../decisions/018-product-layouts-and-appearance.md).

NEM-034 adds a `/gridreplay` overview in the separate frontend, with explicit unfinished-feature
copy and a methodology link. It contains no data, controls or calculated results. The
full product journey and acceptance criteria above remain future work.


## M5 delivery plan — 2026-09-25

### Readiness and boundaries

The original plan established the journey and correctness constraints, but did not settle detector rules, ingest grid observations, persist event/replay records, or define public contracts. Existing production storage and operator refreshes are price-specific; the frontend is still an empty shell. M1's successful samples are evidence for development, not a populated catalogue. These gaps are explicit tasks below.

Keep this a small personal project: the existing API, worker, PostgreSQL, React and ECharts are sufficient. No new service, event broker, live market feed, causal-analysis engine or generic data platform. Public catalogue and replay requests read stored data; they do not trigger OE imports or detection. The original static demo stays intact as the visual reference.

### Initial data and event recommendation — settle in NEM-054

- Start with NSW1. Reuse the validated 2023-09-11 and 2026-09-11 evidence for offline fixtures. **Accepted in NEM-054**: September 2023 is the first catalogue month — the [coverage probe](../evidence/m5-coverage/findings.md) verified all required series complete on all 30 days. Imports are operator-controlled and bounded (≤31 days per request), not an automatic sweep of history.
- Ship three detector types: **negative-price run, price spike, positive scheduled-demand ramp**. **Frozen in decision 020** (v1 rules below). Defer renewable peaks because the denominator/storage/rooftop methodology remains unverified. Do not copy the demo's synthetic renewable formula into production. New event types can follow later without blocking this first experience.
- Keep four visible replay panels: regional price, scheduled demand, generation by technology and regional flows. Price and scheduled demand are the core context. Generation/flow panels explicitly show unavailable series or gaps when absent; missing optional context does not erase a valid price event.
- Use provider technology series with signed values and documented labels. Do not combine overlapping battery representations into regional totals. Unsupported battery aggregates are omitted with an explanation; rooftop solar is optional, separately labelled as an estimate/resampled feed. Stacking must not bridge missing categories or imply complete supply coverage. No supply-demand balance claim.
- Store prices with their verified interval-end semantics; preserve grid observations' source timestamps and metric-specific timing notes. The shared cursor means **same displayed timestamp**, not proof of identical physical measurement windows. Missing observations stay gaps; never interpolate or substitute zero for detection/readouts.

Detector v1 rules — **frozen by [decision 020](../decisions/020-gridreplay-scope-and-detectors.md) on 2026-10-02** with labelled examples in `fixtures/gridreplay/`; the demand-ramp completeness rule was tightened (any missing observation in the eligible domain withholds the daily-largest claim) and edge-incomplete runs are recorded rather than shown as complete:

| Type | Rule | Event value and edge behavior |
| --- | --- | --- |
| Negative-price run | Strict price < 0 AUD/MWh for at least three consecutive five-minute intervals (15 minutes). | All qualifying runs, duration and minimum price. Zero, a missing interval or a non-five-minute step ends the run. |
| Price spike | Strict price > 1,000 AUD/MWh for at least one interval; group adjacent qualifying intervals. | All qualifying runs, duration and peak price. Exactly 1,000 does not qualify; a gap ends the run. Threshold is an illustrative detector setting, not a market price cap. |
| Demand ramp | Largest positive scheduled-demand change over a three-hour window, at most one event per market day. | Compare observations 36 five-minute steps apart; require all 37 observations in each candidate window. Eligible starts and ends lie within that NEM day's 00:00–24:00 context. Ties choose the earliest start. Publish a daily-largest claim only when the entire eligible day/window domain is complete; otherwise record insufficient coverage. A complete nonpositive day has no positive-ramp event. |

Store exact parameters and detector version with events. The demand metric describes AEMO TOTALDEMAND as previously sampled; it is not total underlying consumption. Neutral titles describe measured values and times. Do not ship demo taglines asserting a heatwave, scarcity, solar glut or causal explanation without separate evidence.

Cross-midnight price runs must be scanned as continuous sequences, not independently per day. A chunk boundary alone never closes a run. Preserve detector continuation state and use observed break/gap boundaries; left/right edges of the available source window are explicitly incomplete, not evidence of a true event start/end. The first catalogue may exclude unresolved edge runs with an explicit coverage note. Do not publish two complete-looking cards for fragments of the same run. Assign complete events to their start market day and include overlapping events in date-range filters. No “longest this month” rankings in v1.

### Demo fidelity is a delivery requirement

The user explicitly asked on 2026-09-25 for the real page to look as close to the demo as possible. Use [the demo](../../demos/gridreplay/index.html) as the primary composition reference, not merely color inspiration. Build and visually review the frontend early using test/development fixtures while backend work proceeds; fixtures must not masquerade as real events in the public page.

| Demo element | Real-page requirement |
| --- | --- |
| Compact dark workspace, amber accent | Preserve type scale, density, borders, radii, spacing and amber hierarchy. Keep the accepted centered 1440px maximum and shared 1160px header instead of reverting to full width. Light/Dark/Auto remains shared across products. |
| Catalogue heading and filter row | Same location/order: region, event type, From, To; compact controls, available-coverage hint and responsive wrapping. Dates are inclusive NEM dates in the UI. Show only supported choices, not fake coverage. |
| Event card grid | Same badge/title/time/primary figure/secondary provenance hierarchy; approximately 310px desktop cards and 12px gaps where space allows, one column on phones. Use actual links/buttons with keyboard focus, not click-only divs. Selected event is clearly marked. |
| Replay below catalogue | Preserve the catalogue above the selected replay. Opening a card focuses the replay heading and reveals the charts; Back restores filters/selection without surprising resets. |
| Replay heading and BatteryLab action | Event title and compact metadata on the left, “Open in BatteryLab” on the right, wrapping naturally on mobile. Put the selected simulation day beside the action for cross-midnight events. |
| Playback row | Play/Pause, Slow/Normal/Fast speed, scrubber and NEM clock in the same sequence and location. No autoplay on load. |
| Readout strip | Compact current price/demand/technology/flow values above the charts; units, date/time and missing values explicit. It moves with the shared cursor. |
| Four chart cards | Same order and compact integrated styling: amber price with negative-price shading, blue demand, technology-colored generation, imports above / exports below zero. Event band and one cursor align across all panels. All available charts render automatically. |
| Provenance below charts | Quiet source/revision/detector/coverage/timing notes and methodology; keep the graphics central. Replace the mock-data warning with truthful coverage context. An optional collapsed exact-value table provides accessible inspection. |

Intentional differences from the mock are limited to the accepted centered/shared shell and themes, real-data/coverage honesty, the validated detector set, URL navigation, and accessibility/responsive corrections. Record any further material visual departure before accepting the UI. Compare screenshots at matching desktop, 768px, 390px and 320px widths; include dark and light palettes, long titles, missing optional data and empty/error states. Do not accept “tests pass” as a substitute for viewing the page through computer use.

### Data, publication and reproducibility

Extend the existing storage/worker pattern with a bounded GridReplay slice, not a premature universal ingestion framework. Series identity includes region, metric/technology, units, source and timestamp semantics. Versioned observations distinguish returned zero, null, omitted timestamp and missing series. Coverage is per required metric and detector window, not a single misleading “288/288” badge for every panel.

Run detection against a fixed set of source revisions and frozen parameters. Publish an event record and immutable replay snapshot/manifest together; the manifest must point to retained immutable observations or materialize the exact data. Reloading an event ID never silently switches to the latest series. Logical identity uses region, event type, detector version/configuration and canonical event boundaries; identical reruns deduplicate. A source correction creates a new immutable event version and a new catalogue publication, while old event links remain reproducible within the documented retention policy. Publish catalogue updates atomically so readers cannot see half a run. Reuse a small publication/version record rather than build a moderation system.

Proposed replay scope: event start market day through end market day, with bounded context before/after when available. Set the exact maximum response/window budget in NEM-054 (initial recommendation: seven market days per response); for longer events retain their full summary and offer bounded day windows from the same immutable snapshot. Never silently truncate an event or fetch an unbounded payload. No user-visible replay window may claim completeness outside stored coverage.

### Public contract and navigation

Proposed resources, finalized in the existing OpenAPI contract by NEM-059:

- `GET /api/v1/events`: region/type/inclusive market-date filters, deterministic newest-first ordering with an ID tie-breaker, bounded page size (suggested 24, maximum 100) and cursor pagination pinned to a publication. Return supported coverage separately from “no matching events”.
- `GET /api/v1/events/{eventId}`: immutable event version, boundaries, observations/summary, detector definition, revision/coverage manifest and available replay windows.
- `GET /api/v1/events/{eventId}/replay`: bounded snapshot window with aligned timestamp references, exact stored values, per-series units/semantics/gaps and event highlights. Empty/unsupported/malformed/missing/expired states are explicit contract cases. Never expose credentials or worker internals.

Keep `/gridreplay` as the main route. Proposed share state is `?event=<immutable-id>` plus catalogue filters; optional timestamp/window state can be added only if it remains small and validated. Direct open/reload and browser Back/Forward must work without re-running detection. Do not write a history entry on every playback tick.

“Open in BatteryLab” navigates to `/batterylab?region=NSW1&day=YYYY-MM-DD` with a visible NEM date. Default to the selected replay cursor's day, clamped to available event days, and allow an explicit day choice for cross-midnight events. The terminal 00:00 price observation belongs to the preceding price interval/day: define and test the exact boundary mapping rather than using the browser timezone. BatteryLab prefills only region/day and never auto-runs. A `simulation` saved-result link takes precedence over prefill parameters. Existing visitor price-refresh behavior applies only after the visitor presses Run.

### Playback and verification

Use one cursor/window state for all panels and readouts. Hover/tap/scrub and keyboard actions agree; a zoom/window change preserves the timestamp when possible and visibly clamps it otherwise. Playback advances across the stored timeline, keeps gaps visible, stops at the end, and pauses on event change, navigation, hidden tab or manual scrubbing. Respect reduced-motion preference and provide accessible labels and keyboard controls; keep touch scrolling usable. Do not announce every playback tick through a live region.

Required proof: hand-labelled detector cases (strict thresholds, ties, gaps, day boundaries, overlap/chunking), database revision/deduplication/restart tests, HTTP contract checks, and frontend catalogue/filter/replay/share/BatteryLab tests. Include complete, incomplete, no-event and missing-optional fixtures. Finish with one real bounded ingestion→detection→publication→replay→BatteryLab rehearsal and a demo-matched visual review. Record measured payload/render/playback behavior on the supported maximum window; optimize from evidence rather than inventing service guarantees.

### Order of work

1. NEM-054 freezes the evidence-backed scope, detector rules, bounds and fixture contract.
2. NEM-055/056 build grid persistence and worker ingestion; NEM-057 builds pure detectors. NEM-060 builds the demo-faithful UI early after NEM-054, independently of backend completion.
3. NEM-058 publishes immutable events/replays; NEM-059 exposes the contract and public endpoints.
4. NEM-061 connects the UI and playback to real stored data; NEM-062 completes saved links and the BatteryLab handoff.
5. NEM-063 rehearses operator workflows and decides Admin scope. NEM-064 reviews M5 acceptance and remaining M6 gates.

Admin is an explicit assessment, not a hidden requirement to build another app. See [Admin](admin.md#m5-assessment-plan--2026-09-25). The next implementation task is NEM-054; this planning update does not begin ingestion, feature implementation or public deployment.
