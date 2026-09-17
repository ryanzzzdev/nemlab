# NEMLab backlog

Updated: 2026-09-17

Task sections own status. The index is navigation, not a second status tracker. Next: NEM-009 implements the core and fixed schedule, then NEM-010 evaluates the solver. Earlier illustrative IDs did not create tasks.

NEM-011 onward are milestone-level planning packages: split them into focused tasks with new IDs before execution, preserving the original package and dependency links. Do not treat their broad acceptance criteria as a one-session assignment.

## Task index

- [NEM-001 — Establish initial project planning documents](#nem-001)
- [NEM-002 — Define the OE sample plan and check access](#nem-002)
- [NEM-003 — Validate one recent price day](#nem-003)
- [NEM-004 — Validate historical price access and publish the price gate](#nem-004)
- [NEM-005 — Validate aligned regional grid series](#nem-005)
- [NEM-006 — Validate facility samples and close the grid gate](#nem-006)
- [NEM-007 — Resolve the Java and build baseline](#nem-007)
- [NEM-008 — Specify the executable battery model contract](#nem-008)
- [NEM-009 — Implement and verify the domain model and fixed schedule](#nem-009)
- [NEM-010 — Evaluate hindsight optimisation and engine performance](#nem-010)
- [NEM-011 — Establish backend repository and application modules](#nem-011)
- [NEM-012 — Build versioned data ingestion and coverage storage](#nem-012)
- [NEM-013 — Build durable jobs and operator controls](#nem-013)
- [NEM-014 — Define and implement shared API contracts](#nem-014)
- [NEM-015 — Establish frontend workspace and client integration](#nem-015)
- [NEM-016 — Deliver BatteryLab simulation API and stored results](#nem-016)
- [NEM-017 — Deliver the BatteryLab visitor experience](#nem-017)
- [NEM-018 — Deliver GridReplay catalogue and replay](#nem-018)
- [NEM-019 — Assess and optionally deliver Admin UI](#nem-019)
- [NEM-020 — Prepare and verify the initial public release](#nem-020)

<a id="nem-001"></a>

## NEM-001 — Establish initial project planning documents

- Repository: both
- Milestone: Planning setup
- Priority: High
- Status: Done
- Depends on: None
- References: [Specification / decision](documentation-guide.md)

### Outcome

Create a coherent starting plan from the agreed conversation without claiming implementation has begun.

### Done when

- Repository README links to roadmap, architecture, backlog, blockers, all four feature specifications and decisions.
- Immediate tasks have dependencies and acceptance criteria; later work is explicitly subject to refinement.
- Accepted choices and proposals are distinguishable; local links, task references and dependency consistency are checked.

### Completion evidence

Initial planning documents created from the session and existing summaries. Local-link, task-reference and dependency checks passed. Documentation only; files are uncommitted and Git is not yet initialised.

<a id="nem-002"></a>

## NEM-002 — Define the OE sample plan and check access

- Repository: backend
- Milestone: M1
- Priority: High
- Status: Done
- Depends on: None
- References: [Specification / decision](features/data-foundation.md)

### Outcome

Make the first validation requests concrete without committing credentials or assuming coverage.

### Done when

- Record an initial NEM region, an exact recent completed day and a day more than two years ago, with selection rationale and market-time boundaries.
- Record intended endpoints/metrics, expected normalised counts and sanitised evidence layout.
- Verify whether authorised credentials are available without displaying them; if unavailable, record the access hurdle and next secure configuration action.

### Completion evidence

Selected NSW1 with recent 2026-09-11 and historical 2023-09-11 windows. Documented requests, boundary handling, expected counts and evidence layout in the [sample plan](evidence/oe-validation/sample-plan.md). Scoped credential inspection found no configured key; added ignored local configuration guidance. No authenticated requests sent.

### Next action

Configure the local OE key, then continue NEM-003.

<a id="nem-003"></a>

## NEM-003 — Validate one recent price day

- Repository: backend
- Milestone: M1
- Priority: High
- Status: Done
- Depends on: [NEM-002](#nem-002)
- References: [Specification / decision](features/data-foundation.md)

### Outcome

Establish actual price and interval semantics on a recent sample.

### Done when

- Save sanitised request/response evidence and retrieval time for the selected recent day.
- Document units, start/end labels, timezone and inclusive boundaries; account for all 288 expected normalised intervals or every discrepancy.
- Report nulls, duplicates and gaps separately and record pass/fail for use in BatteryLab.

### Completion evidence

Authenticated sample and numerical checks saved in [recent price findings](evidence/oe-validation/recent-price-findings.md). All 288 query-grid values are present and valid. Four AEMO boundary prices establish same-timestamp agreement to OE precision. Corrected interval-end day contains 288 contiguous observations; NEM-003 passed.

### Next action

[BLK-001](blockers.md#blk-001): Credential access now works. Proceed to NEM-004 historical validation; see the resolved findings report.

<a id="nem-004"></a>

## NEM-004 — Validate historical price access and publish the price gate

- Repository: backend
- Milestone: M1
- Priority: High
- Status: Done
- Depends on: [NEM-003](#nem-003)
- References: [Specification / decision](features/data-foundation.md)

### Outcome

Confirm an older usable price sample and define what the engine can safely consume.

### Done when

- Retrieve and document the chosen older date with the same checks as the recent sample.
- Verify what the series represents for its historical settlement regime; exclude ambiguous regimes from initial simulation support.
- Publish a price-gate conclusion listing tested regions/dates, limitations and any required follow-up; do not infer full-history completeness.

### Completion evidence

Historical request succeeded: 289 raw points and 288 valid normalised intervals, including six negative prices. Both sample dates fall after five-minute settlement commencement. Published the [sampled-price gate](evidence/oe-validation/price-gate.md), with explicit historical cross-check and coverage limitations.

<a id="nem-005"></a>

## NEM-005 — Validate aligned regional grid series

- Repository: backend
- Milestone: M1
- Priority: Normal
- Status: Done
- Depends on: [NEM-003](#nem-003)
- References: [Specification / decision](features/data-foundation.md)

### Outcome

Determine which demand, generation and flow inputs support replay.

### Done when

- Sample matching recent/older windows where accessible, recording endpoint/metric support, signs, units and time alignment.
- Spot-check hourly aggregation against five-minute data using each metric’s semantics.
- Record gaps and an explicit core/optional series classification for GridReplay.

### Completion evidence

Twelve requests passed; 31 series/day combinations have complete 288-point source-label grids, and 744 hourly mean checks agree within 0.000001 MW. [Findings](evidence/oe-validation/grid/findings.md) classify supported views and explicitly defer physical-window reconciliation, battery-category overlap and optional metrics to NEM-006.

<a id="nem-006"></a>

## NEM-006 — Validate facility samples and close the grid gate

- Repository: backend
- Milestone: M1
- Priority: Normal
- Status: Done
- Depends on: [NEM-005](#nem-005)
- References: [Specification / decision](features/data-foundation.md)

### Outcome

Establish facility joins and separate required replay evidence from optional metrics.

### Done when

- Discover and sample representative facility/unit codes across technologies; validate metadata joins and missing-versus-zero handling.
- Record optional renewable/curtailment availability or explicit deferral; do not infer named interconnector support.
- Publish the grid-gate conclusion and remaining launch-coverage checks in the evidence report.

### Completion evidence

Discovered 175 NSW1 facilities; sampled six across five technology classes on both dates. All returned unit IDs join to metadata; confirmed sparse/null split-battery representations and exact duplication of populated values. Optional metric samples and scoped exclusions are recorded in the [grid gate](evidence/oe-validation/grid-gate.md).

### Validation follow-up

Resolve or explicitly scope out battery category overlap, signed gas output, metric-specific physical timing and rooftop source resolution identified in [NEM-005](evidence/oe-validation/grid/findings.md) before closing the grid gate.

<a id="nem-007"></a>

## NEM-007 — Resolve the Java and build baseline

- Repository: backend
- Milestone: M2
- Priority: High
- Status: Done
- Depends on: None
- References: [Specification / decision](decisions/004-java-runtime.md)

### Outcome

Choose a reproducible runtime baseline before writing Java build files.

### Done when

- Verify compatible JDK distribution, Spring Boot and Gradle versions from current primary documentation.
- Retain Java 24 preference unless a change is accepted; record the outcome and maintenance implications in decision 004.
- Record pinned version choices and the scope of the minimal engine build.

### Completion evidence

Documented compatibility and selected pins in [decision 004](decisions/004-java-runtime.md): Java 25 explicitly accepted by user; installed Ubuntu OpenJDK 25.0.4+7 verified with java -version; Gradle 9.7.1 and Boot 4.1.1 selected from primary documentation. Minimal core build scope recorded. No project build has run; NEM-009 owns that verification.

<a id="nem-008"></a>

## NEM-008 — Specify the executable battery model contract

- Repository: backend
- Milestone: M2
- Priority: High
- Status: Done
- Depends on: None
- References: [Specification / decision](features/batterylab.md)

### Outcome

Resolve deterministic strategy behaviour and numerical conventions before coding.

### Done when

- Define fixed-schedule power allocation, feasible terminal handling, allowed windows and price-independent behaviour.
- Specify validated inputs, explicit default assumptions, efficiency split, units, tolerances, rounding and missing-price rejection.
- Record illustrative independent fixtures covering negative prices, zero trades, limits and terminal energy; update decision 006 with accepted versus unresolved choices.

### Completion evidence

Specified the [v1 engine contract](features/battery-model-contract.md): deterministic ordered windows, feasible terminal handling, input/default/time rules, accounting and numerical tolerances, solver statuses and independent arithmetic fixtures. [Decision 006](decisions/006-battery-model-contract.md) distinguishes delegated engineering choices from open launch/solver choices. Fixtures are specification evidence; Java tests remain NEM-009.

<a id="nem-009"></a>

## NEM-009 — Implement and verify the domain model and fixed schedule

- Repository: backend
- Milestone: M2
- Priority: High
- Status: Ready
- Depends on: [NEM-007](#nem-007), [NEM-008](#nem-008)
- References: [Specification / decision](features/batterylab.md)

### Outcome

Build the minimal Java proof with a deterministic feasible baseline and independent accounting.

### Done when

- Create the minimal reproducible build and pure Java domain types without API/database dependencies.
- Verify energy conservation, limits, terminal energy, non-simultaneity and cost accounting on independent synthetic fixtures.
- Verify the strategy cannot inspect prices to choose its dispatch, and report infeasible configurations explicitly.

### Completion evidence

Not started; no implementation or verification evidence yet.

<a id="nem-010"></a>

## NEM-010 — Evaluate hindsight optimisation and engine performance

- Repository: backend
- Milestone: M2
- Priority: High
- Status: Backlog
- Depends on: [NEM-004](#nem-004), [NEM-009](#nem-009)
- References: [Specification / decision](features/batterylab.md)

### Outcome

Choose an open-source Java-compatible solver through correctness and runtime evidence.

### Done when

- Record candidate licence/runtime compatibility and a model enforcing charge/discharge exclusivity.
- Cross-check tiny cases against enumerated/manual optima and compare with every feasible baseline under equal constraints.
- Measure 288-interval synthetic and validated historical runs; record time/memory, tolerances, termination statuses and proposed execution limits.
- Document timeout/failure behaviour and the solver choice; do not label unproven results optimal.

### Completion evidence

Not started; no implementation or verification evidence yet.

<a id="nem-011"></a>

## NEM-011 — Establish backend repository and application modules

- Repository: backend
- Milestone: M3
- Priority: High
- Status: Backlog
- Depends on: [NEM-006](#nem-006), [NEM-010](#nem-010)
- References: [Specification / decision](architecture.md)

### Outcome

Refine into implementation tasks for Git setup, module boundaries, API/worker entry points and CI.

### Done when

- Break this package into focused tasks before starting.
- A clean checkout builds/tests both runnable applications with shared domain/infrastructure boundaries and documented commands.
- Repository ignores protect credentials/generated artifacts; dependency pins and relevant CI checks are recorded.

### Completion evidence

Git setup completed early at the user’s request on 2026-09-17: backend repository initialised on main, with documentation and OE evidence prepared for the initial commit. Application modules, build and CI remain outstanding; this package is not Done.

<a id="nem-012"></a>

## NEM-012 — Build versioned data ingestion and coverage storage

- Repository: backend
- Milestone: M3
- Priority: High
- Status: Backlog
- Depends on: [NEM-011](#nem-011)
- References: [Specification / decision](features/data-foundation.md)

### Outcome

Refine migrations, source provenance, observation versions, bounded polling and backfills.

### Done when

- Break this package into migration, ingestion and coverage tasks before starting.
- Repeat imports remain idempotent and interrupted backfills resume safely.
- Coverage/gaps/revisions are visible and immutable simulation snapshots survive data refreshes.

### Completion evidence

Not started; no implementation or verification evidence yet.

<a id="nem-013"></a>

## NEM-013 — Build durable jobs and operator controls

- Repository: backend
- Milestone: M3
- Priority: High
- Status: Backlog
- Depends on: [NEM-011](#nem-011)
- References: [Specification / decision](architecture.md)

### Outcome

Refine database jobs, retries, leases, idempotency and protected refresh/status operations.

### Done when

- Break this package into focused job and operator tasks before starting.
- Schedule and manual requests share one execution path; expired claims recover without stale workers committing results.
- Concurrency/retries are bounded, failed jobs have actionable diagnostics, and administrative actions are authorised and audited.

### Completion evidence

Not started; no implementation or verification evidence yet.

<a id="nem-014"></a>

## NEM-014 — Define and implement shared API contracts

- Repository: backend
- Milestone: M3
- Priority: Normal
- Status: Backlog
- Depends on: [NEM-012](#nem-012), [NEM-013](#nem-013)
- References: [Specification / decision](architecture.md)

### Outcome

Refine coverage/series and job contracts with validation, errors and generated client inputs.

### Done when

- Break into bounded endpoint/contract tasks before starting.
- API contract documents units, timestamps, window limits, error shapes and versioning.
- Contract and database integration checks demonstrate coverage retrieval and asynchronous job submission/status.

### Completion evidence

Not started; no implementation or verification evidence yet.

<a id="nem-015"></a>

## NEM-015 — Establish frontend workspace and client integration

- Repository: frontend
- Milestone: M3
- Priority: Normal
- Status: Backlog
- Depends on: [NEM-014](#nem-014)
- References: [Specification / decision](decisions/005-infrastructure-and-frontend.md)

### Outcome

Create the separate frontend repo and validate the proposed stack on one API/chart slice.

### Done when

- Break into repository, UI shell and integration tasks before starting.
- Verify dependency versions/licences, typed API integration and a shared time-axis/cursor prototype.
- Add project instructions linking to canonical backend docs; reserve Admin structure without creating an empty application.

### Completion evidence

Not started; no implementation or verification evidence yet.

<a id="nem-016"></a>

## NEM-016 — Deliver BatteryLab simulation API and stored results

- Repository: backend
- Milestone: M4
- Priority: High
- Status: Backlog
- Depends on: [NEM-010](#nem-010), [NEM-014](#nem-014)
- References: [Specification / decision](features/batterylab.md)

### Outcome

Refine scenario validation, queued execution, immutable result storage and retrieval.

### Done when

- Break into scenario, execution and result tasks before starting.
- Save reproducible inputs, model versions, solver status, dispatch and accounting; refreshes do not mutate saved runs.
- Integration checks cover invalid inputs, gaps, deduplication, completion and failure/timeout.

### Completion evidence

Not started; no implementation or verification evidence yet.

<a id="nem-017"></a>

## NEM-017 — Deliver the BatteryLab visitor experience

- Repository: frontend
- Milestone: M4
- Priority: High
- Status: Backlog
- Depends on: [NEM-015](#nem-015), [NEM-016](#nem-016)
- References: [Specification / decision](features/batterylab.md)

### Outcome

Refine forms, comparison views, synchronised charts, methodology and shareable results.

### Done when

- Break into focused UI and browser-workflow tasks before starting.
- A visitor completes and reopens a scenario with clear units, financial breakdown and constraint explanations.
- Accessible controls and meaningful loading/error states pass browser checks; chart values agree with backend results.

### Completion evidence

Not started; no implementation or verification evidence yet.

<a id="nem-018"></a>

## NEM-018 — Deliver GridReplay catalogue and replay

- Repository: both
- Milestone: M5
- Priority: High
- Status: Backlog
- Depends on: [NEM-006](#nem-006), [NEM-017](#nem-017)
- References: [Specification / decision](features/gridreplay.md)

### Outcome

Refine detector definitions, versioned events, catalogue API and replay frontend into separate repository tasks.

### Done when

- Finalise supported region/window, event definitions and thresholds based on data evidence before implementation.
- Detectors pass labelled fixtures, gap/overlap handling and reproducibility checks.
- Catalogue, aligned replay and navigation into the correct BatteryLab day pass an end-to-end browser check.

### Completion evidence

Not started; no implementation or verification evidence yet.

<a id="nem-019"></a>

## NEM-019 — Assess and optionally deliver Admin UI

- Repository: both
- Milestone: M5
- Priority: Normal
- Status: Backlog
- Depends on: [NEM-013](#nem-013), [NEM-018](#nem-018)
- References: [Specification / decision](features/admin.md)

### Outcome

Decide whether a minimal UI is needed before launch and record a usable operational path.

### Done when

- Rehearse coverage inspection, bounded refresh and failed-job retry through existing controls.
- Record the include/defer decision with rationale. If included, split into focused tasks and validate authentication/audit/UI flows.
- If deferred, document and verify equivalent operator procedures; do not mark a nonexistent Admin UI delivered.

### Completion evidence

Not started; no implementation or verification evidence yet.

<a id="nem-020"></a>

## NEM-020 — Prepare and verify the initial public release

- Repository: both
- Milestone: M6
- Priority: High
- Status: Backlog
- Depends on: [NEM-018](#nem-018), [NEM-019](#nem-019)
- References: [Specification / decision](roadmap.md)

### Outcome

Refine deployment, quotas, identity, monitoring, recovery, coverage and release checks.

### Done when

- Split into launch tasks with a hosting/budget decision and measured resource limits.
- Verify promised data coverage, methodology/attribution, both visitor journeys, operator recovery and backup restore.
- Document deployment/rollback and run deployment-environment smoke checks; publish only under applicable user authorisation.

### Completion evidence

Not started; no implementation or verification evidence yet.
