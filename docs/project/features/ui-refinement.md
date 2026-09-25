# BatteryLab results and standalone price exploration

Date: 2026-09-25

Status: Accepted direction, implemented by NEM-047 and NEM-048 in frontend `ef4c25f`. The demo remains the visual reference; deliberate deviations keep the shared site header/theme picker, the demo-incompatible ordering requested below, window shading and the exact readout/interval tables.

## Context

After NEM-044–NEM-046, BatteryLab has working comparison charts, financial and interval tables, saved results and visitor-triggered price refresh. The current result and price charts are hidden behind explicit show/hide buttons. The stored-price explorer is embedded in BatteryLab and still includes an explicitly synthetic energy trace from NEM-036.

The user requested automatically visible comparison charts, financial breakdown above the charts, collapsible interval detail like methodology, and moving stored-price exploration to a separate page with automatically visible charts.

## BatteryLab result hierarchy — NEM-047

### Primary visual reference — accepted user direction

The user explicitly prefers the [BatteryLab demo](../../demos/batterylab/index.html) to the current real page. Make the real page as close to that demo as practical, not merely loosely inspired by it. Match input styling and grouping, field density, button styling and placement, section locations, spacing, typography, borders and panel treatments. Use the demo's compact scenario column beside the results (320px column / 20px gap as the desktop reference), within the accepted centered layout; stack naturally on smaller screens.

Treat charts as part of the same visual system: each chart sits in a consistently styled panel with compact title/legend, matching surfaces, padding, borders, radius and typography. Match the demo's line styles, colors and chart proportions where compatible with clear series distinction and the shared dark/light/auto themes. Avoid a visually separate plotting widget or oversized standalone progress card. Keep the page header compact so the working interface appears promptly.

The primary simulation button belongs in the scenario panel at the demo's action location. Immediately below it, group simulation ID, status/progress, data source/revision and Copy link as compact secondary content/actions in that same panel. Stop/resume/retry controls, when applicable, belong in this area too. Keep technical metadata visually quiet with smaller readable text and subdued colors; long identifiers must wrap or be expandable without widening the panel. Do not duplicate these details above the result charts. Errors requiring action remain clearly visible and announced; secondary styling must not hide failures or make text inaccessible.

This placement follows the user's latest instruction even where the demo itself places a secondary button beside Run. Preserve working API states and sharing behavior rather than copying mocked execution. The original demo remains unchanged.

### Result-column order

1. Summary figures and short strategy explanations. Simulation identity/status/source/share controls live under the simulation button in the scenario panel, not at the top of this column.
2. Financial breakdown, expanded and compact, above the charts.
3. Comparison charts: price, grid-side power, stored energy and cumulative margin, automatically rendered for every available result, including saved-link reopening. Remove the show/hide chart button; retain shared cursor/window controls and theme support.
4. Interval detail in a native `details` disclosure, closed initially, with a descriptive summary such as “Interval detail · 288 five-minute intervals”. Keep the complete accessible table and exact price strings.
5. Methodology and scope, collapsed as today.

“Always show charts” means no opt-in once result data exists. Do not invent a trajectory or present an old result as the newly edited scenario. Before the first result, retain an explanatory empty state. During result loading, reserve chart space with a clear loading state; chunk loading can remain lazy internally without requiring a user click. If charts fail, retain the financial breakdown and provide a direct way to open interval detail.

The latest user direction supersedes the earlier suggestion to distribute identity/source/version metadata across the results and methodology: keep simulation-related technical information together beneath the simulation button, optionally in an expandable detail within that secondary area. Methodology remains for model assumptions and interpretation. Region/day remain clear in the scenario inputs. A labelled example result could improve first arrival later, but only if backed by a real saved result; example sourcing and automatic simulation are outside this task.

Match the demo closely except for the explicitly requested refinements: financial breakdown above charts, always-visible available charts, collapsed interval detail, separate Prices page, and the simulation metadata/action grouping above. These newer instructions take precedence over the demo's original ordering.

## Separate price exploration — NEM-048

Move the existing explorer out of BatteryLab into a directly navigable, reloadable page. Suggested route and public label: `/prices`, “Prices” in the main navigation, with page heading “Explore electricity prices”. Keep “stored” as coverage/source context rather than the feature's primary name. Use the shared centered layout and appearance control.

Suggested page order: region/day controls → coverage and concise day summary → automatically visible price chart → collapsed exact interval table → source/revision details. Charts appear whenever an imported series is available, even when incomplete; gaps must remain gaps. Show clear loading, unavailable and failure states, with no show/hide chart button.

Recommended scope: remove the synthetic energy trace from this visitor-facing page; it was an interaction proof, not market information. Retain the real price curve, negative-price visibility, selected-interval readout, keyboard controls and visible-window control. These naming, table-disclosure and synthetic-trace removal details are recommendations for the implementation plan.

Preserve the price explorer's read-only semantics. Moving it must not silently give “Check prices” the simulation endpoint's visitor-refresh behavior. BatteryLab's own price fetching remains part of scenario submission and does not depend on visiting Prices. An optional “Explore this day's prices” link can pass region/day, but is not required for the first move. Keep saved simulation charts tied to their immutable embedded prices, not the Prices page's current revision.

## Delivery and verification

### Follow-up: three strategies by default — NEM-052

Following delivery of the original refinements and the threshold engine, the user accepted promoting Price thresholds to an equally prominent third strategy — implemented in frontend `5d4a82c` (NEM-052). New scenarios submit thresholds unconditionally with both fields visible and illustrative defaults; the opt-in checkbox is removed. Schedule windows are labelled as fixed-schedule/hindsight-only beside the all-day threshold fields. Old two-strategy saved results reopen unchanged with an explicit "Compare all three" path. See the [accepted threshold UX revision](price-threshold-strategy.md#accepted-ux-revision--2026-09-25-pending-nem-052); threshold-only mode remains deferred.

Verification must cover fresh three-strategy runs, explicit conversion of old two-strategy results into a new scenario, unchanged saved-link replay, input grouping/labels, all three result series and clear ending-energy differences at desktop/mobile widths and in both themes.

### Original refinement delivery sequence

- First implement NEM-047: align the real BatteryLab page closely with the demo, including inputs/actions, panel/chart styling and secondary simulation details beneath Run; reorder result content, remove the comparison-chart toggle and collapse interval details. Update affected browser/live assertions.
- Then implement NEM-048: move price exploration to its route, remove its toggle and replace the prototype presentation with a real-price view. Update navigation, direct-load/reload and price/chart tests to use the new route.
- Verify desktop, 320px/mobile and both themes; keyboard disclosure behavior; automatic chart rendering on fresh and reopened results; synchronized chart controls; loading/chunk failures; exact-table access; incomplete/missing price days; and unchanged saved-result accounting and price-refresh behavior.
- Review the demo and real-page screenshots side by side at matched desktop/mobile widths. Check field grouping/density, button positions, metadata placement, panel consistency and chart integration, as well as hierarchy and chart prominence. Document intentional differences required by the newer instructions or accessibility. Keep the financial table compact enough that it does not dominate the result column above the charts.
- These are post-M4 UX refinements. Preserve historical acceptance evidence; do not reopen backend correctness work or imply hosted CI/public launch completion.
