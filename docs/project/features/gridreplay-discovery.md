# GridReplay discovery and detector v2 delivery plan

Date: 2026-10-08
Status: Accepted product direction; detailed implementation defaults below selected for planning, with detector-v2 parameters subject to the explicit calibration gate. No implementation in this change.

The user accepted all suggestions from the catalogue review: Highlights + All events, reasons for selection, readable cards, sparklines, sorting/filtering, unusual ramps, price reversals and related negative-price episodes. Preserve the demo's flat card grid, palette and replay composition. Do not reinstate the previously rejected day-grouped cards. Parent context: [GridReplay](gridreplay.md); tasks [NEM-083–NEM-091](../backlog.md#gridreplay-discovery-tasks).

## Observed problem and desired outcome

The reviewed NSW1 September 2023 publication contains 99 events: 68 negative-price runs, 30 daily demand ramps and one spike. Its newest-first feed gives daily routine and exceptional episodes the same prominence. Existing interesting candidates include the September 4 spike to 16,599.89 AUD/MWh and September 16 negative run lasting 9 h 5 min. Counts and values were read from all live cards; they are not an independent provider-data audit.

A visitor should immediately see a few worthwhile investigations, understand why they were chosen, and still be able to inspect every detected event. Success is a demonstrably smaller, varied default selection with truthful reasons and unchanged access to original evidence—not producing more events or claiming every month is exceptional.

## Delivery sequence

- **Release A — discovery over existing v1 events:** NEM-083 corrects duration semantics; NEM-084 provides selection/sorts/filters; NEM-085 builds Highlights and All events; NEM-086 adds bounded preview charts. No detector rerun is required for this release.
- **Release B — new event definitions:** NEM-087 validates/calibrates the three v2 candidates; NEM-088–090 implement and integrate them independently. The current UI remains usable if a candidate lacks adequate data. Each task includes its own type-specific API/UI behavior.
- **NEM-091** records both acceptance checkpoints; Release A can ship locally before B. This extension does not retrospectively reopen the original M5 feature or close hosting/launch gates.

Next: NEM-083, then NEM-084. Calibration may start independently using existing stored evidence, but broader source imports are bounded operator actions and not a consequence of a catalogue read.

## Release A: exact selection behavior

### Scope, candidates and reasons

One request resolves a single publication, region and inclusive NEM date range. Reuse existing event-overlap semantics and show the actual publication coverage. Apply type and numeric filters before ranking. Work over the complete matching publication, not the first 24 events loaded in the browser.

Use these candidate lists, with no mixed-unit score:

| Reason | Eligible type | Ordering |
| --- | --- | --- |
| Highest price | Price spike | Peak descending, duration descending |
| Longest negative run | Negative-price run | Duration descending, minimum price ascending |
| Deepest negative price | Negative-price run | Minimum price ascending, duration descending |
| Largest demand rise | Demand ramp | Rise in MW descending |

All orderings then use start time descending and immutable ID descending to break ties, matching the existing newest-first convention. Rank using exact stored numeric values, not rounded card labels. Rankings identify the published candidate population; they do not establish rarity across the NEM or beyond the selected period.

Selection version `highlights-v1`:

1. Build ranked lists for the active types from complete, non-edge-incomplete eligible event versions in the pinned publication. Unknown coverage is not assumed complete.
2. Round-robin through Highest price → Longest negative run → Largest demand rise → Deepest negative price. Add the highest remaining candidate that meets the diversity limits; skip an exhausted list. Continue until no candidate can be added or eight distinct events are selected.
3. Limit to two spike events, two ramps and four negative runs, with at most two cards assigned to the same start market day. If a type filter is selected, retain its cap; Highlights remains a small selection and All events exposes the rest. Do not fill to eight with unsuitable candidates.
4. Deduplicate by immutable event ID and logical event identity within the publication. A card may carry multiple factual reasons, e.g. first in both duration and depth; it never occupies two slots. Candidates skipped because of a date/type cap keep their true ranks—never relabel the third-longest as the longest.
5. Cross-midnight events count against their recorded start market day. Preserve existing event identity and boundaries. V1 diversity is deliberately simple; do not merge distinct events or invent similarity models.

Highlight labels should be explicit: “Longest published run in this selection”, “#2 demand rise among 30 eligible events”. Display the selection scope, eligible counts and any excluded/incomplete coverage. If no events qualify, say so and offer All events; never manufacture a highlight. Completeness of one event does not establish complete month-wide coverage. “Longest this month” without the published/coverage qualification requires separate evidence of the whole comparison domain.

Changing the selection policy later changes `selectionVersion`, not `detectorVersion` or saved event IDs. An old event link always opens its immutable evidence even if it is no longer highlighted.

### API and data responsibilities

Extend the current Python FastAPI/PostgreSQL catalogue, not the retired Java implementation. Proposed concrete contract:

- `GET /api/v1/events/highlights`: existing region/type/from/to scope plus the applicable numeric filters; optional publication ID to stay on a pinned view. Return publication, selectionVersion, scope, matching total, per-type totals, eligible/excluded counts and up to eight event summaries with reason codes, rank, population count and exact metric value. Register this static route before `/{id}`. Reads never import/detect/publish.
- Extend `GET /api/v1/events` with `sort` and validated type-specific numeric filters. Preserve existing default newest-first behavior for clients that omit them. Return matching totals/per-type counts independently of page size. Provide a publication pin for consistent mode switches; reset it only on an explicit fresh search.
- Bind new cursors to publication, normalized query/filter/sort and final sort tuple. Reject mismatched reuse, malformed cursors and unsupported combinations. Keep existing cursor compatibility explicitly versioned during rollout; stable publication pagination must survive concurrent republication.
- Define shared server-side query/rank functions so Highlights and All events agree on scope and eligibility. Full All events results retain incomplete/edge events and clearly label them; highlight eligibility does not silently remove archive records.
- Update OpenAPI, generated frontend types and HTTP captures. Index/measure queries against the maximum supported publication size; do not issue one replay query per candidate or load every full replay to rank summaries.

Per-type options:

| View/type | Sorts | Filters |
| --- | --- | --- |
| All types | Newest first / oldest first | Region and inclusive NEM dates |
| Negative run | Newest / longest / deepest | Minimum duration in minutes; minimum price at or below a signed AUD/MWh value |
| Spike | Newest / highest peak / longest | Minimum duration; peak price at or above AUD/MWh value |
| Demand ramp | Newest / largest rise | Minimum rise in MW; no meaningless duration control for the fixed three-hour rule |

Numeric boundaries are inclusive. Exact decimal strings and nonnegative duration/magnitude validation follow existing API conventions. Unsupported type/filter combinations return clear validation errors. Switching type in the UI clears incompatible filters and resets pagination. Defaults impose no additional numeric filters. Keep filters in an optional “More filters” area to retain the compact demo row. Counts reflect the active filters and state that scope; do not label a publication's total as the current filtered count.

### UI and URL contract

- Add Highlights / All events next to the catalogue heading; fresh visits default to Highlights. Preserve region/type/from/to and Update list in the demo-style filter row.
- Show “N highlights from M matching events”, a compact per-type count summary and scope/coverage context. All events retains the dense grid and bounded Show more pagination.
- Card order: type badge → useful headline/primary figure → factual reason if highlighted → NEM date/time and readable duration → optional sparkline. Negative prices read “9 h 5 min below zero”, with minimum price including AUD/MWh. Use hours/minutes consistently and avoid repeated figures on several lines.
- Routine detector/version/source detail moves into existing replay provenance. Material missing/edge coverage remains visible on cards. Do not invent weather or causal headlines.
- Preserve the replay below the catalogue, selected-card indication, keyboard semantics, theme switch and current chart controls. Filters/mode changes must not erase an already opened saved event; show a small “Outside this selection” notice when appropriate.
- Encode view, type, dates, sort and numeric filters in URL state. Existing `event` links still open immediately; keep any supported replay cursor/window state. Invalid filters have a recovery message and do not trigger imports. Back/Forward restores selection state; hover/playback does not flood history.
- Match the demo visually at desktop, 768px, 390px and 320px. Light/Dark/Auto, loading, no matches, no eligible highlights, incomplete context and long labels all need review through computer use.

### Preview sparklines

Use an event-local preview of price for negative/spike cards and demand for ramps. Display event shading within a documented context window, recommended one hour before/after where retained snapshot coverage permits. Preview data comes from that immutable event snapshot; omit a preview when context is unavailable rather than substituting current data.

Build preview summaries at publication time or lazily cache a bounded result keyed by event ID plus preview-version. Do not download four full replay series per catalogue card. Cap points, serialized response size and concurrent fetches; choose/measure final budgets in NEM-086. A practical starting point is at most 96 plotted points and a small per-card payload; preserve extrema, event edges and gap markers using a documented reduction method. If complex gaps exceed the budget, simplify context or omit the preview, never join across gaps.

Use common units, visible min/max/context duration and an explicit “local scale” label if cards auto-scale. Preview shapes must not imply equal magnitudes or timespans. Keep textual values sufficient for keyboard/screen-reader use; loading/failure of a decorative preview must not block opening a card or change ranking. Reuse lightweight SVG where suitable; no new chart library is needed for sparklines.

### Duration correction

Current `api/src/nemlab_api/events.py::_item` computes `durationMinutes = interval_count * 5` for every type. That correctly counts five-minute price intervals but turns 37 demand observations into 185 minutes, although the endpoints are 180 minutes apart.

NEM-083 makes duration metric-specific: ramp = elapsed source-label endpoints (180 minutes for v1); price run/spike = qualifying interval count × five minutes. Label ramps “37 observations · 3 h”, prices “N intervals · …”. Preserve event IDs, stored input snapshots and detector versions: this is a projection/presentation correction, not a reason to rewrite historical event rows. Review all endpoint/card/provenance consumers and update contract descriptions/tests. Distinguish publication `endExclusive` from inclusive displayed coverage dates as part of the same boundary-copy check.

## Release B: versioned detector candidates

The user accepted these feature directions, not empirical proof of parameter quality. NEM-087 evaluates the concrete starting settings below against labelled fixtures and available real evidence, records event counts/examples and freezes exact rules before production implementation. Do not keep changing thresholds until an arbitrary desired number of events appears. Existing v1 events and saved links remain readable; operator publication of new types is explicit and auditable.

### Unusually large demand ramps — NEM-088

Keep the existing daily ramp as the source candidate, and classify whether its magnitude is unusual relative to a same-region historical reference. Initial calibration settings: preceding 90 NEM days (exclude candidate day/future days), at least 60 complete days overall and 20 of the same weekday/weekend class; compare against that class's daily maximum positive three-hour changes. Include complete nonpositive days as zero when building this distribution; omit missing/ineligible days rather than substituting zero. Proposed qualification: strictly above nearest-rank P90 and at least a configured absolute rise (initial NSW1 candidate 1,000 MW).

Freeze reference selection, quantile method, completeness minimums and absolute floor in detector parameters. Retain baseline dates, sample count, quantile and source revision manifest with the result. Equality to P90 does not qualify; ties are deterministic. Without enough baseline, return insufficient baseline, not “normal” or a fallback rare event. September alone does not establish this baseline; wider collection is a separate bounded import decision. In All events, retain daily ramps; default highlights prefer the unusual version and suppress duplicate cards for its underlying daily ramp. Explain “above 90% of comparable daily ramps in [reference period]”, not “rare across the NEM”.

### Negative-to-high price reversal — NEM-089

Initial calibration rule: a complete v1 negative run (at least 15 minutes below zero), followed after its final interval by a price at least 300 AUD/MWh within six hours, with a trough-to-peak rise of at least 300 AUD/MWh. Require all five-minute prices throughout the negative run and look-ahead window; missing observations/source edges withhold the complete reversal claim. Use the highest qualifying subsequent price, earliest on ties. No earlier high price qualifies, no equality ambiguity (>= 300, elapsed <= 6 h).

If several negative runs lead to the same peak, select the candidate with the largest rise, then earliest negative-run start; retain related run IDs in evidence. Other overlap cases get explicit labelled fixtures and a frozen deduplication rule in NEM-087. Record full observation window, trough, peak and elapsed time, with cross-midnight ownership by start day. Replay highlights both phases. “From negative prices to $X/MWh in Y hours” is an observation, not a battery profit claim or a causal assertion. BatteryLab handoff still selects one explicit day and never auto-runs.

### Related negative-price episodes — NEM-090

Provide a compound exploration event alongside original runs; do not silently change v1's definition of consecutive negative intervals. Initial settings to calibrate: join consecutive complete negative runs when the intervening span is at most 15 minutes, every intervening observation is present and nonnegative but no greater than 50 AUD/MWh, and cumulative joined nonnegative time is at most 30 minutes. Require at least two original runs. One missing observation prevents joining. Never count intervening nonnegative time as time below zero.

Define and test gap duration using price interval boundaries (not subtracting endpoint labels incorrectly). Group left-to-right deterministically over full context, not separately per paginated day, retaining cross-midnight behavior and explicit source-edge completeness. Display “X negative-price episodes across Y h” with actual negative duration, intervening duration, span, low and member IDs. Replay shades member intervals separately. Highlights may choose the compound event and suppress its constituent cards in that selection; All events can still access originals and the relationship. This is event grouping, not a return to day-grouped card layout.

### Shared v2 integration

Each new type has an explicit immutable type/version/configuration and preserved source/baseline provenance, snapshots, hand-labelled tests and corrected-source/republication behavior. Integrate public enum/schema, typed filters, card/replay explanation and methodology in the same task; do not expose an unrenderable type. Old clients need a documented compatibility/error policy before publication.

Extend highlight selection as `highlights-v2`, with calibrated per-type limits and overlap suppression. Preserve reasons in their own units; no global opaque score. A reversal or compound episode may replace linked simple events in Highlights, while All events remains complete. Preserve total counts by type and make any hiding in Highlights explicit. Final cross-type slot priorities are frozen with NEM-087 examples, rather than automatically giving every new type eight more cards.

## Acceptance and evidence

Release A: hand-labelled ranking fixtures prove whole-publication ranking, deterministic ties, query binding, per-type/date caps, deduplication/multiple reasons, incomplete coverage and empty results. HTTP checks cover exact filters, invalid combinations, publication changes and pagination; frontend checks cover default/saved URLs, modes, filters, selected events, themes and responsive layout. Real September review should visibly surface the known spike and longest negative run despite their older dates; verify magnitudes against returned exact values, not hard-coded display expectations. Compare before/after screenshots and record highlighted counts/reasons. No claim of engagement improvement without measurement.

Release B: independently labelled boundary/gap/tie/baseline/overlap fixtures, version/deduplication/storage tests, API/browser/live checks for each added type, and real examples with honest insufficient-data cases. Do not claim unusual ramps are verified from one month without their reference history. Keep operator-triggered imports/publication bounded and old replay URLs reproducible.

Measure query count/latency, page/preview bytes and mobile rendering on representative catalogue sizes; set final budgets from the recorded baseline and verify no per-card full-replay fan-out. Run required backend Python checks, contract verification and frontend `npm run check`; real API/worker/PostgreSQL journey tests at each integrated release. NEM-091 records outcomes, limitations and any follow-up without conflating local acceptance with hosted deployment.
