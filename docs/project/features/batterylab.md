# BatteryLab

Updated: 2026-09-17  
Status: Proposed detailed specification; BatteryLab's place before GridReplay is accepted.

## Visitor outcome

Accepted follow-up UX direction (2026-09-25): new scenarios should present Fixed schedule, Price thresholds and Perfect hindsight as three default strategies, with shared battery inputs, schedule-only windows and separate all-day threshold settings. NEM-052 owns the change; the current shipped UI still uses an optional threshold checkbox. Old saved results remain faithful to their original strategies. See the [threshold UX revision](price-threshold-strategy.md#accepted-ux-revision--2026-09-25-pending-nem-052).

Implemented UX refinement (2026-09-25, frontend `ef4c25f`): automatically visible comparison charts in consistently styled panels, financial breakdown above charts, collapsed interval detail and standalone price exploration at `/prices`. See the [UX plan](ui-refinement.md) and NEM-047–NEM-048.

Accepted visual direction, now implemented: the BatteryLab page closely reproduces the demo's field/button styling and placement, compact layout and consistent panel/chart design. Simulation ID, status, source details and Copy link sit directly beneath the simulation button as secondary content in the scenario panel. Accessible error/progress behavior is preserved.

Accepted visual direction (2026-09-24): a centered 1160px workspace with a scenario-side column, compact result cards and teal accents, taking the light mock as the reference. Shared Light/Dark/Auto applies to this and the GridReplay page; Auto follows the device. See [decision 018](../decisions/018-product-layouts-and-appearance.md). NEM-042 establishes the layout with existing stored-price exploration; the scenario form and actual comparison remain NEM-043–NEM-045.

Configure a battery for a historical market day and understand its simulated energy-trading margin under a fixed schedule and perfect hindsight. Working audience assumption: energy-curious visitors and employers evaluating the engineering; specialised investment workflows are deferred.

## First complete journey

NEM-043 implements the accepted layout revision after UI review: BatteryLab keeps its 1160px centered workspace, both products share aligned header/navigation, and GridReplay is centered with a wider 1440px cap. See [decision 018](../decisions/018-product-layouts-and-appearance.md).

Choose an available region/day, adjust site inputs, submit the scenario, follow job status, and compare results. Inspect price, charging/discharging power, stored energy and cumulative margin with a shared cursor. Open the financial breakdown and methodology, then share a link that reproduces the saved inputs/results.

Use a curated example to make the first result understandable without configuring every advanced field. Illustrative defaults are in the engine contract; final launch presets and initial dates remain UI/coverage choices; do not turn illustrative values into recommended real-world assumptions.

A static mocked-data prototype of this journey lives at [docs/demos/batterylab/index.html](../../demos/batterylab/index.html). It previews the form, job lifecycle, comparison, charts, breakdown and share link with a JavaScript port of the engine; it is a visualisation aid, not the NEM-017 frontend.

## Inputs and domain rules

One aggregate site with separate total charge/discharge MW, energy capacity MWh, import/export connection limits, efficiencies, minimum/maximum/initial stored energy, operating windows, and selected variable fees/degradation. Identical battery count may scale power and capacity before applying shared connection limits. The terminal energy equals initial energy in the initial comparison.

The [M2 engine contract](battery-model-contract.md) defines implementation rules, illustrative defaults, validation and reference fixtures. It refines the earlier [mathematical proposal](../../initial-ideas/battery-arbitrage-details.md). Implementation must enforce:

- `E[t] = E[t-1] + eta_c*c[t] - d[t]/eta_d`, with grid-side imported/exported MWh and explicit interval duration.
- Energy/power/connection bounds and mutually exclusive charge/discharge in every interval.
- Separate conversion losses from financial fees; do not charge for efficiency twice.
- Negative purchase prices produce a charging credit; negative sale prices reduce revenue.
- Finite valid inputs, efficiencies in `(0, 1]`, and feasible initial/terminal conditions. Reject invalid configuration with field-level errors.

If accepting round-trip efficiency, the proposed split is `eta_c = eta_d = sqrt(round_trip_efficiency)`. Record numerical tolerances and rounding rules in the implementation model contract. Use internal precision for computation, then round display values; independently recompute accounting from dispatch.

## Strategies and fair comparison

Fixed schedule uses predetermined windows and a deterministic policy selected before evaluating prices. Its power allocation and terminal-energy handling are specified in the [M2 engine contract](battery-model-contract.md); it must not use future prices to repair an infeasible ending. Report infeasible policies explicitly or prevent them through a price-independent feasibility rule. Do not silently replace a losing schedule with no trading.

Hindsight sees the whole day and optimises margin under the same physical/cost/terminal constraints. It may choose no trading. Prevent simultaneous charging/discharging explicitly, including negative-price cases where an unconstrained relaxation could reward energy dissipation.

Use common windows for an equal-constraint comparison. If also showing unrestricted hindsight against restricted scheduled operation, label the different operating opportunities. Only claim an optimal upper bound if optimality is established within the documented tolerance. A solver timeout with a feasible result is not automatically perfect hindsight; initial UI may simply report the comparison unavailable and allow retry.

## Results and failure states

Persist normalised inputs, exact price snapshot, model/strategy versions, solver termination status, interval dispatch/energy, revenue, charging cost/credit, fees, degradation and total margin. Report energy losses as a physical quantity. Explanations must be derived from computed limits and timing.

UI states: invalid input; fetching prices for an uncovered day; queued; running; complete; failed/timed out; fetch exhausted or fetch queue saturated; missing or expired shared result. Long work is asynchronous; retries must not create uncontrolled duplicate jobs. Public run limits and retention are set before launch.

Assume a price-taking wholesale battery. Exclude capital/finance costs, contracts, detailed losses/network charging, FCAS and household tariffs. Results are simulated energy-trading margin, not investment return or actual facility revenue.

## Acceptance criteria

- Independent tests cover energy conservation, terminal energy, all limits, zero/negative prices, no simultaneous operation, and financial reconciliation.
- Small enumerated cases support optimality checks; a feasible fixed schedule never beats a proven optimum under identical constraints beyond tolerance.
- Incomplete price days cannot yield an apparently complete simulation.
- Reloading a shared result preserves its input data even after OE revisions.
- Charts and totals agree; keyboard-accessible controls, clear units and meaningful loading/error states support the full browser journey.

Price thresholds are a default third strategy (2026-09-25, NEM-052): every new scenario submits two signed-decimal thresholds and the worker replays an all-day "charge below / discharge above, else hold" rule alongside the fixed/hindsight pair. Older two-strategy saved results reopen unchanged with an explicit compare-all-three path. See the [threshold strategy record](price-threshold-strategy.md) and NEM-049–NEM-051. It is an idealised same-interval replay that may end at a different stored energy and is not ranked against the pair. Forecasts, multi-day/annual backtests, multi-asset heterogeneity and investment analysis remain deferred. See [model decision](../decisions/006-battery-model-contract.md), [BLK-004](../blockers.md#blk-004), and [M4](../roadmap.md#m4--batterylab).

## Public shell implementation

NEM-034 adds a `/batterylab` overview in the separate frontend, with explicit unfinished-feature
copy and a methodology link. It contains no data, controls or calculated results. The
full product journey and acceptance criteria above remain future work.

## Stored-price exploration implementation

NEM-043 adds a real aggregate-site scenario form alongside the separate price explorer. It offers round-trip or separate-leg efficiency, exact decimal costs/energy/power, ordered five-minute windows including 24:00, field validation and complete-day coverage checks. Submission progresses through queued/running/succeeded/failed states and retrieves the stored result. Inputs stay locked during monitoring; stop/resume affects browser checking only. Editing inputs clears stale progress/results. Equivalent submissions reuse terminal jobs, including failed jobs. Detailed comparison/charts and saved-link reopening remain NEM-044–NEM-045. A disconnected API produces a clear error, not synthetic results.

NEM-035 adds a bounded region/completed-day price view, now living on the standalone
`/prices` page since NEM-048. It reads coverage before loading the 288 intervals,
preserves exact decimal strings and gap states, and displays source, units and revision
metadata. Loading, unavailable coverage and safe errors are explicit. This read-only
view neither imports data nor runs the battery engine; visitor-triggered refresh under
NEM-046 remains a simulation-submission behaviour, not a price-page behaviour.

NEM-046 changes missing-coverage behaviour for the simulator:
an eligible submitted day without a complete stored revision enqueues a deduplicated price
refresh (`visitor-price-v1:REGION:DAY` keys, three attempts per day, ten pending visitor
jobs globally) and returns `PRICE_REFRESH_PENDING`; the browser resubmits the unchanged
scenario after each `Retry-After` until coverage arrives, the queue cap pauses, or
`PRICE_REFRESH_FAILED` reports exhaustion. Ineligible days keep the explicit rejection.

## Chart interaction proof

NEM-036 proved shared cursor/window selection, fixed-time labels, visible gaps and
text/table alternatives on the price chart. NEM-048 removed the explicitly synthetic
second energy panel: the public price view now renders a single real stored-price
chart automatically whenever a series exists, with the exact interval table in a
collapsed disclosure.


## Simulation request boundary

NEM-039 implements the [request contract](simulation-request-contract.md): exact decimal
parameters, normalised efficiency legs, ordered windows, bounded input validation and
immutable price-revision capture. It defines stable scenario identity without fetching
OE or creating jobs. NEM-040 now implements durable execution/results; NEM-041 now exposes public simulation endpoints. The frontend is not yet a visitor-facing simulator.


## Durable execution and saved comparison

NEM-040 persists exact normalised inputs and their immutable price revision with a durable
job. Equivalent submissions reuse the same job. The independently enabled worker runs both
strategies in a bounded process, validates outputs and atomically stores the comparison and
terminal status. Saved dispatch, energy, accounting, solver status and versions survive
source corrections. Incomplete/unproven solver outcomes remain explicit diagnostic results,
never a successful hindsight comparison. Process failures retry at most three attempts;
resubmitting a terminal failed scenario does not reset it. NEM-041 exposes HTTP submission/status/results while retaining terminal-job deduplication;
there is no public retry-reset operation. The real frontend remains unfinished.


## Public simulation API

NEM-041 completes the backend lifecycle. Visitors can submit a valid scenario via HTTP,
poll its opaque-ID status URL, and reopen the saved proven result. Pending/failed states,
validation errors and unavailable coverage are explicit; worker tokens and raw diagnostics
stay private. The [API guide](../../../api/README.md#public-simulation-lifecycle) defines
transport/error semantics. Forms, progress presentation, real result charts and shared-link
browser journeys remain NEM-017; the existing chart companion is still synthetic.


## Result comparison and linked charts

NEM-044 presents the stored result. Margin stat cards, plain-language explanations
(interval counts, weighted-average prices, the fixed policy's limiting reason, the
hindsight advantage and the solver's dual bound) and a financial breakdown table show
per-strategy imported/exported energy, charging cost (credit when negative), revenue,
fees, degradation and physical losses. Hindsight is labelled a benchmark, not a
forecast. Charts plot approximate numbers; tables and readouts keep stored values.

NEM-047 finalises the result hierarchy after the demo: summary stats and explanations
lead, the financial breakdown sits above the charts, and four chart panels — price with
window/negative bands, grid-side power (a segmented control swaps strategies), stored
energy with site limits, cumulative margin — render automatically in consistent cards
under one cursor and window control. Interval detail and methodology collapse into
native disclosures; the chart toggle is gone. Simulation ID, status chip, price
source/revision, engine versions and monitoring/copy actions live beneath the Run
button in the scenario panel as secondary content.

## Saved-result journey

NEM-045 makes a finished scenario reopenable. A stored result writes its opaque job
ID into the page address (`/batterylab?simulation=<uuid>`), and a keyboard-accessible
"Copy result link" action — beneath the Run button since NEM-047 — copies that
locally constructed URL. Opening the link reads
job status then the immutable result — never resubmitting — restores the stored
scenario inputs into the form and renders the identical comparison; the embedded
price snapshot is unaffected by later source revisions. Links to queued or running
jobs resume monitoring; failed jobs report their safe failure code, and malformed or
unknown identifiers explain the recovery while leaving the form usable. Editing any
input detaches the link so a reload cannot silently resurrect an old result. A
collapsed methodology summary accompanies the comparison. The full journey —
submit, reopen, incomplete-day and unknown/failed recovery — is verified against the
real API, worker and PostgreSQL in the live browser suite.
