# NEMLab backlog

Updated: 2026-10-08

Task sections own status. The index is navigation, not a second status tracker. NEM-037 has reviewed the shared foundation: local implementation evidence passes, but M3 remains in progress until NEM-038 records hosted CI results. NEM-039–NEM-041 complete NEM-016. NEM-017 was delivered as NEM-042–NEM-046: product layouts and appearance, the simulation form/lifecycle, stored comparison/charts, the saved-result journey and visitor-triggered price refresh; M4’s local exit criteria are met. The hosted CI gate remains open under NEM-038 and public launch gates under NEM-020. Earlier illustrative IDs did not create tasks.

NEM-011 onward are milestone-level planning packages: split them into focused tasks with new IDs before execution, preserving the original package and dependency links. Do not treat their broad acceptance criteria as a one-session assignment.

## Task index

Accepted GridReplay discovery extension: [detailed plan](features/gridreplay-discovery.md). All tasks delivered and verified 2026-10-08; see [NEM-091](#nem-091) for checkpoint evidence.

- [NEM-083 — Correct event duration and time-range presentation](#nem-083)
- [NEM-084 — Add publication-wide highlights and typed catalogue filters](#nem-084)
- [NEM-085 — Deliver Highlights and All events in the demo-style UI](#nem-085)
- [NEM-086 — Add bounded immutable event preview charts](#nem-086)
- [NEM-087 — Calibrate and freeze detector v2 definitions](#nem-087)
- [NEM-088 — Detect and explain unusually large demand ramps](#nem-088)
- [NEM-089 — Detect and replay negative-to-high price reversals](#nem-089)
- [NEM-090 — Group related negative-price episodes for exploration](#nem-090)
- [NEM-091 — Verify discovery releases and detector v2 journeys](#nem-091)


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
- [NEM-021 — Backend modules and Boot entry points](#nem-021)
- [NEM-022 — Packaged startup and local setup](#nem-022)
- [NEM-023 — CI and module dependency checks](#nem-023)
- [NEM-024 — PostgreSQL migrations](#nem-024)
- [NEM-025 — OE price retrieval](#nem-025)
- [NEM-026 — Revision/coverage/snapshot storage](#nem-026)
- [NEM-027 — Resumable price backfill](#nem-027)
- [NEM-028 — Durable price-refresh queue and fenced results](#nem-028)
- [NEM-029 — Worker polling and scheduled refresh execution](#nem-029)
- [NEM-030 — Protected operator job controls](#nem-030)
- [NEM-031 — Public stored-price coverage and day series](#nem-031)
- [NEM-032 — Shared OpenAPI contract and generated client inputs](#nem-032)
- [NEM-033 — Frontend repository and reproducible tooling](#nem-033)
- [NEM-034 — Public navigation and UI shell](#nem-034)
- [NEM-035 — Typed stored-price API integration](#nem-035)
- [NEM-036 — Synchronised time-series chart prototype](#nem-036)
- [NEM-037 — Shared-foundation exit review](#nem-037)
- [NEM-038 — Verify hosted foundation CI](#nem-038)
- [NEM-039 — Simulation request contract and validation](#nem-039)
- [NEM-040 — Durable simulation execution and immutable results](#nem-040)
- [NEM-041 — Simulation HTTP lifecycle and generated contract](#nem-041)
- [NEM-042 — Product layouts and shared appearance](#nem-042)
- [NEM-043 — Battery scenario form and simulation lifecycle](#nem-043)
- [NEM-044 — Simulation comparison and linked result charts](#nem-044)
- [NEM-045 — Saved-result journey and BatteryLab acceptance](#nem-045)
- [NEM-046 — Visitor-triggered price refresh](#nem-046)
- [NEM-047 — Make comparison charts part of the default result view](#nem-047)
- [NEM-048 — Separate price exploration from BatteryLab](#nem-048)
- [NEM-049 — Implement the price-threshold engine](#nem-049)
- [NEM-050 — Persist and expose threshold experiments](#nem-050)
- [NEM-051 — Present the threshold experiment](#nem-051)
- [NEM-052 — Make price thresholds a default third strategy](#nem-052)
- [NEM-053 — Polish BatteryLab presentation against the demo](#nem-053)
- [NEM-054 — Freeze GridReplay data scope and detector rules](#nem-054)
- [NEM-055 — Persist versioned GridReplay observations and coverage](#nem-055)
- [NEM-056 — Run bounded grid imports through the worker](#nem-056)
- [NEM-057 — Implement the three deterministic event detectors](#nem-057)
- [NEM-058 — Publish versioned events and reproducible replays](#nem-058)
- [NEM-059 — Expose the GridReplay catalogue and replay contract](#nem-059)
- [NEM-060 — Build the demo-faithful GridReplay interface](#nem-060)
- [NEM-061 — Connect catalogue and synchronized replay to real data](#nem-061)
- [NEM-062 — Share replays and open the correct BatteryLab day](#nem-062)
- [NEM-063 — Rehearse GridReplay operations and decide Admin scope](#nem-063)
- [NEM-064 — Verify the GridReplay journey and M5 exit criteria](#nem-064)
- [NEM-065 — Freeze the Java parity baseline and executable reference cases](#nem-065)
- [NEM-066 — Preserve Java as a runnable reference in the existing repository](#nem-066)
- [NEM-067 — Bootstrap the four Python packages and independent applications](#nem-067)
- [NEM-068 — Port request semantics and deterministic battery strategies](#nem-068)
- [NEM-069 — Prove the Python ordered-hindsight solver and budgets](#nem-069)
- [NEM-070 — Adopt the existing PostgreSQL schema with Alembic](#nem-070)
- [NEM-071 — Port OE prices, immutable revisions and resumable backfill](#nem-071)
- [NEM-072 — Port fenced refresh jobs and visitor admission](#nem-072)
- [NEM-073 — Run isolated price fetches and schedules in the Python worker](#nem-073)
- [NEM-074 — Restore public price reads and protected operator HTTP](#nem-074)
- [NEM-075 — Port immutable simulation inputs, jobs and saved results](#nem-075)
- [NEM-076 — Execute and validate simulations in bounded Python children](#nem-076)
- [NEM-077 — Restore simulation HTTP and visitor-triggered refresh](#nem-077)
- [NEM-078 — Make Python the active local tooling and CI path](#nem-078)
- [NEM-079 — Verify the existing frontend against the Python backend](#nem-079)
- [NEM-080 — Rehearse database cutover and close the Python parity gate](#nem-080)
- [NEM-081 — Research energy-sector roles and refine the Python stack](#nem-081)
- [NEM-082 — Expose grid-observation coverage inspection](#nem-082)
- [NEM-092 — Accept bounded date-range price refreshes](#nem-092)

Post-M4 UX refinement delivered: [NEM-047](#nem-047) aligned BatteryLab's result view with the accepted demo direction and [NEM-048](#nem-048) moved stored-price exploration to `/prices`.

The [price-threshold strategy](features/price-threshold-strategy.md) was delivered through NEM-049–NEM-051 and promoted to a default third strategy in NEM-052. Commercial-grade market realism is explicitly outside its scope.

Python rebuild closed at NEM-080; see the [rebuild plan](python-backend-rebuild.md). M5 underway: NEM-054 froze scope/detectors, NEM-055 built observation persistence, NEM-056 built bounded worker imports, NEM-057 implemented detectors; NEM-058–NEM-062 delivered the versioned catalogue, replay contract, real-data connection and shareable links; NEM-063 rehearsal passed and deferred the Admin UI ([decision 021](decisions/021-admin-ui-deferred.md)); next — [NEM-064](#nem-064) M5 exit review, plus gap task [NEM-082](#nem-082). [GridReplay delivery plan](features/gridreplay.md#m5-delivery-plan--2026-09-25); Admin remains an explicit assessment.


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
- Status: Done
- Depends on: [NEM-007](#nem-007), [NEM-008](#nem-008)
- References: [Specification / decision](features/batterylab.md)

### Outcome

Build the minimal Java proof with a deterministic feasible baseline and independent accounting.

### Done when

- Create the minimal reproducible build and pure Java domain types without API/database dependencies.
- Verify energy conservation, limits, terminal energy, non-simultaneity and cost accounting on independent synthetic fixtures.
- Verify the strategy cannot inspect prices to choose its dispatch, and report infeasible configurations explicitly.

### Completion evidence

Implemented a Java 25 `core` module, checksum-pinned Gradle 9.7.1 wrapper and locked JUnit 6.1.3 dependencies. Immutable battery/efficiency/window/price-day types enforce input and full-day semantics. `FixedSchedule.plan` cannot access prices/costs; separate validation reconstructs energy and checks bounds, power, windows, exclusivity and terminal energy. Accounting is recomputed from dispatch.

Verification: `JAVA_HOME=/usr/lib/jvm/java-25-openjdk-amd64 ./gradlew clean build --no-daemon --offline` passed on 2026-09-17: **33 tests, zero failures/errors/skips**, including 200 seeded scenarios inside one invariant test and both validated NSW1 price days. [Tests](../../reference/java/core/src/test/java/au/nemlab/batterylab/BatteryEngineTest.java) cover negative/zero/losing prices, efficiency/fees, connection limits, partial allocation, terminal inventory, price independence, missing/duplicate/wrong-region data, DST-independent market days, invalid windows, overflow and tampered dispatch. No solver or API is claimed. Changes are uncommitted; setup is in [README](../../README.md).

<a id="nem-010"></a>

## NEM-010 — Evaluate hindsight optimisation and engine performance

- Repository: backend
- Milestone: M2
- Priority: High
- Status: Done
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

Selected pinned MIT-licensed ojAlgo 57.3.0 on Java 25 for the exact ordered-window model. [Decision 007](decisions/007-hindsight-solver.md) records scope and consequences. [Findings](evidence/engine/findings.md) include primal/dual formulation, independent certification, 47 passing tests (including 40 tiny enumerated and 20 fractional cases), 15 validated full-day runs, memory/time measurements and actual budget probes. Experiment command: `./gradlew clean build :core:hindsightBenchmark --offline --no-daemon` with JAVA_HOME set to JDK 25; final offline `build` also passed after adding the oversized-scenario regression. Cold run 165.55 ms; other runs 2.22–10.42 ms; RSS peak ~94.52 MiB. No unrestricted solver claim. Proposed worker limits/enforcement follow-ups are recorded. NEM-010 changes are included in the local solver commit; NEM-009 was committed as `5c21ecd`.

<a id="nem-011"></a>

## NEM-011 — Establish backend repository and application modules

- Repository: backend
- Milestone: M3
- Priority: High
- Status: Done
- Depends on: [NEM-006](#nem-006), [NEM-010](#nem-010)
- References: [Specification / decision](architecture.md)

### Outcome

Refine into implementation tasks for Git setup, module boundaries, API/worker entry points and CI.

### Done when

- Break this package into focused tasks before starting.
- A clean checkout builds/tests both runnable applications with shared domain/infrastructure boundaries and documented commands.
- Repository ignores protect credentials/generated artifacts; dependency pins and relevant CI checks are recorded.

### Completion evidence

Git setup was completed earlier. [NEM-021](#nem-021), [NEM-022](#nem-022) and [NEM-023](#nem-023) now deliver separate Boot applications, locked builds, startup checks and a prepared CI workflow. [Foundation findings](evidence/foundation/findings.md): 49 passing tests; API/worker packaged smoke checks; clean source-only copy builds offline; forbidden dependency probe rejected. Hosted CI has not run. Changes are uncommitted.


### Implementation breakdown

- [NEM-021](#nem-021): module boundaries and independently runnable applications.
- [NEM-022](#nem-022): executable-jar startup checks and local setup.
- [NEM-023](#nem-023): reproducible CI checks and module dependency enforcement.

<a id="nem-012"></a>

## NEM-012 — Build versioned data ingestion and coverage storage

- Repository: backend
- Milestone: M3
- Priority: High
- Status: Done
- Depends on: [NEM-011](#nem-011)
- References: [Specification / decision](features/data-foundation.md)

### Outcome

Refine migrations, source provenance, observation versions, bounded polling and backfills.

### Done when

- Break this package into migration, ingestion and coverage tasks before starting.
- Repeat imports remain idempotent and interrupted backfills resume safely.
- Coverage/gaps/revisions are visible and immutable simulation snapshots survive data refreshes.

### Completion evidence

Price-first implementation complete through NEM-024–NEM-027. [Findings](evidence/data-foundation/findings.md) record 64 passing tests, real PostgreSQL migrations/revision/snapshot/checkpoint tests, bounded HTTP stub tests and packaged application smoke checks. [Operator instructions](../../reference/java/infrastructure/README.md) cover explicit migration/import/resume/coverage/history. GridReplay adapters remain NEM-018; worker integration and scheduling remain NEM-013. No live OE request or hosted CI run was performed. Changes are uncommitted.

### Implementation breakdown

Price-first deliverable: NEM-024 schema, NEM-025 OE adapter, NEM-026 revisions/coverage/snapshots, NEM-027 resumable backfill. GridReplay ingestion adapters will be scoped with NEM-018 after metric semantics are settled; no generic all-metric ingestion promise is made. Scheduling and job leases remain NEM-013.

<a id="nem-013"></a>

## NEM-013 — Build durable jobs and operator controls

- Repository: backend
- Milestone: M3
- Priority: High
- Status: Done
- Depends on: [NEM-011](#nem-011)
- References: [Specification / decision](architecture.md)

### Outcome

Refine database jobs, retries, leases, idempotency and protected refresh/status operations.

### Done when

- Break this package into focused job and operator tasks before starting.
- Schedule and manual requests share one execution path; expired claims recover without stale workers committing results.
- Concurrency/retries are bounded, failed jobs have actionable diagnostics, and administrative actions are authorised and audited.

### Completion evidence

Split into [NEM-028](#nem-028), [NEM-029](#nem-029), and [NEM-030](#nem-030). All three price-refresh slices are implemented and verified, including protected HTTP controls and retirement of direct CLI ingestion. See [operator evidence](evidence/jobs/admin-findings.md). Simulation job execution remains NEM-016; M3 still needs public API contracts and frontend integration.

<a id="nem-014"></a>

## NEM-014 — Define and implement shared API contracts

- Repository: backend
- Milestone: M3
- Priority: Normal
- Status: Done
- Depends on: [NEM-012](#nem-012), [NEM-013](#nem-013)
- References: [Specification / decision](architecture.md)

### Outcome

Refine coverage/series and job contracts with validation, errors and generated client inputs.

### Done when

- Break into bounded endpoint/contract tasks before starting.
- API contract documents units, timestamps, window limits, error shapes and versioning.
- Contract and database integration checks demonstrate coverage retrieval and asynchronous job submission/status.

### Completion evidence

Split into [NEM-031](#nem-031), stored-price read endpoints, and [NEM-032](#nem-032), formal shared contracts and generated client inputs. Both slices are implemented and verified: 103 Java tests, seven contracted operations and 46 actual HTTP response checks. See [contract evidence](evidence/data-foundation/contract-findings.md). Committed as `6e527ed`.

<a id="nem-015"></a>

## NEM-015 — Establish frontend workspace and client integration

- Repository: frontend
- Milestone: M3
- Priority: Normal
- Status: Done
- Depends on: [NEM-014](#nem-014)
- References: [Specification / decision](decisions/005-infrastructure-and-frontend.md)

### Outcome

Create the separate frontend repo and validate the proposed stack on one API/chart slice.

### Done when

- Break into repository, UI shell and integration tasks before starting.
- Verify dependency versions/licences, typed API integration and a shared time-axis/cursor prototype.
- Add project instructions linking to canonical backend docs; reserve Admin structure without creating an empty application.

### Completion evidence

Split into NEM-033 (repository/tooling), NEM-034 (public shell), NEM-035 (typed API integration) and NEM-036 (synchronised charts). NEM-033–NEM-036 are verified. The frontend baseline, typed API slice and shared-chart proof meet this package’s criteria; see [chart evidence](evidence/frontend/chart-findings.md). Committed as `19834eb` (backend records) and `e963747` (frontend); overall M3 exit review is NEM-037.

<a id="nem-016"></a>

## NEM-016 — Deliver BatteryLab simulation API and stored results

- Repository: backend
- Milestone: M4
- Priority: High
- Status: Done
- Depends on: [NEM-010](#nem-010), [NEM-014](#nem-014)
- References: [Specification / decision](features/batterylab.md)

### Outcome

Deliver through [NEM-039](#nem-039) request contract/validation, [NEM-040](#nem-040) durable execution/results, then [NEM-041](#nem-041) HTTP lifecycle/generated contract. Start with the accepted battery-v1 fixed-schedule versus ordered-window comparison; unrestricted hindsight stays deferred.

### Done when

- Break into scenario, execution and result tasks before starting.
- Save reproducible inputs, model versions, solver status, dispatch and accounting; refreshes do not mutate saved runs.
- Integration checks cover invalid inputs, gaps, deduplication, completion and failure/timeout.

### Completion evidence

Refined 2026-09-20 during NEM-037. NEM-039 request preparation, NEM-040 durable execution/results and NEM-041 HTTP integration are complete. The user directed local implementation to continue while the separate M3 hosted CI gate remains open.

<a id="nem-017"></a>

## NEM-017 — Deliver the BatteryLab visitor experience

- Repository: frontend
- Milestone: M4
- Priority: High
- Status: Done
- Depends on: [NEM-015](#nem-015), [NEM-016](#nem-016)
- References: [Specification / decision](features/batterylab.md)

### Outcome

Refine forms, comparison views, synchronised charts, methodology and shareable results.

### Done when

- Break into focused UI and browser-workflow tasks before starting.
- A visitor completes and reopens a scenario with clear units, financial breakdown and constraint explanations.
- Accessible controls and meaningful loading/error states pass browser checks; chart values agree with backend results.

### Completion evidence

Delivered as NEM-042–NEM-046. NEM-042 established product layouts and shared appearance, NEM-043 the scenario form and lifecycle, NEM-044 the stored comparison and linked charts, NEM-045 the saved-result journey and acceptance review, and NEM-046 visitor-triggered price refresh for eligible uncovered days. A visitor configures an exact scenario, follows job progress, inspects both strategies with clear units and financial breakdown, copies a result link and reopens the identical immutable result — including after reload. All 88 desktop/mobile Chromium cases and 6 live API/worker/PostgreSQL cases pass; chart values and totals agree with stored backend accounting. See [NEM-045](#nem-045) and [NEM-046](#nem-046) evidence for the acceptance review.

<a id="nem-018"></a>

## NEM-018 — Deliver GridReplay catalogue and replay

- Repository: both
- Milestone: M5
- Priority: High
- Status: Backlog
- Depends on: [NEM-006](#nem-006), [NEM-017](#nem-017)
- References: [Specification / decision](features/gridreplay.md)

### Outcome

Deliver the demo-faithful real-data journey through NEM-054–NEM-062 and the NEM-064 exit review. This is the parent package, not a single implementation task.

### Done when

- Finalise supported region/window, event definitions and thresholds based on data evidence before implementation.
- Detectors pass labelled fixtures, gap/overlap handling and reproducibility checks.
- Catalogue, aligned replay and navigation into the correct BatteryLab day pass an end-to-end browser check.

### Completion evidence

Delivery tasks and acceptance criteria planned on 2026-09-25; implementation and verification remain pending.

### Notes

A static mock-data demo of the catalogue/replay concept lives at [docs/demos/gridreplay/index.html](../demos/gridreplay/index.html) (2026-09-18) for discussion; synthetic data and illustrative detector definitions only. The user has selected its visual design as the primary target; see the fidelity requirements in the feature spec. NEM-054 settles the data/detector recommendation; BLK-005 retains broader coverage gates.

<a id="nem-019"></a>

## NEM-019 — Assess and optionally deliver Admin UI

- Repository: both
- Milestone: M5
- Priority: Normal
- Status: Done
- Depends on: [NEM-013](#nem-013), [NEM-063](#nem-063)
- References: [Specification / decision](features/admin.md)

### Outcome

Decide whether a minimal UI is needed before launch and record a usable operational path.

### Done when

- Rehearse coverage inspection, bounded refresh and failed-job retry through existing controls.
- Record the include/defer decision with rationale. If included, split into focused tasks and validate authentication/audit/UI flows.
- If deferred, document and verify equivalent operator procedures; do not mark a nonexistent Admin UI delivered.

### Completion evidence

Assessment completed by the NEM-063 live rehearsal on 2026-10-02. Decision: Admin UI **deferred** — [decision 021](decisions/021-admin-ui-deferred.md); the authenticated `/api/admin/v1/*` endpoints plus the documented runbook are the verified operational path. No Admin app was built; revisit triggers are recorded in the decision.

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

<a id="nem-021"></a>

## NEM-021 — Create backend modules and Boot entry points

- Repository: backend
- Milestone: M3
- Priority: High
- Status: Done
- Depends on: [NEM-010](#nem-010)
- References: [NEM-011](#nem-011), [architecture](architecture.md)

### Outcome

Create backend modules and Boot entry points.

### Done when

API and worker build as separate executable jars on Java 25 / Boot 4.1.1; infrastructure depends on core; core remains free of Spring; application contexts start without OE/database credentials.

### Completion evidence

Created infrastructure/api/worker modules on Java 25 and Boot 4.1.1. Both executable jars build; application context tests pass without database/OE credentials; core remains Spring-free. See [foundation findings](evidence/foundation/findings.md).

<a id="nem-022"></a>

## NEM-022 — Verify packaged application startup and local setup

- Repository: backend
- Milestone: M3
- Priority: High
- Status: Done
- Depends on: [NEM-021](#nem-021)
- References: [NEM-011](#nem-011), [architecture](architecture.md)

### Outcome

Verify packaged application startup and local setup.

### Done when

Start each packaged jar, verify API health and worker liveness, shut down only owned processes, and document reproducible commands and current limitations.

### Completion evidence

Packaged startup script verifies API health on a random loopback port and non-HTTP worker liveness, then cleans up its children. Checks pass in the working directory and a clean source-only copy. [README](../../README.md) documents build/run/check commands and current limits.

<a id="nem-023"></a>

## NEM-023 — Add repeatable CI and module dependency checks

- Repository: backend
- Milestone: M3
- Priority: High
- Status: Done
- Depends on: [NEM-022](#nem-022)
- References: [NEM-011](#nem-011), [architecture](architecture.md)

### Outcome

Add repeatable CI and module dependency checks.

### Done when

A checked-in CI workflow runs the locked build/tests and packaged smoke checks; module direction is enforced; verify the commands locally and distinguish that from an unexecuted hosted CI run.

### Completion evidence

Added pinned GitHub Actions workflow and Gradle project-dependency enforcement. Local and clean-copy builds pass 49 tests and packaged smoke checks. Injecting core -> api is rejected. Hosted CI remains unexecuted; local verification is recorded in [findings](evidence/foundation/findings.md).

<a id="nem-024"></a>

## NEM-024 — Create PostgreSQL price storage and migrations

- Repository: backend
- Milestone: M3
- Priority: High
- Status: Done
- Depends on: [NEM-011](#nem-011)
- References: [NEM-012](#nem-012)

### Done when

Migrations establish immutable day revisions, current coverage, ingestion attempts, snapshot references and backfill checkpoints; tested against real PostgreSQL.

### Completion evidence

PostgreSQL 18.6 schema and Flyway migrations verified against a disposable real database, including reapplication, constraints and immutable-record enforcement. See [findings](evidence/data-foundation/findings.md).

<a id="nem-025"></a>

## NEM-025 — Implement bounded OE price-day retrieval

- Repository: backend
- Milestone: M3
- Priority: High
- Status: Done
- Depends on: [NEM-011](#nem-011)
- References: [NEM-012](#nem-012)

### Done when

Parse validated OE price format with correct interval-end boundaries; reject invalid metadata/duplicates; preserve gaps/nulls; bounded requests/retries and no credential logging.

### Completion evidence

Implemented exact price-day query/normalisation, matching source metadata and preserved decimal values. Saved historical fixture and local HTTP stub tests cover boundary selection, gaps/nulls, bad units/regions, duplicates, misaligned intervals, bounded retries, sanitized errors and payload cap.

<a id="nem-026"></a>

## NEM-026 — Store revisions, expose coverage and preserve snapshots

- Repository: backend
- Milestone: M3
- Priority: High
- Status: Done
- Depends on: [NEM-024](#nem-024), [NEM-025](#nem-025)
- References: [NEM-012](#nem-012)

### Done when

Repeated identical content creates no duplicate revision; corrected data creates a new revision; current coverage distinguishes missing/null/zero; old snapshots remain unchanged.

### Completion evidence

Sequential/concurrent reimports reuse a revision; corrections create revisions; earlier fetches cannot replace fresher current data; immutable complete snapshots preserve original prices. Coverage/history and snapshot tests pass on PostgreSQL.

<a id="nem-027"></a>

## NEM-027 — Resume price backfills from persisted checkpoints

- Repository: backend
- Milestone: M3
- Priority: High
- Status: Done
- Depends on: [NEM-025](#nem-025), [NEM-026](#nem-026)
- References: [NEM-012](#nem-012)

### Done when

One-day chunks commit data and checkpoint atomically; failed days do not advance; retries/restarts resume; an explicit local runner demonstrates the integration without enabling a scheduler.

### Completion evidence

One-day data and checkpoint commits are atomic. Injected update failure rolls back both; incomplete/failed days pause; a fresh runner resumes from persisted progress; stale commits and >31-day requests are rejected. Local operator commands expose start/resume/status/coverage/history.

<a id="nem-028"></a>

## NEM-028 — Durable price-refresh queue and fenced results

- Repository: backend
- Milestone: M3
- Priority: High
- Status: Done
- Depends on: [NEM-012](#nem-012)
- References: [Architecture](architecture.md), parent [NEM-013](#nem-013)

### Outcome

Persist one completed price day per job with idempotent submission, bounded retries, expiring claims, cancellation and an audit trail. Use Spring-managed transaction boundaries; network fetches occur outside transactions.

### Done when

Real PostgreSQL tests prove concurrent deduplication/claims, expired-claim recovery, stale-result rejection, atomic price/checkpoint/job updates, bounded retries and cancellation.

### Completion evidence

Implemented in `infrastructure/.../jobs` and migration V2. Spring-proxied PostgreSQL integration tests cover the acceptance criteria, including expiry during price writes. See [job evidence](evidence/jobs/findings.md). Committed as `c5cd5a3`.

<a id="nem-029"></a>

## NEM-029 — Worker polling and scheduled refresh execution

- Repository: backend
- Milestone: M3
- Priority: High
- Status: Done
- Depends on: [NEM-028](#nem-028)
- References: [Architecture](architecture.md), parent [NEM-013](#nem-013)

### Outcome

Connect the durable queue to the non-web worker. Scheduled refresh and manual submission use the same queue; configuration is opt-in and validated.

### Done when

Verify startup configuration, scheduled deduplication, bounded execution, recovery after restart and graceful shutdown. Define and verify ingestion deadlines. Simulation subprocess/watchdog integration belongs to NEM-016 before simulation jobs are enabled.

### Completion evidence

Implemented opt-in worker configuration, lifecycle-managed polling, fixed UTC+10 daily submission, child-process fetch deadlines and shutdown/restart recovery. Full offline build: 88 passing tests, including real child-process and PostgreSQL worker tests plus executable-jar child launching without live OE calls. See [worker evidence](evidence/jobs/worker-findings.md) and [setup](../../reference/java/worker/README.md). Committed as `dc170bf`.

<a id="nem-030"></a>

## NEM-030 — Protected operator job controls

- Repository: backend
- Milestone: M3
- Priority: High
- Status: Done
- Depends on: [NEM-029](#nem-029)
- References: [Architecture](architecture.md), parent [NEM-013](#nem-013)

### Outcome

Expose authorised refresh submission, job status and cancellation with audited operator identity. Document safe local operation and failure diagnostics.

### Done when

HTTP tests reject unauthorised requests and verify valid/invalid submissions, status, cancellation and audit identity. Retire or explicitly constrain the direct backfill CLI execution path while the worker operates.

### Completion evidence

Implemented opt-in bearer authentication, server-derived audit identity, refresh submission, status/recent jobs, paginated events and idempotent cancellation. Direct CLI ingestion is retired. Full build: 97 passing tests; see [HTTP/PostgreSQL evidence](evidence/jobs/admin-findings.md) and [operator guide](../../reference/java/api/README.md). Committed as `8d7c4b1`.

<a id="nem-031"></a>

## NEM-031 — Public stored-price coverage and day series

- Repository: backend
- Milestone: M3
- Priority: Normal
- Status: Done
- Depends on: [NEM-012](#nem-012)
- References: [Data foundation](features/data-foundation.md), parent [NEM-014](#nem-014)

### Outcome

Expose opt-in read-only coverage and current price-day endpoints with explicit units, fixed NEM time, revision identity and missing/null states.

### Done when

Real HTTP/PostgreSQL tests verify complete/incomplete/absent days, exact prices, fixed-offset boundaries, bounded ranges, safe errors, read-only access and coexistence with admin authentication.

### Completion evidence

Opt-in anonymous GET coverage/current-day endpoints implemented with bounded single-query coverage, exact decimal strings and explicit gap states. Java 25 offline build passes 103 tests, including six HTTP/PostgreSQL cases and operator coexistence checks. See [read API evidence](evidence/data-foundation/read-api-findings.md). Committed as `6e527ed`.

<a id="nem-032"></a>

## NEM-032 — Shared OpenAPI contract and generated client inputs

- Repository: backend
- Milestone: M3
- Priority: Normal
- Status: Done
- Depends on: [NEM-031](#nem-031)
- References: [Data foundation](features/data-foundation.md), parent [NEM-014](#nem-014)

### Outcome

Publish a versioned machine-readable contract for price reads and operator jobs; produce deterministic frontend type/client inputs without creating a frontend repository.

### Done when

Validate the contract, check it against endpoint behaviour and errors, and verify reproducible generated artifacts. Document compatibility/versioning and preserve protected operator boundaries.

### Completion evidence

Versioned OpenAPI 3.0.3 contract, pinned toolchain and deterministic TypeScript declarations implemented. A clean Java 25 offline build passes 103 tests and validates 46 real HTTP responses across all seven operations and application error codes. Stale generated output fails checks; regeneration is byte-for-byte reproducible. See [contract evidence](evidence/data-foundation/contract-findings.md) and [consumer/update guide](../../api/contracts/README.md). Committed as `6e527ed`.

<a id="nem-033"></a>

## NEM-033 — Frontend repository and reproducible tooling

- Repository: frontend
- Milestone: M3
- Priority: Normal
- Status: Done
- Depends on: [NEM-032](#nem-032)
- References: parent [NEM-015](#nem-015), [frontend decision](decisions/005-infrastructure-and-frontend.md)

### Outcome

Create the separate nemlab-ui Git repository with one public React/TypeScript/Vite application, pinned dependencies, standard formatting, CI and canonical documentation links. Reserve the eventual Admin app boundary without creating an empty application.

### Done when

A locked clean install, strict TypeScript checks, formatting checks and production build pass. Chromium loads the production bundle at desktop/mobile widths without browser errors. Verify selected versions/licences and separate Git roots; document local setup. No API client or product workflows are implied.

### Completion evidence

Separate `nemlab-ui/.git` repository and React/TypeScript/Vite npm workspace created. Clean locked install, formatting, strict TypeScript and production build pass; two desktop/mobile Chromium checks pass and screenshots were inspected. Versions/licences are recorded in [decision 011](decisions/011-frontend-foundation.md); see [evidence](evidence/frontend/foundation-findings.md). Committed as `19834eb` (backend records) and `e963747` (frontend); no remote or deployment.

<a id="nem-034"></a>

## NEM-034 — Public navigation and UI shell

- Repository: frontend
- Milestone: M3
- Priority: Normal
- Status: Done
- Depends on: [NEM-033](#nem-033)
- References: parent [NEM-015](#nem-015), [frontend decision](decisions/005-infrastructure-and-frontend.md)

### Outcome

Build accessible public navigation and shared page layout for BatteryLab, GridReplay and methodology, with explicit unfinished-feature states. Select and verify routing and styling tools from the proposed stack.

### Done when

Keyboard navigation, direct route loading, unknown-route handling and responsive layouts pass browser checks. No invented market results or working simulation claims. Document static-host fallback requirements.

### Completion evidence

Shared public shell, four named routes, not-found recovery and keyboard/focus behaviour implemented. Locked clean install, formatting, strict build and 16 desktop/mobile Chromium cases pass; desktop/mobile screenshots reviewed. See [navigation evidence](evidence/frontend/navigation-findings.md) and [decision 012](decisions/012-public-navigation.md). Committed as `19834eb` (backend records) and `e963747` (frontend).

<a id="nem-035"></a>

## NEM-035 — Typed stored-price API integration

- Repository: frontend
- Milestone: M3
- Priority: Normal
- Status: Done
- Depends on: [NEM-034](#nem-034), [NEM-032](#nem-032)
- References: parent [NEM-015](#nem-015), [frontend decision](decisions/005-infrastructure-and-frontend.md)

### Outcome

Import versioned backend contract inputs with recorded provenance and a drift check. Implement the public typed price client, query caching and a bounded region/day coverage/price view.

### Done when

Verify real local backend integration plus browser fixtures for loading, complete/incomplete/not-imported days, invalid input and HTTP/transport failures. Preserve exact strings, fixed UTC+10 and revision metadata. Development and deployment API routing are documented; public code cannot send operator credentials.

### Completion evidence

Completed the interrupted task on 2026-09-20. Contract snapshot/provenance, drift checks, typed public client, query caching and stored-price UI are implemented. Fresh checks pass formatting, strict build, 34 browser cases and two real Java/PostgreSQL integration cases. Mobile screenshot reviewed; exact values, gap states, revision metadata and credential omission verified. See [evidence](evidence/frontend/price-integration-findings.md) and [decision 013](decisions/013-typed-price-client.md). Committed as `19834eb` (backend records) and `e963747` (frontend).

<a id="nem-036"></a>

## NEM-036 — Synchronised time-series chart prototype

- Repository: frontend
- Milestone: M3
- Priority: Normal
- Status: Done
- Depends on: [NEM-035](#nem-035)
- References: parent [NEM-015](#nem-015), [frontend decision](decisions/005-infrastructure-and-frontend.md)

### Outcome

Verify Apache ECharts against the required shared time axis, cursor and zoom behaviour before adopting it for BatteryLab/GridReplay. Use the price slice and explicitly labelled synthetic companion data where needed.

### Done when

Verify aligned cursor/zoom across two panels, negative prices, gaps, fixed NEM time, resizing and mobile/touch behaviour. Include accessible text/table alternatives, browser evidence and measured bundle/performance observations. Confirm chart licence/version and close or record failures before completing NEM-015.

### Completion evidence

ECharts 6.1.0 linked SVG prototype verified with exact text/table alternatives, shared cursor/zoom geometry, gaps, keyboard/touch, fixed NEM labels, resize and download-failure recovery. Clean build and 40 browser cases pass; two real Java/PostgreSQL cases include charts. Optional chunk is 176.64 kB gzip; sampled local initial renders were 78.4/82.6 ms. See [evidence](evidence/frontend/chart-findings.md) and [decision 014](decisions/014-linked-chart-prototype.md). Committed as `19834eb` (backend records) and `e963747` (frontend).

<a id="nem-037"></a>

## NEM-037 — Shared-foundation exit review

- Repository: both
- Milestone: M3
- Priority: Normal
- Status: Done
- Depends on: [NEM-011](#nem-011)–[NEM-015](#nem-015)
- References: [M3 exit criteria](roadmap.md#m3--shared-foundation)

### Outcome

Reconcile the completed foundation slices against the milestone's cross-repository exit
criteria before starting BatteryLab delivery. Avoid repeating already adequate checks.

### Done when

Map ingestion/idempotency, immutable snapshots, queue recovery, operator submission,
public reads and frontend/CI checks to concrete evidence. Run any missing local combined
verification, distinguish configured/local CI from hosted execution, and explicitly record
whether M3 can close or which specific gap remains. Refine NEM-016's next work accordingly;
this review does not authorise a push, deployment or new hosted account.

### Completion evidence

Reviewed 2026-09-20: [exit evidence](evidence/foundation/m3-exit-review.md) maps each criterion to implementation and recorded verification. No missing local check was identified that requires repeating the existing suites. Hosted CI execution remains unverified and neither repository has a remote; NEM-038 and BLK-007 own that explicit gap. M3 remains In progress. NEM-016 is refined into NEM-039–NEM-041. Review changes are committed as `2b5917b`.


<a id="nem-038"></a>

## NEM-038 — Verify hosted foundation CI

- Repository: both
- Milestone: M3
- Priority: Normal
- Status: Blocked
- Depends on: [NEM-037](#nem-037)
- References: [BLK-007](blockers.md#blk-007), [exit review](evidence/foundation/m3-exit-review.md)

### Outcome

Verify the existing backend and frontend workflows on hosted CI at identified commits, then close M3 if both pass.

### Done when

- Repository destinations and publication are authorised before configuring remotes or pushing.
- Both workflows complete successfully; record run URLs, commit IDs and any failures/fixes.
- Reconcile the exit review and milestone status with those results.

### Completion evidence

No remotes configured and no hosted run evidence. Local checks are recorded separately; this task does not authorise publication or account creation.

<a id="nem-039"></a>

## NEM-039 — Simulation request contract and validation

- Repository: backend
- Milestone: M4
- Priority: High
- Status: Done
- Depends on: [NEM-037](#nem-037), [NEM-010](#nem-010)
- References: parent [NEM-016](#nem-016), [model contract](features/battery-model-contract.md)

### Outcome

Define and implement a transport-independent scenario request for one complete stored market day and the accepted fixed/ordered-window comparison. Reuse core model validation and capture normalised parameters, immutable price revision and model/strategy versions for reproducibility.

### Done when

- Specify exact numeric/time representations, field errors and bounded scenario inputs before implementing them.
- Resolve a complete immutable price snapshot; reject unavailable or incomplete days without triggering ingestion.
- Define stable scenario identity including the price revision and all result-affecting parameters/versions.
- Verify invalid values/windows, equivalent normalised requests and source corrections against real storage and existing engine fixtures.

### Completion evidence

Implemented exact request normalisation, field errors, core model reuse, read-only immutable revision capture and versioned scenario identity. Java 25 offline build passes 116 tests (13 new cases) and 46 HTTP contract responses. See [contract](features/simulation-request-contract.md), [decision 015](decisions/015-simulation-request-boundary.md) and [evidence](evidence/engine/request-findings.md). No executable public endpoint; HTTP integration follows NEM-041. Committed as `a151677`.

<a id="nem-040"></a>

## NEM-040 — Durable simulation execution and immutable results

- Repository: backend
- Milestone: M4
- Priority: High
- Status: Done
- Depends on: [NEM-039](#nem-039)
- References: parent [NEM-016](#nem-016), [BatteryLab](features/batterylab.md)

### Outcome

Persist and execute bounded simulation jobs using the existing engine, with simulation concurrency separate from price refreshes and immutable results tied to their original inputs.

### Done when

- Specify migrations, deduplication, lease/retry semantics and process resource limits before implementation.
- Enforce a hard subprocess deadline and reject stale completion after recovery.
- Persist both strategies, solver status, dispatch, energy and independently verified accounting atomically.
- Verify restart recovery, duplicate requests, failure/timeout, and unchanged saved inputs/results after source refresh.
- Never present a feasible incomplete solver result as proven optimal.

### Completion evidence

Implemented V3 immutable inputs/results, an independent bounded simulation queue, token-fenced recovery/publication, and opt-in subprocess execution. Full Java 25 offline build passes 141 tests (25 new) and all 46 HTTP contract responses. Packaged worker execution, deadlines, watchdog, shutdown, retries and source-correction preservation are verified. See [execution evidence](evidence/engine/execution-findings.md) and [decision 016](decisions/016-durable-simulations.md). Public HTTP lifecycle remains NEM-041. Committed as `a151677`.

<a id="nem-041"></a>

## NEM-041 — Simulation HTTP lifecycle and generated contract

- Repository: backend
- Milestone: M4
- Priority: High
- Status: Done
- Depends on: [NEM-040](#nem-040)
- References: parent [NEM-016](#nem-016), [API contract guide](../../api/contracts/README.md)

### Outcome

Expose bounded scenario submission, job status and immutable result retrieval with opaque shareable identifiers; extend the versioned contract and generated frontend inputs.

### Done when

- Define methods, status/error responses and compatibility rules in OpenAPI; keep operator capabilities separate.
- Verify the actual HTTP lifecycle against PostgreSQL, including validation, unavailable data, deduplication, queue saturation, failures and unknown results.
- Verify deterministic generated types and HTTP response-contract checks.
- Record the frontend handoff for NEM-017 and keep launch quotas/retention decisions explicit under NEM-020.

### Completion evidence

Implemented opt-in public submission/status/result endpoints with strict decimal-string JSON, safe DTOs, bounded bodies, durable deduplication and explicit pending/failure states. OpenAPI 1.1.0 and deterministic TypeScript inputs are verified by 94 actual HTTP responses across ten operations. Full backend build passes 150 tests and packaged startup checks. All three child tasks now pass, completing NEM-016. See [evidence](evidence/engine/http-findings.md) and [decision 017](decisions/017-simulation-http-contract.md). Committed as `9395a92` (backend) and `762ef1d` (frontend snapshot). Frontend contract/format/type/build checks and all 40 browser cases pass; the visitor workflow remains NEM-017.

<a id="nem-042"></a>

## NEM-042 — Product layouts and shared appearance

- Repository: frontend
- Milestone: M4
- Priority: High
- Status: Done
- Depends on: [NEM-015](#nem-015)
- References: parent [NEM-017](#nem-017), [decision 018](decisions/018-product-layouts-and-appearance.md)

### Outcome

Establish the real app's visual foundation from the accepted mock direction: centered BatteryLab, full-width GridReplay and a shared light/dark/auto preference.

### Done when

- Both product routes retain distinct layouts and accents in both palettes, without presenting mock data as real results.
- Appearance persists across reload/navigation, follows device changes in Auto, and remains usable with blocked storage.
- Existing price/chart interactions, keyboard navigation and 320px layouts remain usable; chart appearance changes preserve selection.
- Frontend checks pass and desktop/mobile screenshots are visually reviewed.

### Completion evidence

Frontend commit `362f1f4` implements mock-inspired product layouts, persistent Light/Dark/Auto appearance, storage fallback/cross-tab updates, and theme-aware charts preserving selection. Contract, formatting, TypeScript, production build and all 46 desktop/mobile Chromium cases pass. Desktop/mobile light BatteryLab, dark GridReplay and dark chart screenshots were visually reviewed, including a corrected mobile heading. The existing lazy ECharts bundle size warning remains. No simulation/replay integration or hosted CI result is implied. Next: NEM-043.

<a id="nem-043"></a>

## NEM-043 — Battery scenario form and simulation lifecycle

- Repository: frontend
- Milestone: M4
- Priority: High
- Status: Done
- Depends on: [NEM-042](#nem-042), [NEM-041](#nem-041)
- References: parent [NEM-017](#nem-017), [request contract](features/simulation-request-contract.md), [HTTP contract](decisions/017-simulation-http-contract.md)

### Outcome

Replace the scenario guide with an accessible real form and connect submission, polling and terminal states to the public API.

Also applies the accepted centered-layout revision in [decision 018](decisions/018-product-layouts-and-appearance.md): BatteryLab capped at 1160px, GridReplay at 1440px, with the same centered header/navigation and responsive gutters. This follow-up supersedes NEM-042's full-width GridReplay choice without changing its historical completion evidence.

### Done when

- Verify centered workspace caps and consistent header alignment at wide desktop widths; both routes remain usable at 320px and in both themes. Update the existing full-width browser expectation and review screenshots.
- All required site, efficiency, cost and ordered-window inputs have units, illustrative defaults and accessible field errors; preserve exact decimal strings and fixed NEM-time semantics.
- Coverage is checked, invalid/incomplete scenarios are explained, and submissions cannot race or display stale status for a different scenario.
- A separate bounded simulation client handles queued/running/succeeded/failed, safe validation errors, queue limits and unavailable services without operator capabilities.
- Browser checks cover validation, deduplicated submissions, cancellation/unmount and lifecycle failures; successful result payload is ready for NEM-044.

### Completion evidence

Implemented the exact-decimal scenario form, complete-day checks, bounded public simulation client and queued/running/terminal lifecycle with stop/resume and stale-state clearing. Both products now use the accepted centered layouts. Frontend contract/format/TypeScript/build checks and 66 desktop/mobile Chromium cases pass. Four additional browser cases pass against a disposable PostgreSQL database and real API/worker, including worker-produced result retrieval and terminal deduplication. Desktop/mobile screenshots reviewed. Detailed comparison/charts remain NEM-044; saved-link reopening remains NEM-045. The existing lazy ECharts bundle warning and hosted CI gate remain. Committed as `81af319` (frontend implementation) and `f8ff41e` (records); `2d5cd08` corrects a focus race found when the browser suite was re-run before committing.

<a id="nem-044"></a>

## NEM-044 — Simulation comparison and linked result charts

- Repository: frontend
- Milestone: M4
- Priority: High
- Status: Done
- Depends on: [NEM-043](#nem-043)
- References: parent [NEM-017](#nem-017), [BatteryLab](features/batterylab.md)

### Outcome

Display real fixed/hindsight comparisons, financial breakdown and synchronised price, power, stored-energy and cumulative-margin charts in the accepted layout.

### Done when

- Totals, units, signs, losses and constraints agree with saved backend results and independent accounting fixtures.
- Four charts share cursor/window controls with keyboard/touch and text/table alternatives in both themes.
- Hindsight is explained as a benchmark, exact values remain available, and no synthetic prototype trace is confused with results.
- Browser checks cover positive/negative-price cases, strategy comparison and responsive result layouts.

### Completion evidence

Implemented the result section: margin stat cards, derived explanation sentences, financial breakdown and a 288-row interval detail table with exact stored price strings, plus a lazy four-panel ECharts view (price, grid-side power, stored energy, cumulative margin) sharing one cursor, window zoom and slider across desktop and mobile in both themes. Operating windows and negative-price runs are shaded; energy bounds are marked. Cumulative margin mirrors the backend accounting formula and ends at the stored margin. Frontend contract/format/TypeScript/build checks and 76 desktop/mobile Chromium cases pass (10 new: totals/breakdown agreement, shared cursor in light and dark, 320px layout, chart-load failure fallback). Desktop/mobile light and desktop dark screenshots reviewed. A live API/worker/PostgreSQL case now asserts the comparison renders from a worker-produced result. Saved-link reopening remains NEM-045; the lazy ECharts bundle warning and hosted CI gate remain. Committed as `6f3cb60` (frontend); records accompany this update.

<a id="nem-045"></a>

## NEM-045 — Saved-result journey and BatteryLab acceptance

- Repository: both
- Milestone: M4
- Priority: High
- Status: Done
- Depends on: [NEM-044](#nem-044)
- References: parent [NEM-017](#nem-017), [M4](roadmap.md#m4--batterylab)

### Outcome

Complete saved-result sharing/reopening, methodology and the end-to-end BatteryLab acceptance review.

### Done when

- Direct links and reloads restore the immutable inputs/results, including after source-price corrections; missing/failed results offer clear recovery.
- Share actions and navigation preserve scenario meaning and remain keyboard accessible.
- Full browser journey runs against the real API/worker/PostgreSQL, including unavailable data and failures; accounting/chart agreement is verified.
- Review all NEM-017 and M4 exit criteria, keeping hosted CI and public launch gates separate.

### Completion evidence

Implemented `/batterylab?simulation=<uuid>` reopening: a stored result writes its opaque job ID into the page address, and a keyboard-accessible "Copy result link" action copies the locally constructed URL. Opening the link reads job status then the immutable result — no resubmission — restores the stored scenario inputs into the form, and renders the identical comparison; the embedded price snapshot is unaffected by later source revisions. Links to queued/running jobs resume monitoring; failed jobs report their safe failure code, and malformed or unknown identifiers explain recovery while leaving the form usable. Editing any input detaches the link. A collapsed methodology summary accompanies the result. Frontend contract/format/TypeScript/build checks and 84 desktop/mobile Chromium cases pass (8 new: reload restoration, reopenable copy link, pending-job resume, missing/failed/malformed recovery). Six live browser cases pass against disposable PostgreSQL with the real API and worker, covering submit→result→reload-restore, incomplete-day rejection and unknown-link recovery; the live screenshot was reviewed. Acceptance review: NEM-017 done-when satisfied (task split, complete-and-reopen journey with clear units/breakdown/explanations, accessible states and backend-agreeing values); M4 exit criteria satisfied locally (valid scenario → progress → both results → immutable reopen; invalid input, missing data, failure and paused-checking states are explicit; browser and numerical checks pass). Hosted CI remains a separate open gate under NEM-038; public launch gates remain NEM-020. Committed as `a5c3067` (frontend); records accompany this update.

<a id="nem-046"></a>

## NEM-046 — Visitor-triggered price refresh

- Repository: both
- Milestone: M4
- Priority: High
- Status: Done
- Depends on: None
- References: parents [NEM-016](#nem-016) and [NEM-017](#nem-017), [durable queue decision](decisions/009-durable-refresh-queue.md), [HTTP contract decision](decisions/017-simulation-http-contract.md)

### Outcome

When a visitor submits a scenario for an eligible market day that lacks a complete stored price revision, the public simulation API enqueues a deduplicated price-refresh job for that region/day and returns a distinguishable pending-data state instead of only `PRICE_DAY_UNAVAILABLE`. The frontend explains the fetch delay and resumes the normal simulation lifecycle once the day is imported.

### Done when

- Eligible missing or incomplete days (valid region, completed fixed-UTC+10 market day on/after 2021-10-01) enqueue a refresh job; ineligible days still fail validation without enqueueing.
- Visitor submissions cannot duplicate fetches for the same day: request keys deduplicate against scheduled, operator and earlier visitor jobs, and a terminal visitor-triggered job has a defined re-request path.
- The HTTP contract exposes the pending-data outcome with a version bump and regenerated frontend inputs.
- Anonymous enqueueing is bounded: an explicit abuse limit (for example a separate visitor pending cap or rate limit) is chosen, implemented and recorded so visitors cannot exhaust the 100-job queue or OE quota.
- The frontend shows the pending state, resumes checking until data arrives or the refresh fails, then continues the normal lifecycle; refresh failure surfaces a clear safe state.
- Verified end to end against real API/worker/PostgreSQL, including the pending and refresh-failure browser paths.

### Completion evidence

Implemented end to end. `RefreshJobService.submitVisitor` enqueues under deterministic `visitor-price-v1:REGION:DAY` keys with `:rN` retry suffixes, deduplicates onto any active job for the day (scheduled, operator or visitor), allows at most three visitor attempts per day and ten pending visitor jobs globally; the shared 100-job cap still bounds the whole queue. `SimulationController` converts eligible-day coverage failures (`PRICE_DAY_*`, which imply a normalised eligible day) into 409 `PRICE_REFRESH_PENDING` with `Retry-After: 30`; per-day exhaustion maps to 409 `PRICE_REFRESH_FAILED`, the visitor cap to 429 `VISITOR_REFRESH_LIMIT` with `Retry-After: 60`. Ineligible days still fail validation (400) without enqueueing. The contract is 1.2.0; `PRICE_DAY_UNAVAILABLE`/`PRICE_DAY_INCOMPLETE` are removed as unreachable. The frontend dropped its coverage pre-check — POST is the trigger — and retries pending/limited submissions after `Retry-After` up to a bounded attempt count, then pauses with an explicit resumable message; `PRICE_REFRESH_FAILED` is terminal and flags the day input. Backend Testcontainers suites cover dedup onto scheduled jobs, retry-suffix re-requests, both caps and HTTP mappings; 88 desktop/mobile Chromium cases pass including pending-fetch, terminal-failure and saturated-queue paths. Six live cases pass against disposable PostgreSQL with the real API and worker: an incomplete day drove real claim→fetch cycles whose placeholder OE credential failed permanently, and the browser reached the explicit terminal state after three bounded attempts (~90 s of `Retry-After` waits). A visitor fetch succeeding against real OE remains unexercised — the harness holds no live credential — but the claim/commit path is the one already proven for scheduled and operator jobs. Committed as `cf4d63b` (backend) and `6dd3478` (frontend); records accompany this update.

### Notes

Agreed with the user on 2026-09-24 and required before BatteryLab/M4 is treated as done; the milestone record reflects the reopened scope. The rejected alternative is a synchronous OE fetch inside the API request: it would hold a credential the API deliberately lacks, cannot fit fetch latency/retries inside a request, and loses crash-safe dedup. Implemented choices: the `visitor-price-v1:` request-key namespace with `:rN` retry suffixes, three visitor attempts per day, ten pending visitor jobs globally, and `Retry-After`-paced automatic resubmission (20 pending / 10 limited attempts) before pausing. Reusing the durable queue keeps provider calls inside the existing bounded claim/fetch/commit path.

<a id="nem-047"></a>

## NEM-047 — Make comparison charts part of the default result view

- Repository: frontend
- Milestone: Post-M4 UX refinement
- Priority: High
- Status: Done
- Depends on: [NEM-044](#nem-044), [NEM-045](#nem-045)
- References: [UX plan](features/ui-refinement.md)

### Outcome

Show comparison charts automatically, put the financial breakdown above them and collapse the interval detail table.

Expanded by explicit user direction (2026-09-25): make the real BatteryLab page closely match the static demo's inputs, buttons and positions, compact layout, consistently styled panels and integrated charts. Group ID/status/source/Copy link and relevant monitoring controls immediately below the simulation button as secondary content. See the UX plan for precedence over the demo's original ordering.

### Done when

- Fresh and reopened results render all four charts without a toggle, preserving shared controls and immutable result values.
- Summary figures and compact financial breakdown precede charts; interval detail is keyboard-accessible and closed initially, like methodology.
- Demo and real-page screenshots are compared at matched widths; input grouping, action positions, spacing, panel styling and chart styling closely follow the demo, with deliberate deviations recorded.
- Simulation metadata and secondary actions sit beneath Run in the scenario panel; no oversized progress/metadata panel competes with results. Long IDs, copy feedback, queued/fetching/failure states and stop/resume remain accessible and usable in both themes.
- Loading/no-result/chart-failure states are honest and exact table access remains available.
- Desktop/mobile, theme, disclosure, failure and saved-result regression checks pass; screenshots reviewed.

### Completion evidence

Implemented in frontend `ef4c25f`. The scenario panel reproduces the demo's compact 320px card: denser fieldset grouping, a radio efficiency input, the primary Run button, and a status chip with simulation ID, scenario, price source/revision, engine versions, stop/resume and Copy result link directly beneath it — long identifiers wrap without widening the panel. The result column orders summary stats, strategy explanations and the financial breakdown ahead of four chart panels that render automatically in consistently styled cards with compact titles/legends; the power panel swaps Fixed/Hindsight through a segmented control. Interval detail and methodology sit in closed native disclosures; the chart show/hide toggle is gone. `npm run check` passed with 90/90 desktop/mobile cases covering fresh and saved-link charts, disclosure keyboard access, 320px layout, light/dark/auto themes and chart-chunk failure; `npm run test:live` passed 6/6 against the real stack. Desktop/mobile/light/dark screenshots were reviewed against the demo; the site header and theme picker stay shared rather than adopting the demo's bespoke band, and window shading plus the exact readout are retained where the demo relies on a tooltip.

<a id="nem-048"></a>

## NEM-048 — Separate price exploration from BatteryLab

- Repository: frontend
- Milestone: Post-M4 UX refinement
- Priority: High
- Status: Done
- Depends on: [NEM-035](#nem-035), [NEM-036](#nem-036)
- References: [UX plan](features/ui-refinement.md)

### Outcome

Give price exploration its own navigable page and render available price charts automatically; remove the embedded explorer from BatteryLab.

### Done when

- A dedicated route supports direct load/reload and shared navigation/theme; BatteryLab no longer includes the explorer.
- Imported price series render charts without a toggle; missing observations stay distinct from zero and no-data/error states remain clear.
- Read-only price browsing and visitor-triggered simulation refresh remain separate; saved results retain their original prices.
- Exact values remain accessible; route, coverage, chart and keyboard/mobile checks pass and screenshots are reviewed.

### Completion evidence

Implemented in frontend `ef4c25f`. `/prices` is a directly navigable route ("Explore electricity prices") in the primary navigation; BatteryLab no longer embeds the explorer. The stored-price chart renders automatically whenever a series exists — the synthetic energy trace is removed — while gaps stay disconnected and the exact interval table sits in a collapsed disclosure. Coverage, revision, loading, incomplete, absent and failure states are unchanged, and price browsing still issues only read-only GETs — no visitor refresh. Saved simulation results keep their embedded price snapshots. `npm run check` passed with route, coverage, auto-chart, collapsed-table, keyboard, mobile, theme and failure cases (90/90), `npm run test:live` passed 6/6 against the real API, and screenshots were reviewed in both themes.

<a id="nem-049"></a>

## NEM-049 — Implement the price-threshold engine

- Repository: backend
- Milestone: Optional post-M4 extension
- Priority: Normal
- Status: Done
- Depends on: [NEM-009](#nem-009)
- References: [Threshold strategy proposal](features/price-threshold-strategy.md)

### Outcome

An understandable all-day strategy that charges below a fixed threshold, discharges above another and otherwise holds, using existing physical limits and accounting.

### Done when

- Finalise/version strict threshold comparisons, idealised same-interval execution, multiple cycles and no forced terminal trade before implementation.
- Tests cover exact boundary prices, negative prices, repeated/no trades, partial intervals, losses/fees, power/energy limits and no future-price dependence.
- Ending energy and cashflow are explicit; existing schedule/hindsight behavior and proof claims remain intact.

### Completion evidence

Implemented in backend `98015d0` as `PriceThreshold` (`price-threshold-v1`) with a `Thresholds` exact-decimal value type. The engine evaluates each stored interval price strictly — charge below the charge threshold, discharge above the discharge threshold, hold otherwise (equality holds) — at the greatest feasible power under energy bounds, charge/discharge MW, import/export MW and efficiency, clamping partial intervals and allowing multiple cycles with no forced terminal trade. `DispatchValidator` gained an unrestricted variant enforcing physical limits and energy balance without schedule windows or equal terminal energy. `PriceThresholdTest` covers exact boundary prices, negative prices, repeated and zero trades, partial intervals, losses/fees, power/energy limits and no future-price dependence; the full `./gradlew test` suite passes.

<a id="nem-050"></a>

## NEM-050 — Persist and expose threshold experiments

- Repository: both
- Milestone: Optional post-M4 extension
- Priority: Normal
- Status: Done
- Depends on: [NEM-049](#nem-049), [NEM-041](#nem-041)
- References: [Threshold strategy proposal](features/price-threshold-strategy.md)

### Outcome

Support optional threshold inputs/results through the existing durable simulation lifecycle and versioned API.

### Done when

- Versioned request/result contracts preserve exact threshold strings and immutable snapshot/strategy identity; generated frontend types agree.
- Worker execution, storage, deduplication and result retrieval include the experiment without changing existing strategy semantics.
- Old requests and saved results remain usable; integration tests cover optional fields and stored-result reproduction.

### Completion evidence

Implemented in backend `98015d0`; frontend types synced via `contract:sync`. `SimulationRequest` gained an optional `thresholds` block whose exact decimal strings ride the canonical identity only when present — old scenario keys stay byte-identical while threshold scenarios deduplicate separately. `SimulationComparison` carries an optional threshold experiment result (version, thresholds, dispatch, accounting) validated before persistence, and `SimulationController` exposes it on `/result` plus the `inputs` echo. API contract 1.3.0 models the optional result field as `anyOf` object-or-null (compatible with the Swagger Parser/AJV verifier; `Retry-After` enum was widened for the legitimate `60` value); `verify.mjs` passed all operations and 120 captured responses. `SimulationJobsTest` covers threshold round-trip, distinct scenario keys and old-result compatibility; `SimulationHttpTest` covers submission, rejection and stored-result reproduction. `./gradlew test` passes.

<a id="nem-051"></a>

## NEM-051 — Present the threshold experiment

- Repository: frontend
- Milestone: Optional post-M4 extension
- Priority: Normal
- Status: Done
- Depends on: [NEM-050](#nem-050), [NEM-047](#nem-047)
- References: [Threshold strategy proposal](features/price-threshold-strategy.md)

### Outcome

Let visitors adjust two thresholds and inspect the resulting dispatch, cashflow and ending energy with the existing charts.

### Done when

- Controls, threshold price lines, distinct strategy series, financial details and interval explanations agree with saved backend results.
- All-day operation and ending-energy differences are visible; no invalid winner ranking or restricted-hindsight upper-bound claim is made.
- Saved links and old results work; browser checks cover themes, narrow screens, keyboard controls and validation.

### Completion evidence

Implemented in frontend `d4540c7`. An optional "Price thresholds" fieldset enables two signed-decimal inputs with strict ordering and exact-string submission; saved results restore the checkbox and values, and results stored before the experiment still render. The comparison adds a threshold stat card naming all-day operation and ending energy, a third financial-breakdown column, threshold MW/MWh/margin columns in the interval table, a third power-panel strategy and a violet series in the energy and margin charts, labelled dashed charge/discharge lines on the price chart, and per-interval action explanations including binding energy/power limits. Explanations state the rule is not ranked against the fixed/hindsight pair, whose equal-terminal-energy comparison and dual-bound claims are unchanged. `npm run check` passed 98/98 including new validation, ordering, negative-threshold, saved-link, old-result, theme and narrow-screen cases; `npm run test:live` passed 6/6 with a threshold submission executed by the real worker; screenshots reviewed in both themes.

<a id="nem-052"></a>

## NEM-052 — Make price thresholds a default third strategy

- Repository: frontend
- Milestone: Post-M4 UX refinement
- Priority: High
- Status: Done
- Depends on: [NEM-051](#nem-051)
- References: [Threshold UX revision](features/price-threshold-strategy.md#accepted-ux-revision--2026-09-25-implemented-as-nem-052), [UI refinement plan](features/ui-refinement.md)

### Outcome

Present Fixed schedule, Price thresholds and Perfect hindsight as three default strategies, with clearly separated shared, schedule and threshold inputs rather than an optional experiment.

### Implementation sequence

1. Enable thresholds in new scenarios, show both fields and remove the opt-in checkbox; preserve the API's optional fields for old-result compatibility.
2. Group shared battery settings, schedule settings and price-threshold settings. Label windows as applying only to fixed schedule and hindsight; explain that thresholds run all day.
3. Align the three strategy names and visual prominence across summaries, financial breakdown, charts and selectors; retain the short ending-energy caveat and correct scope of hindsight claims.
4. Preserve old two-strategy saved results. Add an explicit “Compare all three” path to a new editable scenario with illustrative thresholds; never mutate or silently rerun the old result.

### Done when

- New submissions include validated thresholds by default and produce three visible strategy results without an enabling checkbox.
- Windows remain available for scheduled strategies and are never presented as affecting threshold dispatch.
- Fresh, shared and older saved-result paths behave correctly; no third result is fabricated or old input altered on reload.
- Browser/live checks cover default submission, validation, conversion from old results, sharing and result agreement; demo-style desktop/mobile/theme screenshots are reviewed.
- Threshold-only mode remains out of scope; no unnecessary engine or API change is introduced.

### Completion evidence

Implemented in frontend `5d4a82c` (NEM-051 shipped thresholds as opt-in; this task removed the opt-in). New scenarios submit `thresholds` unconditionally — the checkbox is gone, both fields are always visible with illustrative defaults (30/150) and the same signed-decimal/ordering validation. The form separates shared settings, "Schedule windows — fixed schedule and hindsight only", and "Price thresholds — all-day rule" with the ending-energy caveat beside the fields. Strategy naming is aligned ("Fixed schedule" / "Price thresholds" / "Perfect hindsight") across stat cards, breakdown and interval columns, legends and the power-panel selector, and the threshold card sits with the other strategy cards. Old two-strategy saved results reopen unchanged with empty threshold fields and an explicit "Compare all three" action that fills the illustrative defaults, detaches the link and preserves the stored result — nothing is fabricated or silently rerun. The API still accepts optional thresholds; no engine or contract change. `npm run check` passed 98/98 (default submission, validation, old-result conversion, saved links, themes, narrow screens); `npm run test:live` passed 6/6 with the real worker producing a three-strategy result; screenshots reviewed in both themes.


<a id="nem-053"></a>

## NEM-053 — Polish BatteryLab presentation against the demo

- Repository: frontend
- Milestone: Post-M4 UX refinement
- Priority: Normal
- Status: Done
- Depends on: [NEM-052](#nem-052)
- References: [UI refinement plan](features/ui-refinement.md)

### Outcome

Polish the implemented three-strategy page through computer-use review of the live page and static demo, preserving the simulation workflow.

### Done when

- All three strategies appear in the empty state and as equally prominent result summaries; supporting metrics are visually secondary.
- Form pairs and panel styling follow the demo, with shared inputs preceding strategy settings.
- Power charts show isolated five-minute trades and retain synchronized cursors/window controls.
- One-sided trading days have readable explanations without invalid price averages; desktop/mobile/theme checks pass.

### Completion evidence

Implemented in the frontend files `BatteryWorkspace.tsx`, `ResultView.tsx`, `ResultCharts.tsx`, `compare.ts` and `styles.css`. Capacity occupies its own row, charge/discharge and import/export inputs pair correctly, and costs precede both strategy-specific groups. Strategy-colored summary cards form one desktop row and compact mobile rows; supporting hindsight metrics are quieter, and explanation/disclosure panels use the shared card surface. Empty-state and stored-result copy reflect the actual strategy count. Charging/discharging bars replace lines that could hide isolated intervals; disabling automatic bar padding preserves exact cursor alignment at zoomed endpoints. Zero-volume sides omit their undefined average price.

`npm run check` passed 100/100 browser cases, contract validation, formatting and build; a charge-only regression case was added. Computer-use review compared the demo and a real local NSW1 result for 2026-09-24, including saved-result reload, threshold power selection, light/dark appearance and 390px mobile presentation. Existing tests additionally cover 320px overflow/disclosures and shared chart controls. The first bar-chart test run exposed cursor padding; the final full suite passes after correction. No backend/contract changes; the separate live integration suite was not rerun for this presentation change. Local commits are recorded in the journal.

A follow-up pass compacted the page further: the introduction fits one line at desktop width, scenario controls share a uniform 32px height (previously the date picker was visibly taller), and the seven scenario groups collapse behind native disclosures — Market day open by default, the rest closed, with any group holding a rejected field forced open before focus lands on it. `npm run check` passed 102/102 cases and the live suite 6/6; frontend commit `4e4156f`.

A second follow-up moved interval data into demo-style cursor tooltips: each chart shows a dark tooltip card beside the axis cursor (native ECharts `axis` tooltips synchronised across panels via chart groups), replacing hover-driven React updates that made the cursor feel heavy. The discrete selected interval still drives the mark line, slider and readout via click, arrow keys or controls. The Fixed/Thresholds/Hindsight segmented control now appears on the power, energy and margin panels with one synced selection — power swaps its bars, energy and margin emphasise the selected strategy while keeping comparison lines faintly visible. `npm run check` passed 102/102 cases; the live suite was not rerun for this presentation-only change. Frontend commit `d9b5a08`. A further copy pass gave `.intro` full width on every page and renamed the heading to "What could a battery do in a market day?" with a three-strategy introduction; `npm run check` stayed green, commit `3730335`.

A third follow-up removed the chart controls entirely — the Visible window selector, Selected interval slider and the below-charts `.chart-readout` are gone on both the comparison and prices charts. Panels always cover the full day; the connected axis tooltips carry interval values and the exact interval tables remain the accessible alternative. Interval selection now commits on `mousedown` (taps on touch devices never produced a zrender `click`), a chart resize clears the stale axis-pointer state so the tooltip cannot linger at old coordinates, and `.chart-plot` clips the tooltip DOM. The Prices chart gained the same axis tooltip as the comparison panels. `npm run check` passed 102/102 cases updated for full-day rendering, tooltip content, cursor synchronisation and narrow layouts; the live suite passed 6/6 (it also caught a stale `nth(1)` table selector left by the metadata-table change, now scoped to the disclosure). Frontend commit `b48295e`.


<a id="m5-delivery-tasks"></a>

## M5 delivery tasks

Planned on 2026-09-25. Only NEM-054 is ready to start; downstream records remain Backlog until their dependencies and evidence gates are met. The visual direction is accepted; proposed detector defaults, catalogue period and Admin recommendation must not be described as shipped or fully validated.

<a id="nem-054"></a>

## NEM-054 — Freeze GridReplay data scope and detector rules

- Repository: both
- Milestone: M5
- Priority: High
- Status: Done
- Depends on: [NEM-006](#nem-006), [NEM-053](#nem-053)
- References: [Delivery specification](features/gridreplay.md)

### Outcome

Turn the proposed NSW1 scope into an implementable contract and small labelled fixture set.

### Done when

- Record the first catalogue region/date window and a metric-by-metric coverage matrix using existing M1 evidence; list any additional bounded source checks needed before enabling imports.
- Freeze the three detector definitions, exact comparisons, ramp tie/completeness policy, cross-midnight ownership, chunk continuation and treatment of unresolved coverage edges. Document recommended defaults and exclusions from the GridReplay spec.
- Define event/replay fixture shapes, timestamp semantics, immutable version identity, retention dependency and maximum import/replay/page bounds. Add hand-labelled complete/gap/boundary/no-event examples without pretending synthetic data is real.
- Record accepted implementation decisions and remaining evidence gaps; do not block the UI fixture work on optional renewable/battery methodology.

### Completion evidence

2026-10-02 — all "Done when" criteria met:

- **Catalogue window**: NSW1, 2023-09-01..30 — a bounded six-request live
  probe ([evidence/m5-coverage](evidence/m5-coverage/findings.md)) shows all
  16 required series complete 288/288 on all 30 days; negative prices occur
  on all 30 days and a genuine spike (>1000 AUD/MWh) occurs on 2023-09-04.
  Remaining pre-import checks listed in the findings.
- **Detectors frozen** in [decision 020](decisions/020-gridreplay-scope-and-detectors.md):
  negative_price_run (<0, >=3 consecutive), price_spike (>1000, contiguous
  grouping), demand_ramp (36-step window, all 37 observations required,
  earliest-tie, insufficient-coverage withholds the claim). Cross-midnight
  ownership = start market day; chunk boundaries never close runs; edge runs
  recorded as `edge_incomplete`, excluded from complete claims.
- **Fixture contract**: `fixtures/gridreplay/` — run-length-encoded labelled
  inputs (8 files: complete runs, absent/null interruptions, cross-midnight,
  strict thresholds, ramp tie, insufficient coverage, no-event, edge), all
  explicitly synthetic.
- **Bounds frozen**: imports ≤31 market days/request, replay ≤7 market days,
  catalogue page 24 default/100 max; event identity and immutable
  version/snapshot contract defined for NEM-055–058.
- Exclusions recorded: renewable-peak detector, battery aggregation, named
  interconnectors, causal annotations; retention bound deferred to
  NEM-055/058.

Committed as `fb58da1` (plus `c5fdd0a` recording the SHA/UTC title).

<a id="nem-055"></a>

## NEM-055 — Persist versioned GridReplay observations and coverage

- Repository: backend
- Milestone: M5
- Priority: High
- Status: Done
- Depends on: [NEM-054](#nem-054)
- References: [Delivery specification](features/gridreplay.md)

### Outcome

Store the required grid context alongside the existing price foundation, preserving metric-specific semantics.

### Done when

- Migrations and repositories cover region/metric/technology identity, exact values, source timestamps, revisions and per-series coverage. Distinguish zero, null, omitted timestamps and missing series.
- Bounded provider adapters validate demand, selected technology and flow responses, preserve signed anomalies and keep optional/unsupported categories explicit. Reuse proven price ingestion without changing its semantics.
- PostgreSQL and adapter tests verify idempotence, corrections, malformed input, gaps, metadata/units and consistent revision reads. No generic all-metric framework or new service is required.

### Completion evidence

- **V4 schema** (`infrastructure/src/nemlab_infrastructure/db/migration/V4__grid_observations.sql`,
  Alembic `nemlab_v4_grid_observations`): `grid_revision` (immutable,
  content-hash deduped per region/metric/series/day), `grid_current`
  (freshness-fenced pointer), `grid_import_attempt` (per-request audit,
  `FAILED ⇔ revision_count=0`). Region/metric/series/day/source-revision
  identity plus per-series valid/missing/null counts.
- **`nemlab_infrastructure.grid`** package: `batch` (288-slot source-label
  `GridBatch` — zero, source-null and missing stay distinct), `source`
  (`OeGridSource` reusing `OePriceSource` transport unchanged;
  `fetch_market` = demand+flows, `fetch_power` = all fueltech series on the
  data endpoint), `store` (`GridStore` save/coverage/history/pinned-revision
  reads). No generic all-metric framework; no new service.
- Missing expected market metric → explicit all-MISSING series revision;
  absent fetch → no row (missing series); power keeps every returned
  fueltech; signed anomalies (e.g. negative MW) preserved.
- **Adopt fix**: `adopt` now stamps only `nemlab_baseline_v1_v3` then
  upgrades to head, so post-baseline migrations apply to adopted
  Java-managed databases instead of being skipped by a head stamp.
- Tests: `infrastructure/tests/test_grid.py` (31) cover parsing boundaries,
  idempotence, corrections, stale-fetch fencing, malformed input, gaps,
  metadata/units, pinned revision reads; `test_schema.py` gained an
  adopt-applies-later-migrations case. Full suite 340 passed.

<a id="nem-056"></a>

## NEM-056 — Run bounded grid imports through the worker

- Repository: backend
- Milestone: M5
- Priority: High
- Status: Done
- Depends on: [NEM-055](#nem-055)
- References: [Delivery specification](features/gridreplay.md)

### Outcome

Let the operator request and inspect durable GridReplay imports with the existing worker operating model.

### Done when

- Add protected bounded region/window submissions and status/audit visibility; reuse existing authentication and lease/fencing patterns without exposing controls to public visitors.
- Worker imports are limited, resumable, deduplicated and retryable under a documented policy; cancellation/restart cannot publish partial data as complete. Preserve price/simulation workload limits.
- Verify timeout/provider-error/restart/duplicate cases and document commands, progress and safe recovery. Optional-series failures remain distinguishable from core-data failure.

### Completion evidence

- **V5 schema** (`V5__grid_import_jobs.sql`): `grid_import_job` with the
  refresh queue's lease/claim-token fencing plus a durable `next_day`
  checkpoint, `optional_failures` counter, window CHECKs (1–31 days) and an
  active-window dedupe index; `grid_import_request` idempotency keys;
  `grid_import_job_event` audit.
- **`GridImportJobs`** (`infrastructure/.../grid/imports.py`): bounded
  submissions (1–31 completed days, ≤20 pending), one running import
  globally, lease renewal inside each `complete_day`, retryable core
  failures requeue at the checkpoint (≤3 attempts), optional power failures
  record FAILED attempts without blocking the window, cancellation revokes
  the claim.
- **Worker** (`worker/grid.py`): `--fetch-grid market|power` child mode on
  the cleared-environment isolated process; `GridFetchProcess` bounds
  runtime/output; `GridImportWorker` claims, then commits one market day
  per iteration. `NEMLAB_GRID_IMPORT_ENABLED`/`_POLL_MS` in settings; OE key
  required only when enabled.
- **API**: `/api/admin/v1/grid-imports` submit/list/status/events/cancel
  behind the existing `OperatorBearer`; no visitor surface. OpenAPI bumped
  to 1.4.0 with the five operations; verifier validates 78 captures/15 ops.
- Tests: `test_grid_jobs.py` (15), `test_grid_worker.py` (11 real child
  processes: timeout kills, no DB-credential inheritance, optional-power
  continuation, retry/recovery, shutdown recoverability),
  `test_grid_import_http.py` (8). Full suite 374 passed.

Committed as `b7cf536`.

<a id="nem-057"></a>

## NEM-057 — Implement the three deterministic event detectors

- Repository: backend
- Milestone: M5
- Priority: High
- Status: Done
- Depends on: [NEM-054](#nem-054)
- References: [Delivery specification](features/gridreplay.md)

### Outcome

Calculate negative-price runs, price spikes and scheduled-demand ramps from fixed versioned inputs.

### Done when

- Pure detector code implements the frozen rules and returns factual summaries, boundaries, required coverage and detector parameters/version.
- Hand-labelled tests cover exact thresholds, minimum length, no events, nonpositive ramps, equal maxima, missing observations, midnight and input chunk overlaps. Chunked and unchunked evaluation agree.
- Unresolved source edges do not become fabricated complete runs, and incomplete ramp domains do not produce unsupported daily-largest claims. No synthetic renewable ratio or causal title generator is introduced.

### Completion evidence

2026-10-02 — `nemlab_core/detectors.py` implements the frozen v1 rules from
decision 020 as pure code: `RunScanner` (stateful negative-run/spike run
detection with continuation across chunks — a gap in grid position, a null or
absent value, or a non-qualifying value closes a run; runs open at the
window's left edge or still open at `finish()` are `edge_incomplete`) and
`evaluate_demand_ramp` (per-day 36-step window, all-288-required completeness
else `insufficient_coverage`, earliest tie, no event on nonpositive max).
`DETECTOR_PARAMS`/`DETECTOR_VERSION` expose the canonical params for storage.

`core/tests/test_detectors.py` (21 tests) replays every `fixtures/gridreplay/`
file — strict thresholds (0 and 1000 do not qualify), minimum length,
no-event days, ties-to-earliest, absent/null interruption, cross-midnight
ownership, edge-incomplete flagging — plus chunked-vs-unchunked equivalence
at nine split points and single-interval/adjacent spike grouping. ruff,
format and mypy clean; full core suite 91 passed.

No synthetic renewable ratio or causal titles introduced.

<a id="nem-058"></a>

## NEM-058 — Publish versioned events and reproducible replays

- Repository: backend
- Milestone: M5
- Priority: High
- Status: Done
- Depends on: [NEM-055](#nem-055), [NEM-056](#nem-056), [NEM-057](#nem-057)
- References: [Delivery specification](features/gridreplay.md)

### Outcome

Produce a catalogue whose event links retain the same evidence after source refreshes.

### Done when

- Persist events and immutable replay snapshots/manifests with detector configuration and exact source revisions; publish complete catalogue versions atomically.
- Same inputs rerun without duplicates; corrected sources produce explicit new versions while retained old IDs still reproduce old evidence. Overlapping imports do not split or duplicate cross-midnight runs.
- Provide a bounded, auditable detection/publication operator job and coverage summary, including incomplete/skipped windows. Failure/retry cannot expose partial publication.
- Integration tests verify deduplication, corrections, snapshot retrieval, publication rollback and event-to-source provenance; define cleanup/reference protection before any deletion is enabled.

### Completion evidence

Done. `V6__grid_events.sql` adds immutable `grid_event` versions (identity
region/type/version/start_at, `supersedes` chains), materialised
`grid_replay` manifests bounded to 7 days, `grid_publication` +
`grid_publication_event`, the `grid_catalogue_current` pointer flipped inside
the same transaction, and `grid_detection_run` audit rows that survive
rollback for failed runs.
`infrastructure/src/nemlab_infrastructure/grid/events.py` runs the `v1`
detectors inside a REPEATABLE-READ transaction over pinned current revisions,
materialises exact values into replay payloads, dedupes identical reruns,
and supersedes on corrected inputs. `api/src/nemlab_api/grid_publications.py`
exposes `POST/GET /api/admin/v1/grid-publications` behind operator auth.
Retention: all event versions retained; deletion is not implemented and stays
blocked pending explicit reference-protection rules. Verified by
`test_grid_events.py` (15: dedupe, correction supersede, replay
materialisation/bounds, immutability triggers, failure rollback + audit) and
`test_grid_publication_http.py` (4). Contract: 86 responses, 18 operations.
Full suite 393 passed.

Committed as `81bde29`.

<a id="nem-059"></a>

## NEM-059 — Expose the GridReplay catalogue and replay contract

- Repository: both
- Milestone: M5
- Priority: High
- Status: In progress — backend contract done; frontend type sync and browser checks remain
- Depends on: [NEM-058](#nem-058)
- References: [Delivery specification](features/gridreplay.md)

### Outcome

Offer read-only typed public endpoints for catalogue filters, event details and bounded replay data.

### Done when

- Version OpenAPI schemas and generated frontend types for the proposed events/detail/replay resources, per-metric coverage, exact units/timestamps and immutable IDs.
- Define inclusive UI date overlap filtering, stable ordering, publication-pinned pagination and bounded replay windows. Unsupported coverage, no matches, missing optional series and missing/expired events are distinct.
- HTTP/contract tests cover invalid inputs, bounds, pagination under concurrent publication and saved-version reproducibility. Public reads never cause imports/detection and never return operator secrets.

### Completion evidence

In progress. `api/src/nemlab_api/events.py` adds read-only
`GET /api/v1/events` (region/type/inclusive-day overlap filters, page 24/100,
base64 cursor pinning the publication so a republish cannot shift pages),
`GET /api/v1/events/{id}` (immutable detail; superseded ids stay readable)
and `GET /api/v1/events/{id}/replay` (materialised snapshot, optional
validated sub-window). `GridCatalogue` gained `current_publication`,
`catalogue_events`, `event`, `replay_window` and bounded `replay`.
`CATALOGUE_NOT_PUBLISHED` vs empty page and `EVENT_NOT_FOUND` vs
`PUBLICATION_NOT_FOUND` (stale cursor) are distinct states. OpenAPI 1.4.0
gains 3 operations (21 total); verifier passes 103 captures.
`test_events_http.py` covers filters, pinned pagination across
republication, replay bounds and error states. Contract 1.4.0 verified;
frontend types regenerated (`7e38c3a` in nemlab-ui) and consumed by the
GridReplay client built under NEM-060 with full browser coverage.

<a id="nem-060"></a>

## NEM-060 — Build the demo-faithful GridReplay interface

- Repository: frontend
- Milestone: M5
- Priority: High
- Status: Done
- Depends on: [NEM-054](#nem-054)
- References: [Delivery specification](features/gridreplay.md)

### Outcome

Establish the real React page visually against the demo before live backend integration is complete.

### Done when

- Match the demo catalogue filters/card hierarchy, selected card, replay heading/BatteryLab action, Play/speed/scrub/clock row, readout strip, four chart cards and quiet provenance using the specification fidelity matrix.
- Preserve centered 1440px workspace/shared header and shared Light/Dark/Auto behavior; test semantic controls, keyboard focus, mobile wrapping and chart legends.
- Exercise typed complete/gapped/empty/error fixtures in browser tests or an explicit development harness only. The public page must not show synthetic events as real.
- Use computer-use screenshots side by side with the demo at matching desktop, 768px, 390px and 320px sizes in both themes. Record deliberate differences and correct visual mismatches before integration acceptance.

### Completion evidence

Done. `nemlab-ui/apps/public/src/gridreplay/` adds a strict openapi-fetch
client (catalogue + replay validation, same-origin, no credentials,
15s timeout), `GridReplayWorkspace` (region/type/date filters, event cards
with detector badge/type/title, interval count, duration, extreme value,
coverage state, detector version and source revisions, pinned "Show more
events" pagination) and `ReplaySection`/`ReplayCharts` (four shared-cursor
ECharts panels — price, demand, generation by fueltech, interconnector
flow — with event markArea, Play/Pause, three speeds, slider scrub,
pointer/touch and arrow-key cursor control, exact-string readouts and a
provenance details disclosure). Badge palette and card hierarchy matched
to `docs/demos/gridreplay/index.html`; screenshots compared against the
demo at 1440/768/390/320px in light and dark. Deliberate differences:
renewable-share readout uses real observed series (the demo's synthetic
formula was not copied); causal labels omitted by design. 16
fixture-driven Playwright tests in `tests/gridreplay.spec.ts` cover
complete/gapped/empty/error catalogue states, replay loading, cursor and
pagination; all synthetic data stays in test fixtures.

<a id="nem-061"></a>

## NEM-061 — Connect catalogue and synchronized replay to real data

- Repository: frontend
- Milestone: M5
- Priority: High
- Status: Done
- Depends on: [NEM-059](#nem-059), [NEM-060](#nem-060)
- References: [Delivery specification](features/gridreplay.md)

### Outcome

Replace the empty public shell with the stored catalogue and working replay interactions.

### Done when

- Wire region/type/date filters and bounded pagination to public endpoints with cancellation, loading, retry and truthful coverage/no-match states; opening a card selects and focuses the replay below the catalogue.
- Render available price/demand/generation/flow panels automatically with event shading and one timestamp/window state. Preserve per-metric gaps/semantics and signed values; do not claim balance or causal alignment.
- Play/Pause, three speeds, pointer/touch, keyboard scrub and bounded window changes keep charts/readouts synchronized. Stop at the end and pause on manual scrub, event change, hidden tab and navigation.
- Browser tests verify those behaviors, missing optional context, reduced motion, chart failures, theme changes and responsive overflow; inspect actual UI through computer use.

### Completion evidence

Done on the real stack. Rehearsal: `POST /api/v1/admin/grid-imports` ran
NSW1 2023-09-01..30 through the worker (job SUCCEEDED, ~75s for 30 days);
30 per-day price refreshes supplied the separate price store;
`POST /api/v1/admin/grid-publications` produced publication
`c81f0287-…` with 99 real events, including the 2023-09-04 spike
(`47af4f63-…`, value 16599.89 — replay `price[210]` verified). The Vite
proxy now covers `/api/v1/events` for live development. Client validation
was corrected against real payloads (replay manifest omits `series` when
absent; `pumps` fueltech mapped). Play/Pause/speeds/scrub, pointer/touch,
arrow keys, end-of-replay stop, pause-on-scrub and
pause-on-hidden-tab (`visibilitychange`) are implemented; missing series
render as gaps. 124 Playwright tests pass including theme changes,
missing-catalogue, stale-cursor and removed-event states. Known
limitations carried to NEM-064: no prefers-reduced-motion playback
adjustment, no chart-render-failure fixture, max-window payload/render
measurement outstanding.

<a id="nem-062"></a>

## NEM-062 — Share replays and open the correct BatteryLab day

- Repository: frontend
- Milestone: M5
- Priority: High
- Status: Done
- Depends on: [NEM-061](#nem-061)
- References: [Delivery specification](features/gridreplay.md)

### Outcome

Make an investigation reloadable and complete the catalogue-to-BatteryLab journey.

### Done when

- Implement validated event/filter URL state with direct loads, saved immutable event links, reload and Back/Forward; playback ticks do not flood browser history.
- Place the BatteryLab link as in the demo; display/select the NEM day for cross-midnight events and define midnight price-interval ownership explicitly.
- BatteryLab accepts valid region/day prefills without submitting; saved simulation IDs take precedence. Invalid/unsupported parameters produce a useful recovery state.
- Browser and live journey checks cover same-day, cross-midnight, final 00:00, user timezone differences, missing event/price coverage and unchanged saved BatteryLab links.

### Completion evidence

Done (nemlab-ui `6afc7d3`). Catalogue filters (region/type/from/to) and
the selected event are URL-driven: direct loads, reload, Back/Forward and
copy-link reproduce the view; playback ticks never touch history. Invalid
query values fall back to defaults without a request for the bogus value.
`?day=` on `/batterylab` prefills valid completed market days and reports
ignored ones; the existing `?simulation=` restore path is unchanged and
still takes precedence by simply running. Replay heading links
"Open in BatteryLab" with the event's market day (UTC+10), which is the
owning day for cross-midnight events; instants are interval-end
timestamps so a 00:00-owned event links its own day. New browser tests:
filter/event URL round-trip, invalid-param fallback, BatteryLab day
prefill — 124/124 pass.

<a id="nem-063"></a>

## NEM-063 — Rehearse GridReplay operations and decide Admin scope

- Repository: both
- Milestone: M5
- Priority: Normal
- Status: Done
- Depends on: [NEM-056](#nem-056), [NEM-058](#nem-058), [NEM-059](#nem-059)
- References: [Delivery specification](features/admin.md)

### Outcome

Prove an operator can maintain both products and make an explicit include/defer decision for Admin UI.

### Done when

- Exercise authenticated coverage inspection, bounded price/grid import, status/audit, safe failed-job recovery, cancellation where supported, detection/republication and old-link preservation.
- Verify unauthorized requests fail and repeated submissions do not create duplicate logical work. Distinguish automatic worker retry from a supported manual resubmission; document any missing operation rather than claiming an existing retry endpoint.
- Record commands, actual results, usability pain points and required fixes. Split material gaps into new tasks before marking the rehearsal done.
- Recommend include/defer with evidence and record the final scope decision explicitly. If UI is included, scope authentication/session handling and create separate implementation tasks; NEM-019 remains open until they pass. If deferred, retain the tested operator alternative.

### Completion evidence

Done. Full live rehearsal recorded in
[evidence/m5-ops-rehearsal.md](evidence/m5-ops-rehearsal.md): 401s for
missing/wrong tokens; idempotency-key replay returns the same job while
reuse on a different window is rejected (`IDEMPOTENCY_CONFLICT`) and an
identical active window dedupes to the running job; cancellation of a
queued job is audited (`SUBMITTED → CANCELLED`) and clears the claim
fence; a pre-NEM window fails permanently
(`INVALID_SOURCE_DATA_OR_CONFIGURATION`, no retry); a SIGKILLed worker
mid-import recovered via lease expiry and resumed from the `next_day`
checkpoint to SUCCEEDED; republication minted a new publication while
event ids, detail and replay payloads stayed pinned and reproducible.
Manual recovery is a fresh keyed `POST` — there is no in-place retry
endpoint (documented, not claimed). Rehearsal fix: admin validation
errors now name the missing field (e.g. `Missing header
'idempotency-key'`). Gap split to [NEM-082](#nem-082) (grid coverage
inspection). **Admin decision: deferred** —
[decision 021](decisions/021-admin-ui-deferred.md); the tested endpoint
runbook is the deliverable.

<a id="nem-064"></a>

## NEM-064 — Verify the GridReplay journey and M5 exit criteria

- Repository: both
- Milestone: M5
- Priority: High
- Status: Backlog
- Depends on: [NEM-061](#nem-061), [NEM-062](#nem-062), [NEM-063](#nem-063)
- References: [Delivery specification](features/gridreplay.md)

### Outcome

Close M5 only when the real-data journey, demo fidelity and Admin decision are evidenced.

### Done when

- Rehearse a bounded real NSW1 import→detection→publication→catalogue→replay→BatteryLab flow and record the actual supported period. Retain reproducible fixture versions of key failure/boundary cases.
- Run relevant backend, migration, contract, frontend and live checks; measure maximum-window payload/render/playback behavior and fix observed bottlenecks.
- Review demo-matched desktop/mobile screenshots in light/dark/auto, keyboard/touch interaction, unavailable metrics and factual event copy. Record limitations and intentional differences.
- Review NEM-018/NEM-019 acceptance. If an Admin UI is included, its added tasks are additional dependencies before closure. Update M5 status only when all required evidence passes; preserve hosted CI and public launch/retention/security gates under M6 and NEM-038.

### Completion evidence

Planned only; no implementation or verification evidence yet.


<a id="nem-082"></a>

## NEM-082 — Expose grid-observation coverage inspection

- Repository: backend
- Milestone: M5
- Priority: Normal
- Status: Ready
- Depends on: [NEM-055](#nem-055)
- References: [Rehearsal gap](evidence/m5-ops-rehearsal.md)

### Outcome

Let an operator see which grid days/series are stored without creating a
publication.

### Done when

- An admin-scoped endpoint returns per-day, per-metric/series coverage
  (evaluated/missing or revision presence) over a bounded window,
  mirroring the price-coverage shape.
- Contract and HTTP tests cover bounds and empty coverage; the runbook
  references it for pre-import inspection.

### Completion evidence

Gap identified in the NEM-063 rehearsal; not yet implemented.

<a id="nem-092"></a>

## NEM-092 — Accept bounded date-range price refreshes

- Repository: backend
- Milestone: Post-M5 operator tooling
- Priority: Normal
- Status: Done
- Depends on: None (existing refresh queue)
- References: [runbook-grid-data.md](runbook-grid-data.md), [features/admin.md](features/admin.md)

### Outcome

Replace the per-day fan-out callers must run today with one bounded-window
submission, so backfilling e.g. Sept-2023 × 5 regions is 5 requests instead of
150, without growing a second queue or changing worker claim semantics.

### Plan

- Extend `POST /api/admin/v1/price-refreshes` to accept either `{region, day}`
  (current shape) or `{region, startDay, endExclusive}` — an OpenAPI `oneOf`,
  so existing callers keep working. Window bound mirrors grid imports:
  1–31 completed market days (the `price_backfill` primitive already accepts a
  start/end window).
- `RefreshJobService.submit_window` fans out to one `refresh_job` per market
  day **inside a single transaction**, deriving per-day idempotency keys as
  `{key}:{day}`. This composes with existing dedup for free: same key + same
  window → every day resolves to its existing job → identical response; same
  key + different window → the overlapping day's `RequestKeyConflict` surfaces
  as `IDEMPOTENCY_CONFLICT` (decide: reject the whole window, not partial).
- Pending-cap check applies per inserted row; with `MAX_PENDING_JOBS=1000` a
  31-day submission is safe, but a partially-queued failure must roll back the
  whole transaction (all-or-nothing is what makes the response honest).
- Response shape: `202` + `{jobs: [JobView…]}` for windows, unchanged
  `JobView` + `Location` for single-day. `GET .../{id}`, `events`, `cancel`
  keep working per job — no new read surface needed.
- Rejected alternative: a windowed *job type* with a day checkpoint (the
  grid-import model). Unnecessary — per-day jobs are already individually
  retryable and a day is the natural recovery unit here.
- Update `runbook-grid-data.md` Phase 2, OpenAPI contract and captures; note
  in `features/admin.md` that the Admin UI "refresh a range" form maps to one
  call.

### Done when

- Windowed submission accepts 1–31 completed days, validates bounds, and
  inserts one deduplicated job per day in one transaction.
- Idempotency verified: identical resubmission returns the same job set;
  changed window under the same key conflicts; partial-failure rollback leaves
  no orphan jobs.
- Contract regenerated and HTTP/service tests cover bounds, dedup, window
  overlap and the cap; runbook Phase 2 updated; journal entry recorded.

### Completion evidence

Implemented 2026-10-08 per the plan above. `RefreshJobService.submit_window`
fans out one `refresh_job` per market day in a single queue-locked
transaction with derived keys `{key}:{day}` plus a bare-key marker pinning
the window; identical resubmission returns the same job set, a changed
window/region under the same key raises `RequestKeyConflict`, and a cap
overflow mid-window rolls back atomically. The API accepts
`{region, day}` or `{region, startDay, endExclusive}` (OpenAPI `oneOf`);
window responses are `202 {"jobs": [...]}` in day order. Bounds mirror grid
imports (1–31 completed days, ≥ 2021-10-01). Verified: 5 new service tests +
2 HTTP tests (dedup, conflicts, bounds, rollback, per-job cancel);
contract `oneOf` + `JobSet` schema regenerated, 115 captures / 23 operations
validated; full suite green; runbook Phase 2 updated.

<a id="python-rebuild-tasks"></a>

## Python rebuild tasks

Added 2026-10-01. Scope and stack are accepted; implementation has not started. Historical Done tasks describe the Java delivery and remain intact. Promote dependencies to Ready as their gates pass.

<a id="nem-065"></a>

## NEM-065 — Freeze the Java parity baseline and executable reference cases

- Repository: both
- Milestone: Python backend rebuild
- Priority: High
- Status: Done
- Depends on: None
- References: [Rebuild plan](python-backend-rebuild.md), [decision 019](decisions/019-python-backend-rebuild.md); capability-specific Java/spec references in the plan.

### Outcome

Capture the exact delivered behavior before moving or replacing implementation.

### Done when

- Record backend/frontend revisions, working-tree state, all routes, environment flags/defaults, commands, SQL objects and Java test inventory in evidence/python-rebuild/parity.md; preserve unrelated user edits.
- Read the linked specs/decisions and Java production/tests for every capability; list discrepancies with their resolution or open gate.
- Run the baseline Java build/contract/startup and available frontend checks; capture sanitised HTTP, canonical-hash, engine and old/new saved-result fixtures with generation commands and provenance. Report unavailable checks honestly.
- Inventory populated-database/queue compatibility requirements and prerequisites (JDK, Node, Docker/PostgreSQL, Python wheels); keep database snapshots outside Git.

### Completion evidence

2026-10-01: [Parity baseline](evidence/python-rebuild/parity.md) records backend `e93142c`, frontend `b48295e`, working-tree state, toolchain, 10 routes, 14 environment flags/defaults, command/schema/test inventories, operational constants and the capability parity matrix. Baseline verification: `gradlew clean build --offline` 150 tests pass; contract check validated 120 HTTP captures across 10 operations; `smoke_apps.py` passed; frontend `npm run check` passed (102 browser tests) after installing Playwright chromium (initial failure was a missing browser, not a regression); `npm run test:live` passed all 6 real-stack cases. Frozen fixtures under `evidence/python-rebuild/fixtures/` via the new `:infrastructure:parityExport` Gradle task (`infrastructure/.../parity/ParityExport.java`), covering decimal canonicalisation, request normalisation/errors, content hashes, scenario-key inputs, 10 full strategy runs and stored two-/three-strategy result JSON; legacy two-strategy shape reconstructed by removing the `threshold` key (recorded as representative, not provenance-captured). No live OE calls beyond the harness's designed 401 path; unrelated user edits preserved. Changes uncommitted.

<a id="nem-066"></a>

## NEM-066 — Preserve Java as a runnable reference in the existing repository

- Repository: backend
- Milestone: Python backend rebuild
- Priority: High
- Status: Done
- Depends on: [NEM-065](#nem-065)
- References: [Rebuild plan](python-backend-rebuild.md), [decision 019](decisions/019-python-backend-rebuild.md); capability-specific Java/spec references in the plan.

### Outcome

Move only Java-specific tracked assets to reference/java while preserving repository history and stable shared paths.

### Done when

- Inventory tracked/hidden files and use git mv for Java module sources/tests/resources, Gradle files/wrapper/locks and Java module READMEs; leave docs, .git, api/contracts, root configuration and user files in place.
- Preserve the Java smoke script/workflow as reference assets; document baseline SHA, old-to-new paths, setup and commands. Keep a separately reviewable move diff.
- Run reference Java build and startup/contract verification with repaired paths; no secrets, caches, build output or database volumes enter the reference tree.

### Completion evidence

2026-10-01: All Java-specific tracked assets moved to `reference/java/` via `git mv` (rename history preserved): `core/`, `infrastructure/`, `api/` module sources/tests/resources/READMEs/lockfiles, root `build.gradle`/`settings.gradle`/wrapper/`gradle/`, `scripts/smoke_apps.py`, and `.github/workflows/backend.yml` → `reference/java/ci/backend.yml` (repaired to `working-directory: reference/java`; it is a reference copy — hosted CI is NEM-078's gate). `api/contracts/`, `docs/`, `compose.yaml`, `.env*` and user files stay at the root. Path repairs: module `build.gradle` files resolve evidence/contract output via `../../` to the repo root; contract captures still land at `api/build/contract-responses/` so `api/contracts/verify.mjs` is unchanged. Doc link repairs across README, `running-locally.md`, `api/contracts/README.md`, architecture, features, evidence and decision files; parity.md carries a pre-move layout note. New [reference README](../../reference/java/README.md) records baseline SHA, old→new path map, setup and commands. Verification from `reference/java/` with JDK 25: `./gradlew clean build --offline` passes (150 tests, module boundaries, contract check validating 120 captures against the unchanged root `api/contracts/`); `python3 scripts/smoke_apps.py` passes packaged api+worker startup. No secrets, caches, build outputs or database volumes moved into the reference tree. Committed as `ca7a66161a55dd257c81202564c347f89514ea2a`.

<a id="nem-067"></a>

## NEM-067 — Bootstrap the four Python packages and independent applications

- Repository: backend
- Milestone: Python backend rebuild
- Priority: High
- Status: Done
- Depends on: [NEM-066](#nem-066)
- References: [Rebuild plan](python-backend-rebuild.md), [decision 019](decisions/019-python-backend-rebuild.md); capability-specific Java/spec references in the plan.

### Outcome

Create a locked uv workspace matching core/infrastructure/api/worker boundaries.

### Done when

- Provision SQLAlchemy 2 Core with Psycopg 3; infrastructure owns explicit transaction contexts and one bounded Engine pool per process, without a second psycopg_pool or domain ORM dependencies.
- Pin a supported CPython 3.13 patch, uv and stable compatible dependencies after Linux wheel/license checks; commit-ready pyproject files and uv.lock resolve reproducibly.
- Provide API, worker and migration entry points; API starts with disabled optional features and no credentials; worker stays non-HTTP, idle by default, and shuts down cleanly.
- Enforce imports: core independent of apps/persistence/web; infrastructure may depend on core; API/worker may depend on both but not each other. Configure Ruff, mypy, pytest and import-linter.
- Validate a clean locked install, both process entry points, health compatibility and invalid-configuration diagnostics.

### Completion evidence

2026-10-01: uv workspace at repo root — CPython **3.13.14** pinned via `.python-version`, `required-version >=0.11.0`, one `uv.lock`, four packages matching the Java boundaries: `nemlab-core` (SciPy), `nemlab-infrastructure` (SQLAlchemy 2.1 Core, `psycopg[binary]` 3.3, Alembic 1.20, pydantic-settings, httpx), `nemlab-api` (FastAPI 0.141, uvicorn 0.53), `nemlab-worker` (httpx). `DatabaseSettings` accepts the existing `jdbc:postgresql://` `NEMLAB_DB_URL` unchanged and translates to `postgresql+psycopg://` with credentials; all Java `NEMLAB_*` flags keep identical names/defaults (features off, polls 5000 ms, regions NSW1); API binds `SERVER_ADDRESS`/`PORT` like Spring. One bounded QueuePool Engine per process (`pool_size=5, max_overflow=5, timeout=30s, pre_ping`); no `psycopg_pool`, no ORM. Entry points: `nemlab-api` serves `GET /actuator/health` → `{"status":"UP"}` (feature routes unmounted → 404 while disabled), `nemlab-worker` idles non-HTTP and exits 0 on SIGTERM, `python -m nemlab_infrastructure.migrate {migrate,check,stamp}` runs Alembic against `migrations/`; invalid env (bad int/bool/URL) exits 2 with per-field diagnostics. import-linter `layers` contract enforces `api|worker → infrastructure → core`. Verified: fresh `uv lock` + `uv sync --all-packages --locked` reproducible (53 packages, Linux wheels incl. psycopg-binary/scipy/pydantic-core), `pytest` 17 pass, `ruff check`/`format`, `mypy --strict` (12 files), `lint-imports`, live API health+404 surface, worker SIGTERM, Alembic online `check` against compose Postgres :55432. Version-age policy applied: fastapi pinned `<0.142` (0.142.x <7 days old), uvicorn `<0.54`, sqlalchemy `<2.1.1`, hypothesis `<6.168.2` — resolved versions all ≥7 days old (verified via PyPI upload times). Licences: MIT (fastapi, sqlalchemy, alembic, pydantic, pydantic-settings), BSD (uvicorn, scipy, httpx, starlette), LGPL-3.0-only (psycopg/psycopg-binary — unmodified library use, accepted). Dev tools: pytest 9.1, hypothesis, ruff 0.16, mypy 2.3, import-linter 2.15, pytest-asyncio, httpx. Note: `ruff` excludes `reference/` and `docs/` (historical scripts); Starlette deprecation warning on httpx TestClient is upstream-only. Committed as `64041a9bb499bb12793bf2d6ec4c06e859d962a5`.

<a id="nem-068"></a>

## NEM-068 — Port request semantics and deterministic battery strategies

- Repository: backend
- Milestone: Python backend rebuild
- Priority: High
- Status: Done
- Depends on: [NEM-067](#nem-067)
- References: [Rebuild plan](python-backend-rebuild.md), [decision 019](decisions/019-python-backend-rebuild.md); capability-specific Java/spec references in the plan.

### Outcome

Implement exact market-day/request boundaries, fixed schedule, threshold strategy and accounting.

### Done when

- Port PriceDay, Battery, Efficiency, ScheduleWindows, SimulationRequest, Thresholds, FixedSchedule, PriceThreshold, DispatchValidator and Accounting using specs plus Java tests.
- Preserve 288 interval-end slots, fixed UTC+10, decimal canonical strings/hashes, numeric bounds, null/missing rules, negative prices and strict threshold equality behavior.
- Compare fixed/threshold interval outputs and accounting to frozen Java fixtures under existing tolerances; independently test physical limits, terminal-energy rules, fees/losses and property invariants.
- Old requests without thresholds remain valid; thresholds keep unrestricted daily operation and unforced final energy.

### Completion evidence

- `core/src/nemlab_core/` ports all named types across `decimal_text.py` (BigDecimal-grammar parse, sign-free zero, manual trailing-zero strip avoiding `Decimal.normalize` 28-digit context rounding), `numbers.py`, `prices.py` (288 slots, fixed UTC+10, contiguous 5-minute ends), `battery.py`, `windows.py`, `dispatch.py`, `accounting.py`, `fixed.py`, `threshold.py` (strict `<`/`>` equality-hold semantics, unrestricted daily operation, unforced terminal energy), `request.py` (normalise + canonical strings, structured field/code errors, optional threshold pairs, legacy two-strategy requests still valid).
- `tests/parity/test_java_parity.py` replays `docs/project/evidence/python-rebuild/fixtures/parity-fixtures.json` — 56 cases covering decimal forms, request normalisation/error codes, content hashes, canonical strings, and all 10 frozen strategy runs with bitwise-exact interval dispatch and accounting for fixed and threshold strategies.
- `core/tests/test_engine.py` and `core/tests/test_threshold.py` port the Java unit/property coverage: physical limits, terminal-energy rules, fees/losses, validator rejections, negative prices, equality-hold; sampled real OE CSV days feed the property checks.
- Verification: `uv run pytest` 120 passed; `uv run ruff check`/`ruff format --check` clean; `uv run mypy` clean (22 files); `uv run lint-imports` kept. `pyproject.toml` per-file-ignores extended for test S311 and `request.py` post-validation asserts (S101).
- The solver (`OrderedHindsight`) remains NEM-069 scope; no solver code was ported here.

<a id="nem-069"></a>

## NEM-069 — Prove the Python ordered-hindsight solver and budgets

- Repository: backend
- Milestone: Python backend rebuild
- Priority: High
- Status: Done
- Depends on: [NEM-068](#nem-068)
- References: [Rebuild plan](python-backend-rebuild.md), [decision 019](decisions/019-python-backend-rebuild.md); capability-specific Java/spec references in the plan.

### Outcome

Replace ojAlgo with a verified HiGHS LP adapter without changing the comparison model.

### Done when

- Port the actual ordered-window primal and independent dual certificate; verify objective/marginal signs and reconstruct dispatch/accounting independently.
- Match exact synthetic optima and sampled-day objective/bounds under existing tolerances; tied optima may differ in dispatch only when independently feasible and equally optimal.
- Test infeasible/error/unproven/time/iteration-limit cases, nonfinite output and invalid certificates; only certified OPTIMAL results publish.
- Benchmark cold/warm 288-interval cases and abort probes against five-second cooperative and 15-second parent targets; record runtime/native-library versions and evidence. Any failure blocks solver acceptance, not a silent limit increase.
- Select truthful Python solver/execution version metadata and prove scenario keys change when execution identity changes.

### Completion evidence

- `core/src/nemlab_core/hindsight.py` ports the stored-energy primal (exact +1/-1 balance) and the independent dual-certificate LP onto `linprog(method="highs-ds")` — HiGHS 1.12.0 via SciPy 1.18.1. `time_limit`/`maxiter` carry the 5000 ms / 100000-iteration cooperative budgets; feasibility tolerances set to 1e-9, inside the 1e-7 validator tolerance. `dual_upper_bound` re-evaluates the bound in `Decimal` + `nextafter` exactly as Java; `comparison.py` ports `SimulationComparison.run/validate` so only certified OPTIMAL outcomes publish dispatch.
- Evidence: `docs/project/evidence/python-rebuild/solver.md` — versions, LP formulation, measured budgets (import ~255 ms, cold solve ~6 ms, warm 2.4–4.0 ms vs the 5 s budget; abort probes for ms=0/iters=0/1ms/iter-limits all return NO_SOLUTION or unproven-with-dispatch, never false OPTIMAL).
- Parity: `test_hindsight_runs` replays all 10 frozen runs — OPTIMAL status/state, objectives, bounds and gaps reconcile, dispatches independently validate; vertices may differ on ties (documented). `test_scenario_keys_change_with_python_execution_identity` proves key sensitivity to solver identity (`SOLVER = "HiGHS 1.12.0 via SciPy 1.18.1 linprog/highs-ds"`).
- `core/tests/test_hindsight.py` ports all HindsightTest cases (manual optima, enumeration oracle, fractional efficiency, large-allowance unproven, denormal-overflow FAILED_VALIDATION, dual-bound robustness) plus warm-timing and abort probes; `test_comparison.py` ports SimulationComparisonTest. `sys.float_info.min` is *not* Double.MIN_VALUE — the denormal-overflow case uses `math.nextafter(0.0, 1.0)`.
- Verification: `uv run pytest` 153 passed; `ruff check`/`format --check`/`mypy` (24 files)/`lint-imports` clean. mypy `scipy.*` `ignore_missing_imports` override added (no stubs shipped).

<a id="nem-070"></a>

## NEM-070 — Adopt the existing PostgreSQL schema with Alembic

- Repository: backend
- Milestone: Python backend rebuild
- Priority: High
- Status: Done
- Depends on: [NEM-067](#nem-067)
- References: [Rebuild plan](python-backend-rebuild.md), [decision 019](decisions/019-python-backend-rebuild.md); capability-specific Java/spec references in the plan.

### Outcome

Support both empty databases and validated populated Java database clones without data loss.

### Done when

- Use the selected SQLAlchemy/Psycopg migration connection; verify transaction/DDL behavior on the supported PostgreSQL version.
- Port V1–V3 schema semantics including immutable triggers, checks, indexes and functions into an explicit Alembic baseline; preserve original Flyway SQL in Java reference.
- Provide verified adoption: check Flyway versions/checksums and schema before stamping; refuse unknown/drifted/partial databases; preserve Flyway history and never replay create DDL on an existing schema.
- Test fresh upgrade, repeated upgrade, transaction failure and populated-clone adoption with old results/revisions/audits intact using real PostgreSQL.
- Document explicit single-run migration, backup and restore rehearsal commands; no automatic app-start migration or destructive live reset.

### Completion evidence

- The Java V1–V3 SQL is the single source: packaged byte-identically at `infrastructure/src/nemlab_infrastructure/db/migration/` and replayed verbatim by the Alembic baseline `migrations/versions/nemlab_baseline_v1_v3.py`; the original Flyway scripts remain in `reference/java/infrastructure/src/main/resources/db/migration/`.
- `infrastructure/src/nemlab_infrastructure/schema.py` reproduces Flyway 12.x `ChecksumCalculator` (per-readLine CRC32, terminators excluded, per-line BOM strip, UTF-8, signed int32) — verified against real `flyway_schema_history` checksums produced by Flyway 12.4.0 on PostgreSQL 18.6: V1 `-1351753437`, V2 `581062717`, V3 `-144120848`.
- Adoption validates history rows (exactly V1–V3, ordered, `success=true`, checksums recomputed from the packaged bytes) plus live schema: tables, columns (name/type/nullability), per-kind constraint counts, triggers, functions, indexes. Refuses empty (→ `migrate`), unknown (no Flyway history), partial, and drifted databases; stamps `nemlab_baseline_v1_v3` without replaying DDL; `flyway_schema_history` preserved.
- CLI: `python -m nemlab_infrastructure.migrate` with `migrate` / `check` / `adopt` / `stamp` — explicit single-run commands; no app performs migrations on startup. Operator docs incl. backup/restore rehearsal in `infrastructure/README.md`; `docs/project/running-locally.md` and `README.md` updated.
- Verified on real PostgreSQL 18.6 (`postgres:18.6-alpine`, compose service + scratch container): Java `migrate` output adopted end-to-end via the CLI (`check` → `adopt` → `alembic_version` = baseline, 3 history rows intact); fresh empty DB `migrate` produced all 11 tables, 6 triggers, 3 functions, indexes — identical manifest to the Java schema.
- `infrastructure/tests/test_schema.py` (20 tests): pinned checksums vs packaged + reference-tree bytes, CRLF/BOM handling, history-row unit cases (checksum drift, failed row, partial, extra), and DB-backed cases — empty/unknown states, fresh migrate satisfying the same manifest adoption validates, repeated upgrade no-op, adopt preserving a populated `price_revision` row, refusals on dropped trigger, dropped table and tampered checksum, and transactional rollback (failed upgrade on an unadopted Java DB leaves no `alembic_version`, schema and history untouched, still adoptable).
- Full suite: `uv run pytest` 173 passed; `ruff check`/`ruff format --check`/`mypy`/`lint-imports` clean.
- Committed as `c77ae99` — new `schema.py`, baseline revision, `db/migration/*.sql`, `migrate.py` actions, `test_schema.py`, `infrastructure/README.md`.

<a id="nem-071"></a>

## NEM-071 — Port OE prices, immutable revisions and resumable backfill

- Repository: backend
- Milestone: Python backend rebuild
- Priority: High
- Status: Done
- Depends on: [NEM-068](#nem-068), [NEM-070](#nem-070)
- References: [Rebuild plan](python-backend-rebuild.md), [decision 019](decisions/019-python-backend-rebuild.md); capability-specific Java/spec references in the plan.

### Outcome

Restore bounded source retrieval and revision/coverage/snapshot persistence.

### Done when

- Implement repositories through SQLAlchemy Core/parameterised SQL on the shared Engine; preserve exact Decimal mappings and avoid ORM entities crossing boundaries.
- Read OePriceSource, PriceBatch, PriceStore, PriceBackfill and CLI tests plus data-foundation specification; preserve bounded windows, interval labels, validation and credential isolation.
- Prove Java-equivalent content hashes and exact decimal values; preserve missing/source-null/zero distinctions, corrections, idempotency, provenance and snapshot references.
- Port resumable checkpoint/status behavior through the supported queue boundary; do not revive retired direct production ingestion bypasses.
- Test source failures, oversized/truncated payloads, duplicates/gaps, incomplete days and concurrent corrections on fixtures and real PostgreSQL; existing snapshots must stay unchanged.

### Completion evidence

- New `infrastructure/src/nemlab_infrastructure/prices/` package ports the Java `au.nemlab.infrastructure.prices` classes: `batch.py` (`PriceBatch`/`Slot`/`Kind`, 288-slot invariant, BigDecimal precision/scale/finiteness gate via `decimal_text`, exact `contentHash` canonical string, `to_price_day`), `source.py` (`Fetch` + `OePriceSource` on httpx — 3 attempts, `1000<<attempt` backoff, `Retry-After` seconds/RFC-1123 honoured with the 60 s ceiling, 2 MiB stream cap, key only in `Authorization` header, strict `parse` preserving MISSING vs SOURCE_NULL), `store.py` (`PriceStore` on SQLAlchemy Core parameterised text — byte-equivalent statements incl. `ON CONFLICT` idempotent revision insert, `retrieved_at <=` freshness guard on `price_current`, attempts audit, snapshot/coverage/history reads, `create_backfill` bounds, `commit_day` optimistic `next_day` fence, `record_failure` with safe diagnostics), `backfill.py` (`PriceBackfill.step` with `HTTP_*`/transport codes and `FETCH_OR_STORAGE_FAILED:<type>`), `cli.py`/`__main__.py` (`python -m nemlab_infrastructure.prices` — `start`/`resume` exit 2 retired; `status`/`history`/`coverage`; sanitised error output).
- `content_hash` parity proven against the frozen Java fixtures: both CSV days reproduce the pinned `contentHash` values bitwise (`test_content_hash_matches_java_fixtures`).
- `infrastructure/tests/test_price_ingestion.py` (16 tests) ports `PriceIngestionTest` on real PostgreSQL 18.6 via per-test `nemlab_test_*` scratch DBs: fixture boundary/exact prices, idempotent saves + snapshot surviving a correction + immutability triggers rejecting UPDATE/DELETE, freshness fencing (older fetch loses, reverted content reuses revision), MISSING/SOURCE_NULL/zero distinct and unsnapshotable, crash/restart resume from persisted `next_day` with secret-free diagnostics, incomplete-day pause, data+checkpoint atomic rollback under an injected trigger failure, stale-checkpoint and unbounded-date rejection, parser metadata/duplicate/malformed/missing-vs-null cases, stdlib-HTTP-server retry/Retry-After/secret tests (401 once; 503/429 three attempts; 2 MiB+1 body cancelled → `TRANSPORT_RETRIES_EXHAUSTED`), 4-thread concurrent idempotent saves, and operator-status diagnostic safety.
- `infrastructure/tests/test_price_command.py` ports `PriceImportCommandTest` — subprocess `start`/`resume` exit 2 with the retired message and no env names.
- Direct production ingestion bypasses stay retired; resumable checkpoint/status goes through `price_backfill` as in Java (worker fencing is NEM-072).
- Full suite: `uv run pytest` 190 passed; `ruff check`/`ruff format --check`/`mypy`/`lint-imports` clean. Shared `scratch_db` fixture extracted to `infrastructure/tests/conftest.py`.
- Committed as `23d7cd3` — new `prices/` package, `test_price_ingestion.py`, `test_price_command.py`, `conftest.py` refactor.

<a id="nem-072"></a>

## NEM-072 — Port fenced refresh jobs and visitor admission

- Repository: backend
- Milestone: Python backend rebuild
- Priority: High
- Status: Done
- Depends on: [NEM-070](#nem-070), [NEM-071](#nem-071)
- References: [Rebuild plan](python-backend-rebuild.md), [decision 019](decisions/019-python-backend-rebuild.md); capability-specific Java/spec references in the plan.

### Outcome

Recreate durable refresh transitions, audit and bounded public refresh submissions.

### Done when

- Verify queue locks and fencing through actual SQLAlchemy transaction contexts, including rollback and pooled-connection reuse.
- Port RefreshJobService and queue tests: advisory/row locks, claim tokens, leases, cancellation, atomic import/checkpoint/completion, deduplication, capacity, retry/backoff and recovery.
- Preserve server-derived actors, stable request keys and visitor eligibility/day-attempt/global-cap rules from current code.
- Use real PostgreSQL concurrent tests for competing claims/submissions, expired stale writers, cancellation races, rollback and retry exhaustion; no network work inside transactions.
- Confirm existing job/audit records remain readable after schema adoption.

### Completion evidence

- New `infrastructure/src/nemlab_infrastructure/jobs.py` ports `RefreshJob`/`RefreshJobService` onto SQLAlchemy Core: identical constants (`MAX_PENDING_JOBS=100`, `MAX_ATTEMPTS=3`, `LEASE_SECONDS=300`, `MAX_VISITOR_PENDING=10`, `MAX_VISITOR_ATTEMPTS=3`, `visitor-price-v1:` keys, advisory `pg_advisory_xact_lock(735028)`), label/diagnostic validators, request-key dedup + `RequestKeyConflict`, shared-queue capacity, active-job aliasing, claim/recovery ordering, claim-token + live-lease fencing on every worker mutation, `30 * attempts` retry backoff, terminal `FAILED`/`CANCELLED` transitions, and `submit_visitor` server-side `visitor` actor with deterministic retry keys (`base:rN`).
- `PriceStore` gained connection-taking internals (`_save_inside`, `_create_backfill`, `_backfill`, `_commit_day`, `_record_failure`) so `complete`/`fail` compose price persistence, backfill checkpoint and job transition in one transaction — fetch happens outside, matching the Java "no network inside transactions" rule.
- `infrastructure/tests/test_refresh_jobs.py` (16 tests) ports `RefreshJobServiceTest` on real PostgreSQL 18.6 scratch DBs: 4-thread dedup'd submissions retaining aliases after completion, single-winner competing claims across pooled connections, expired-claim write rejection + fresh-token recovery with `LEASE_EXPIRED` diagnostic, retry exhaustion to `FAILED` with 3 recorded import attempts, final-expired-attempt fail-stop, cancel fencing + actor audit + `CANCEL_NOOP`, atomic rollback under an injected `BEFORE UPDATE` trigger (no revision/attempt/checkpoint leak, job stays RUNNING), lease-expiry-mid-write rollback for complete and incomplete fetches, incomplete-day visible-but-retrying (287 valid coverage, checkpoint held), label/future-day/100-job bounds, visitor dedup onto a scheduler job, visitor `r2`/`r3` retries after terminal jobs then `RefreshAttemptsExhausted`, the separate 10-job visitor cap, and legacy raw-SQL rows readable via `find`/`events`/`recent` post-adoption.
- Full suite: `uv run pytest` 206 passed; `ruff check`/`ruff format --check`/`mypy`/`lint-imports` clean.

<a id="nem-073"></a>

## NEM-073 — Run isolated price fetches and schedules in the Python worker

- Repository: backend
- Milestone: Python backend rebuild
- Priority: High
- Status: Done
- Depends on: [NEM-072](#nem-072)
- References: [Rebuild plan](python-backend-rebuild.md), [decision 019](decisions/019-python-backend-rebuild.md); capability-specific Java/spec references in the plan.

### Outcome

Restore opt-in polling, fixed-market-time schedules and supervised fetch processes.

### Done when

- Port RefreshWorker, RefreshSchedule, PriceFetchProcess and FetchCommand behavior, including daily scheduling after 00:15 fixed UTC+10 and independent configuration flags.
- Preserve 240-second deadline and HTTP/retry classification; bound child input/output, network bytes/time and logging; cap concurrency across processes through the database.
- Test restart/lease recovery, duplicate schedules, terminal 4xx versus 429/transient errors, excessive Retry-After, timeout, child crash/orphan and parent shutdown; prove child termination and cleanup.
- Record measured Python fetch resource bounds and safe credential delivery without logs or tracked fixtures containing secrets.

### Completion evidence

- `worker/src/nemlab_worker/refresh.py` ports the whole `au.nemlab.worker.refresh` package: `FetchOutcome` (exactly-one-of contract, `[A-Z][A-Z0-9_]{0,79}` failure codes, slot prices as plain decimal text), `run_fetch_command` (the `--fetch-price` child mode — 240 s self-watchdog `os._exit(124)`, OE failure classification `!HTTP_4xx || HTTP_429) && !RETRY_AFTER_EXCEEDS_BUDGET`, exit codes 0/2/3), `PriceFetchProcess` (one child at a time, cleared env carrying only `OPEN_ELECTRICITY_API_KEY`, inherited console, 256 KB output cap → `INVALID_CHILD_RESULT`, deadline → `FETCH_DEADLINE_EXCEEDED`, crash/malformed → `FETCH_PROCESS_FAILED`, forcible terminate with 5 s `TerminationFailure` bound), `RefreshSchedule` (fixed UTC+10 `-15 min`/`-1 day` math, `daily-price-v1:` keys, restart-safe dedup) and `RefreshWorker` (fixed-delay poll, TerminationFailure stops polling, `WORKER_STOPPED` claim release).
- `main.py` dispatches `--fetch-price` before settings load like `WorkerApplication.main`; `__main__.py` adds `python -m nemlab_worker`; `settings.py` adds `OPEN_ELECTRICITY_API_KEY` (outside the `NEMLAB_` prefix) and enforces, only when enabled: 1000–60000 ms poll bound, non-blank newline-free key, valid `worker_regions`.
- Concurrency across processes stays capped by the database claim (one global `RUNNING`); no network work inside transactions — the child fetch happens between `claim()` and `complete()`/`fail()`.
- `worker/tests/test_refresh.py` (17 tests) ports `RefreshWorkerTest` + `PriceFetchProcessTest` on real PostgreSQL and real child processes via `fetch_fixture.py` (which aborts if `NEMLAB_DB_PASSWORD` leaks): round-trip 288 slots + temp-file cleanup, stalled child killed before `FETCH_DEADLINE_EXCEEDED`, shutdown kills the active child and leaves the job `QUEUED` with zero COMPLETE attempts, crash/malformed/oversized outputs → safe codes, `HTTP_401` terminal after one attempt, expired-claim recovery with a fresh token, fixed-NEM-time schedule dedup across "restarts", a packaged `python -m nemlab_worker` end-to-end run reaching `FAILED/INVALID_SOURCE_DATA_OR_CONFIGURATION` with cleared env, and settings ValidationErrors before polling.
- Credential delivery: child env is wiped except `OPEN_ELECTRICITY_API_KEY`; the key never reaches logs, the outcome file, or the database. Fetch resource bounds: 240 s deadline + watchdog, 256 KB result cap, single child per worker — measured fetch completes in <1 s for fixture loads; real OE fetch is bounded by the httpx timeouts (10 s connect/30 s read) inside the deadline.
- Full suite: `uv run pytest` 223 passed; `ruff check`/`ruff format --check`/`mypy`/`lint-imports` clean. Shared scratch-DB helpers moved to `infrastructure/tests/db_fixture.py` (uniquely named to avoid cross-package `conftest` shadowing).

<a id="nem-074"></a>

## NEM-074 — Restore public price reads and protected operator HTTP

- Repository: backend
- Milestone: Python backend rebuild
- Priority: High
- Status: Done
- Depends on: [NEM-071](#nem-071), [NEM-072](#nem-072), [NEM-067](#nem-067)
- References: [Rebuild plan](python-backend-rebuild.md), [decision 019](decisions/019-python-backend-rebuild.md); capability-specific Java/spec references in the plan.

### Outcome

Serve the existing price and operator routes through FastAPI with compatible responses.

### Done when

- Port all PriceReadController/AdminRefreshController routes, filters, limits, errors and bearer security using baseline HTTP cases and canonical OpenAPI.
- Keep opt-in flags independent, constant-time token comparison, server-derived audit identity, safe error envelopes and existing disabled/unauthorised semantics.
- Validate actual HTTP status/body/headers against frozen fixtures and schema, including coverage gaps, malformed values, pagination and cancellation/audit behavior.
- Keep api/contracts and generated TypeScript compatible; no automatic FastAPI schema/error changes.

### Completion evidence

Done — port of `PriceReadController`/`AdminRefreshController` and their error
advices, security filter chain, database smoke check and request logging onto
FastAPI/Starlette (`api/src/nemlab_api/`). `prices.py` serves
`GET /api/v1/prices/{region}/coverage` and `/{day}` only when
`NEMLAB_DATA_ENABLED`; `admin.py` serves the five refresh routes under
`OperatorBearer` middleware (SHA-256 + `hmac.compare_digest`, actor
`operator:<name>` server-derived, `X-Actor` ignored) only when
`NEMLAB_ADMIN_ENABLED`. Responses are hand-built dicts in the Java record
field order — decimal-string prices, `Z` instants, `Cache-Control: no-store`,
`Location` on 202, `Retry-After: 30` on 429, `WWW-Authenticate: Bearer` with
`application/json;charset=ISO-8859-1` `{"code":"UNAUTHORISED"}` on 401, and
Spring's security-header set (X-Content-Type-Options/X-Frame-Options/
X-XSS-Protection plus the no-cache trio only when the endpoint set no
`Cache-Control`). Framework-level misses (unmatched paths, wrong methods,
disabled features) return a bare 404 like the denyAll chain.

Verified against real PostgreSQL 18.6 scratch databases via `TestClient`
(`api/tests/`): `test_price_http.py` ports `PriceReadHttpTest` (mixed
coverage, exact 288-slot decimal-string series with `+10:00`→UTC instants,
404/400 matrices, safe 503), `test_admin_http.py` ports `AdminHttpTest`
(401 matrix, idempotent submit + `operator:alice` audit, spoofed `X-Actor`
ignored, 409 conflict, cancel/revoke fencing, `not-a-uuid`→400, queue-full
429 + `Retry-After: 30`, safe 503, fail-closed config validation,
credentials-free disabled shell). `test_contract_captures.py` writes 25
live captures in Java `ContractCapture` format to `api/build/contract-responses/`;
`node api/contracts/verify.mjs` validates every one against the frozen
schemas/headers and stops only at the not-yet-implemented simulation
operations (NEM-076/077). Live `uvicorn` run against the compose database
served real Java-era refresh jobs in the contract `JobView` shape. Full
suite `uv run pytest` 240 passed; ruff/format/mypy/import-linter clean.
Committed as the NEM-074 checkpoint; SHA recorded in the journal.

<a id="nem-075"></a>

## NEM-075 — Port immutable simulation inputs, jobs and saved results

- Repository: backend
- Milestone: Python backend rebuild
- Priority: High
- Status: Done
- Depends on: [NEM-068](#nem-068), [NEM-069](#nem-069), [NEM-070](#nem-070)
- References: [Rebuild plan](python-backend-rebuild.md), [decision 019](decisions/019-python-backend-rebuild.md); capability-specific Java/spec references in the plan.

### Outcome

Persist reproducible scenarios and fenced simulation lifecycle with old-result compatibility.

### Done when

- Verify immutable JSON/Decimal mapping and atomic completion through the selected SQLAlchemy persistence boundary.
- Port ScenarioPreparation and SimulationJobs canonical identity, revision capture, deduplication, queue caps/leases/retries and atomic immutable results.
- New runs use Python solver/execution metadata; Java two-/three-strategy results retain stored provenance and UUIDs without recomputation.
- Test source correction races, submission races, stale tokens, retry recovery, terminal deduplication and transaction rollback on real PostgreSQL.
- Prove old JSON payload readers tolerate supported historical shapes; legacy queued execution is drained/blocked at cutover rather than silently converted.

### Completion evidence

Done 2026-10-01. `infrastructure/src/nemlab_infrastructure/simulations.py` ports `ScenarioPreparation` + `SimulationJobs` onto SQLAlchemy Core over the V3 `simulation_*` tables: canonical request identity (SHA-256 over normalised parameters + captured immutable price revision), `Versions` carrying the truthful Python solver string (`HiGHS 1.12.0 via SciPy 1.18.1 linprog/highs-ds`) + `ordered-comparison-v1` profile, Jackson-compatible JSON codecs (compact `_encode`, `Decimal` parse hooks), dedup by `scenario_key`, `MAX_PENDING_JOBS=100` cap, advisory queue lock, single-runner claims with expired-lease recovery, `30 * attempts` backoff, claim-token + live-lease fencing (`StaleClaim`), atomic `complete` (validate → insert result → finish), `SOLVER_*` terminal codes on non-optimal outcomes, and `UnsupportedVersion` on stored-version mismatch before publish. `SimulationComparison` results persist verbatim; Java-era rows with old solver metadata read back without recomputation (legacy `QUEUED` rows surface as unsupported rather than silently converting). `hindsight.py` dispatch loop now mirrors Java's all-double arithmetic (numpy scalars no longer leak into domain objects/JSON).

`infrastructure/tests/test_simulations.py` (18 tests) ports `SimulationJobsTest` + `ScenarioPreparationTest` on real PostgreSQL 18.6: 4-thread global dedup, competing-claim single winner, equivalent-request identity (normalised efficiency legs, `2.000`/`-0.00` inputs), corrections minting new keys while captured inputs stay immutable, unavailable/incomplete days never enqueueing, validation before DB access, every result-affecting parameter + execution identity in the key, result publication + trigger-forced rollback, lease expiry recovery, queue cap, unsupported-version reads, and `RUNNING` refresh jobs not blocking claims. `uv run pytest` 258 passed; ruff/format/mypy/lint-imports clean. Committed as `692df46`.

<a id="nem-076"></a>

## NEM-076 — Execute and validate simulations in bounded Python children

- Repository: backend
- Milestone: Python backend rebuild
- Priority: High
- Status: Done
- Depends on: [NEM-075](#nem-075)
- References: [Rebuild plan](python-backend-rebuild.md), [decision 019](decisions/019-python-backend-rebuild.md); capability-specific Java/spec references in the plan.

### Outcome

Supervise independent compute and publish only independently validated outcomes.

### Done when

- Port SimulationWorker/Process/Command orchestration with independent refresh/simulation concurrency, bounded file exchange and cleared credential-free child environments.
- Enforce initial 15-second deadline, five-second termination allowance, orphan/shutdown cleanup and native thread limits; measure native RSS and document enforceable Linux/container resource bounds.
- Parent independently checks fixed and threshold policy identity, physical invariants, all accounting, solver bound/gap and supported versions before atomic publication.
- Test hangs, crash, nonzero exit, malformed/oversized/nonfinite output, invalid dispatch/certificates, unsupported versions and retry classification through real subprocesses.

### Completion evidence

Done 2026-10-01. `worker/src/nemlab_worker/simulation.py` ports the `au.nemlab.worker.simulation` package: `run_simulation_command` (`--simulate INPUT OUTPUT` child mode — DB-free, 15 s self-watchdog `os._exit(124)`, 512 KB input cap, exit 0/2/3, 4 GiB `RLIMIT_AS` self-bound), `SimulationProcess` (one child at a time, fully cleared env, discarded stdio, parent deadline → `SIMULATION_DEADLINE_EXCEEDED` retryable, nonzero exit → `SIMULATION_PROCESS_FAILED` retryable, >1 MB/invalid/mismatched-key output → `INVALID_CHILD_RESULT` terminal, `UnsupportedVersion` before launch → `UNSUPPORTED_SIMULATION_VERSION` terminal, parent-side `validate()` before publish, forcible kill bounded by 5 s → `TerminationFailure`), `SimulationWorker` (fixed-delay poll, `StaleClaim` results discarded, `WORKER_STOPPED` claim release on shutdown). `main.py`/`__main__.py` dispatch the child mode before settings; `WorkerSettings` enforces the 1000–60000 ms simulation poll bound; simulation polling needs no OE credential and shares the bounded engine with refresh when both are enabled. `simulations.py` gained the `Input`/`Output` file codecs (Jackson-shaped `key/request/prices/versions` + `key/comparison`).

Measured child footprint on a real run: ~110 MiB RSS, ~1.9 GiB peak VmSize, ~0.6 s wall — the 4 GiB `RLIMIT_AS` bounds runaway allocation without clipping normal scipy imports (documented bound; cgroup memory limits remain the operator-level enforcement, same as the Java deployment).

`worker/tests/test_simulation.py` (15 tests) + `simulation_fixture.py` on real PostgreSQL 18.6 and real children: OPTIMAL result through the packaged `python -m nemlab_worker` child with empty env, parent deadline kill, shutdown kill + `WORKER_STOPPED` recovery, malformed/oversized/crash/tampered-key classification, orphan watchdog bound (<23 s), unsupported stored version never launching, restart recovering an expired claim to `SUCCEEDED` (attempts=2), bounded retry exhaustion to `FAILED`, independent opt-in settings, and a packaged worker process claiming/completing a real queued job end-to-end. `uv run pytest` 273 passed; ruff/format/mypy/lint-imports clean. Committed as `5e642b0`.

<a id="nem-077"></a>

## NEM-077 — Restore simulation HTTP and visitor-triggered refresh

- Repository: backend
- Milestone: Python backend rebuild
- Priority: High
- Status: Done
- Depends on: [NEM-073](#nem-073), [NEM-074](#nem-074), [NEM-076](#nem-076)
- References: [Rebuild plan](python-backend-rebuild.md), [decision 019](decisions/019-python-backend-rebuild.md); capability-specific Java/spec references in the plan.

### Outcome

Complete compatible public submission/status/result and missing-price refresh behavior.

### Done when

- Port strict SimulationJson behavior: 16384-byte bound, JSON media type, duplicate/unknown fields, trailing documents, decimal strings, integer-not-boolean windows and safe validation reasons.
- Preserve 202/200 duplicate semantics, Location/Retry-After/no-store headers, pending/failed result conflicts, opaque IDs, optional thresholds and safe failure allowlists.
- Preserve PRICE_REFRESH_PENDING/PRICE_REFRESH_FAILED/VISITOR_REFRESH_LIMIT and unchanged-scenario resubmission without exposing queue internals.
- Validate real HTTP responses against canonical schema plus baseline success/error/disabled cases; old saved results and three-strategy new runs work end to end.

### Completion evidence

Done — `api/src/nemlab_api/simulations.py` ports `SimulationController`, `SimulationJson` and `SimulationErrors` to FastAPI. Strict parse boundary: `application/json` only (415), 16384-byte body cap (413), duplicate-field and trailing-token rejection via `object_pairs_hook`, unknown-field rejection, decimal strings preserved via `Decimal`, integer-not-boolean windows, strict `YYYY-MM-DD` days. Submit dedupes on scenario key (202 pending + `Retry-After: 2`, 200 terminal dedup, `Location`, `Cache-Control: no-store` everywhere). Coverage `Invalid` (`PRICE_DAY_UNAVAILABLE`/`PRICE_DAY_INCOMPLETE`) triggers `submit_visitor` → 409 `PRICE_REFRESH_PENDING` + `Retry-After: 30`; `RefreshAttemptsExhausted` → 409 `PRICE_REFRESH_FAILED`; `VisitorLimited` → 429 `VISITOR_REFRESH_LIMIT` + `Retry-After: 60`; sim `QueueFull` → 429 `QUEUE_FULL` + `Retry-After: 5`. Status/result project only public fields — diagnostic codes filtered through a whitelist; claim tokens/leases never leave. Shared handlers in `errors.py` branch on `/api/v1/simulations` paths for `SQLAlchemyError` (503 `STORAGE_UNAVAILABLE`) and request errors without disturbing price/admin envelopes. Router mounts only under `NEMLAB_SIMULATION_API_ENABLED`; startup smoke adds `simulation_job`.

Verified: `api/tests/test_simulation_http.py` (12 tests) ports `SimulationHttpTest` on real PostgreSQL — submit/poll/complete/reopen, decimal-exact price echo, threshold round-trip, strict-parse matrix, visitor refresh dedup/retry/exhaustion/10-cap, ineligible-day rejection without refresh, failure-code projection, queue saturation with working dedup, and storage-failure 503s across all three ops. `test_contract_captures.py` now writes sim captures; `api/contracts/verify.mjs` is fully green: 61 HTTP responses, all 10 operations, every error code. `uv run pytest` 285 passed; ruff/format/mypy/lint-imports clean. Committed as `9cb9223`.

<a id="nem-078"></a>

## NEM-078 — Make Python the active local tooling and CI path

- Repository: backend
- Milestone: Python backend rebuild
- Priority: High
- Status: Done
- Depends on: [NEM-073](#nem-073), [NEM-077](#nem-077)
- References: [Rebuild plan](python-backend-rebuild.md), [decision 019](decisions/019-python-backend-rebuild.md); capability-specific Java/spec references in the plan.

### Outcome

Replace active Java commands with reproducible Python checks and clear operational documentation.

### Done when

- Build Docker packaging with independently runnable API and worker targets/commands; verify native HiGHS dependencies, non-root execution, shutdown and the same locked checks in containers. Keep production cloud/provider selection under NEM-020.
- Update root README, running-locally, module READMEs, environment example, smoke scripts and backend workflow to locked Python install/lint/types/unit/integration/contract/process checks.
- Keep active Compose data/volume continuity, documented flag mappings, safe logs and independent API/worker startup; update Java-only configuration names explicitly.
- Run full local checks from a clean source copy without Java for the active path; verify reference Java remains optional and docs explain both paths.
- Keep NEM-038 hosted CI outstanding until actual remote run evidence exists; do not infer hosted success from workflow syntax/local checks.

### Completion evidence

Done — `Dockerfile` builds three non-root targets from the locked uv workspace on `python:3.13.14-slim`: `api` (`nemlab-api`), `worker` (`nemlab-worker`) and `migrate` (`python -m nemlab_infrastructure.migrate`, default `check`). SciPy/HiGHS run as binary wheels — no system solver libraries. `compose.yaml` keeps the `postgres` service and `nemlab-postgres` volume untouched and adds optional `api`/`worker` services under the `apps` profile (in-network `jdbc:postgresql://postgres:5432/nemlab`, `.env` passthrough for flags/credentials, api healthcheck on `/actuator/health`). `scripts/smoke_apps.py` replaces the jar smoke — starts `nemlab-api`/`nemlab-worker` flags-off, checks actuator health + worker liveness, SIGTERM-stops its own children. `.github/workflows/backend.yml` is the active workflow: pinned checkout/setup-node (same SHAs as the Java-era workflow), `uv==0.11.29` via pip, `uv sync --locked`, ruff/format/mypy/lint-imports, pytest against a postgres:18.6 service container, `verify.mjs`, packaged smoke and docker build+smoke per target. Module READMEs (`api/README.md`, `worker/README.md`), root README and running-locally rewritten Python-first; Java usage documented as reference. NEM-038 remains outstanding — no remote run evidence yet.

Verified: all three images build; container API serves `/actuator/health` and contract-shaped errors as uid 999 non-root; container worker claimed and committed a real refresh job against the Java-managed compose DB and exited cleanly on SIGTERM; containerised `migrate check` correctly reported the compose DB as java-managed V1-V3. `docker compose --profile apps up` starts postgres+api+worker independently. Clean `git clone` copy: `uv sync --locked`, ruff/format/mypy/lint-imports, full pytest (285) and `verify.mjs` (61 captures) all pass with no Java tooling. Committed as `5c9c94e`.

<a id="nem-079"></a>

## NEM-079 — Verify the existing frontend against the Python backend

- Repository: both
- Milestone: Python backend rebuild
- Priority: High
- Status: Done
- Depends on: [NEM-078](#nem-078)
- References: [Rebuild plan](python-backend-rebuild.md), [decision 019](decisions/019-python-backend-rebuild.md); capability-specific Java/spec references in the plan.

### Outcome

Adapt only runtime integration plumbing and prove existing visitor behavior against Python.

### Done when

- Read frontend AGENTS; adapt scripts/test-live.py from Gradle/JAR launch to Python and preserve api/contracts provenance/sync paths.
- Run frontend npm run check and npm run test:live against real Python API/worker/PostgreSQL, including default three strategies, missing-price refresh and old two-strategy saved links.
- Validate prices, form errors, polling, failures, immutable reopen/share and displayed accounting agreement; avoid unrelated UI redesign.
- Record exact backend/frontend revisions or uncommitted files, commands/results and any contract changes; no unexplained generated-type drift.

### Completion evidence

Done — `nemlab-ui/scripts/test-live.py` now launches the Python backend (`uv sync --all-packages --locked`, `python -m nemlab_infrastructure.migrate migrate`, `uv run nemlab-api` / `uv run nemlab-worker`) on a disposable PostgreSQL; contract provenance (`scripts/contract.mjs`, `contracts/provenance.json` sha256 pinning) unchanged and verified backend-compared at v1.3.0. `npm run check` fully green — contract check, prettier, tsc+vite build, all 102 Playwright tests (after `npx playwright install chromium`, an environment prerequisite). `npm run test:live`: all 6 live tests pass against the real Python API/worker/PostgreSQL — real simulation submit → worker-produced stored result with all three strategies (fixed/hindsight/threshold) and immutable saved-link reopen; incomplete day → visitor fetch → three permanent HTTP_401 attempts → terminal "could not be fetched" plus not-found recovery; complete/incomplete/absent price days through the real proxy with exact decimal strings and missing-gap states. No contract changes; no generated-type drift. Revisions: backend `af7c784` (HEAD at verification), frontend `8a39d18` (harness port).

<a id="nem-080"></a>

## NEM-080 — Rehearse database cutover and close the Python parity gate

- Repository: both
- Milestone: Python backend rebuild
- Priority: High
- Status: Done
- Depends on: [NEM-065](#nem-065), [NEM-069](#nem-069), [NEM-070](#nem-070), [NEM-078](#nem-078), [NEM-079](#nem-079)
- References: [Rebuild plan](python-backend-rebuild.md), [decision 019](decisions/019-python-backend-rebuild.md), [parity gate](evidence/python-rebuild/parity.md), [cutover rehearsal](evidence/python-rebuild/cutover-rehearsal.md); capability-specific Java/spec references in the plan.

### Outcome

Demonstrate complete local parity, safe transition and recovery before resuming M5.

### Done when

- Complete every parity-matrix row with code/test/evidence links; explain intentional solver metadata/degenerate-optimum differences and resolve all material gaps.
- Rehearse backup/restore, empty setup and populated Java-clone adoption; drain legacy jobs, stop Java schedulers/workers and verify Python reads historical prices/results and executes new work.
- Exercise rollback on an isolated clone including Python-version jobs and post-switch writes; document recovery without automatic destructive restore.
- Run final combined contract/domain/PostgreSQL/process/browser gates once against final changes; record numerical/performance/resource limits and pending hosted/deployment gates honestly.
- Update architecture/decisions/runbooks as implemented only on evidence, mark rebuild milestone complete, retain M3/NEM-038 and launch gates, and make NEM-054 next.

### Completion evidence

2026-10-02 — all "Done when" criteria met; full record in
[parity.md](evidence/python-rebuild/parity.md) and
[cutover-rehearsal.md](evidence/python-rebuild/cutover-rehearsal.md):

- **Parity matrix**: all 12 rows closed with Python module, test and commit
  links. Intentional differences recorded: solver provenance strings
  (`ojAlgo 57.3.0` preserved on old rows, HiGHS/SciPy on new) and the
  ojAlgo `DISTINCT` vs HiGHS `OPTIMAL` degenerate-optimum status (Python
  publishes on success + independent validation, not native status names).
- **Rehearsal on isolated clones** (live `nemlab` DB untouched): populated
  Java DB (10 revisions/days/refresh jobs, 13 sim jobs+results, queues
  drained) dumped, restored, adopted (`java-managed` → `alembic-managed`,
  `flyway_schema_history` preserved). Empty setup rehearsed on a fresh DB.
  Python API read Java-era prices and results verbatim; Python worker
  executed a new simulation to `SUCCEEDED`. The Java API booted on the
  adopted clone and read the Python-written result — both-direction read
  compatibility. Rollback = restore pre-cutover dump to a fresh DB →
  `java-managed`, Java resumes; forward dump/restore preserves adoption +
  post-switch writes. No automatic destructive restore exists.
- **Final combined gates** (once, final tree): `uv sync --locked`, ruff
  check/format, mypy (45 files), lint-imports, `pytest` 285 passed,
  `verify.mjs` 61 captures/10 operations, frontend `npm run check` (102
  Playwright) and `npm run test:live` (6/6 real stack) — all pass.
- **Limits recorded**: solver budget/tolerances identical; sim child ~110 MiB
  RSS / ~1.9 GiB virtual / ~0.6 s, 4 GiB address-space bound (not RSS);
  queue caps/backoffs unchanged. Honest pending gates: NEM-038 hosted CI
  (never run), NEM-020 deployment.
- Rebuild milestone marked Complete in [roadmap](roadmap.md); NEM-054 is
  next; M3/NEM-038 and launch gates retained.

Committed as `b4bbefe` — rehearsal/parity evidence docs, architecture,
roadmap, backlog, journal, plus two lint/typing repairs (`pyproject.toml`
`scripts/**` ignores; `FastAPI` typing on `register_simulation_errors`).


<a id="nem-081"></a>

## NEM-081 — Research energy-sector roles and refine the Python stack

- Repository: backend
- Milestone: Python backend rebuild
- Priority: High
- Status: Done
- Depends on: None
- References: [Research findings](evidence/python-rebuild/energy-python-stack-research.md), [decision 019](decisions/019-python-backend-rebuild.md), [rebuild plan](python-backend-rebuild.md).

### Outcome

Ground stack selection in relevant Australian, US, EU and UK energy-role evidence and NEMLab's scope.

### Done when

- Record named employers, roles, locations, stated technologies, source links and evidence limitations; separate employer usage from industry-wide popularity claims.
- Compare utility/customer platforms with trading, battery optimisation and energy-data work, avoiding duplicate-employer counting.
- Select the stack under delegated authority and reconcile affected plan, task, architecture and decision records.

### Completion evidence

2026-10-01: Reviewed employer/ATS evidence from Kraken, Powerline, Scale Microgrid Solutions, Joulea, Form Energy, trawa and Wattstor, plus explicitly historical Habitat Energy evidence. Recorded direct versus indexed/removed-page limitations. Retained FastAPI/PostgreSQL and added SQLAlchemy 2 Core over Psycopg 3; retained the PostgreSQL queue and SciPy/HiGHS parity design. NEM-067/070/071/072/075/078 now specify persistence/container implications. Markdown references and git diff whitespace checked; no runtime implementation or tests were performed. Committed as `5ff5106`.


<a id="gridreplay-discovery-tasks"></a>

## GridReplay discovery tasks

Accepted by the user on 2026-10-08 following live catalogue review. Existing detector v1 and immutable saved replays remain supported. Release A is useful independently of Release B; empirical v2 parameters are frozen in NEM-087. NEM-082 is an existing separate coverage task, not a reused ID.

<a id="nem-083"></a>

## NEM-083 — Correct event duration and time-range presentation

- Repository: both
- Milestone: Post-M5 GridReplay discovery refinement
- Priority: High
- Status: Done
- Depends on: None (existing GridReplay implementation)
- References: [Discovery and detector v2 plan](features/gridreplay-discovery.md)

### Outcome

Fix the 37-observation/185-minute demand-ramp projection without changing stored event identity.

### Done when

- Return elapsed endpoint duration for demand ramps and interval-count duration for price runs/spikes; update contract descriptions and all UI consumers.
- Cards distinguish observations from intervals, use readable hours/minutes, and show inclusive publication dates derived correctly from endExclusive.
- Tests cover three-hour ramps, one-interval spikes, multi-interval/cross-midnight runs and unchanged saved event IDs/snapshots. Record actual verification.

### Completion evidence

Done 2026-10-08. `durationMinutes` returns interval-count minutes for price run/spike/reversal/episode events and elapsed endpoint duration for demand/unusual ramps; replay bounds and `startAt`/`endAt` interval-end semantics unchanged, so stored event identity is preserved. UI shows "N observations · Xh Ym" for ramps and "N intervals · Xh Ym" otherwise, and derives the inclusive publication end (`endExclusive − 1 day`). Backend commit `5e01125`; UI duration/inclusive-date rendering in nemlab-ui `40ff212`. Verified by `test_events_http`/`test_events_discovery` duration cases plus live check: Sept-16/17 run reads "9h 5m" on card and "109 intervals · 9h 5m".

<a id="nem-084"></a>

## NEM-084 — Add publication-wide highlights and typed catalogue filters

- Repository: backend
- Milestone: Post-M5 GridReplay discovery refinement
- Priority: High
- Status: Done
- Depends on: [NEM-083](#nem-083)
- References: [Discovery and detector v2 plan](features/gridreplay-discovery.md)

### Outcome

Rank/filter all matching published events before pagination, preserving v1 detections and saved replays.

### Done when

- Implement highlights-v1 round-robin selection, eight-card maximum, type/day caps, deterministic exact-value ordering, duplicate suppression and multiple truthful reasons from the accepted discovery spec.
- Add highlights response with scope, eligible/excluded counts, per-type totals, ranks/reasons and selectionVersion; incomplete or unknown-coverage candidates are excluded honestly.
- Extend All events with compatible type-specific sorts/numeric filters and query-bound publication-pinned cursors; default unparameterized clients keep newest-first behavior.
- OpenAPI/HTTP/database fixtures verify full-publication ranking beyond page one, ties, filters/equalities, unsupported combinations, gaps, empty populations and republication. Measure query plan; do not fetch full replays to rank.

### Completion evidence

Done 2026-10-08 (backend commit `5e01125`). `core/highlights.py` implements the round-robin selector: per-reason exact-value ordering (no mixed-unit score), deterministic id-descending ties, ≤8 cards, ≤2/day, per-type caps, scan-down on cap-blocked candidates, duplicate suppression by logical identity, and `selectedBy`/`reasons` carrying truthful rank+population. `GET /api/v1/events/highlights` returns selectionVersion (`highlights-v1`/`highlights-v2` by publication suite), scope echo, eligible/excluded counts, typeTotals; incomplete or edge-incomplete events are excluded. All events gained `sort` (newest/oldest + per-type longest/deepest/highest/largest_rise), `minDurationMinutes`, `valueGte`, `valueLte`, `publication` pin; unsupported combinations return INVALID_REQUEST. v2 cursors (`v2.` prefix) bind publication + normalised-query fingerprint + sort tuple; legacy cursors still parse for the unfiltered shape. Ranking is SQL over stored columns — no replay fetch. Tests: `core/tests/test_highlights.py`, `api/tests/test_events_discovery.py`, infra `test_grid_events_v2.py`; OpenAPI evidence captured for all operations. Live: Sept-2023 NSW1 v2 publication selects spike + reversal first, day cap exercised (4th same-day event dropped).

<a id="nem-085"></a>

## NEM-085 — Deliver Highlights and All events in the demo-style UI

- Repository: frontend
- Milestone: Post-M5 GridReplay discovery refinement
- Priority: High
- Status: Done
- Depends on: [NEM-084](#nem-084)
- References: [Discovery and detector v2 plan](features/gridreplay-discovery.md)

### Outcome

Make the initial catalogue a small set of explainable investigations while keeping every original event available.

### Done when

- Default fresh visits to Highlights; preserve the flat demo grid, replay composition and shared appearance. Add All events with existing bounded pagination.
- Show clear values, duration, factual selection reasons and scoped counts; move routine version data to replay provenance while retaining material coverage warnings.
- Provide type-specific sorting and More filters; validate URL state, reset incompatible options and preserve open saved events outside the current selection.
- Browser/live checks cover modes, query state, Back/Forward, saved links, incomplete/empty/error states and all supported themes/widths. Computer-use review verifies September spike/longest-run discovery without scrolling through routine cards.

### Completion evidence

Done 2026-10-08 (nemlab-ui `67c1cd6`, `40ff212`, `9ecabd1`). `/gridreplay` defaults to a Highlights seg control ("Highlights"/"All events" via `view` param); the flat card grid, replay composition and theme are unchanged. Cards show value, readable duration, `#rank reason of N eligible` labels and scoped counts ("8 highlights selected from 114 eligible of 114 matching"); detector version/coverage stay as compact footer/provenance text. Sort select offers only the per-type supported sorts; More filters exposes min-duration/value bounds only for compatible types; invalid URL values are dropped on parse; `?event=` replay links work from either view. Verified by 12 GridReplay browser tests (desktop + mobile, incl. 320px) and live check against the real v2 NSW1 publication — Sept-4 $16,599.89 spike is card 1 and the Sept-16/17 9h5m run tops `type=run&sort=longest`.

<a id="nem-086"></a>

## NEM-086 — Add bounded immutable event preview charts

- Repository: both
- Milestone: Post-M5 GridReplay discovery refinement
- Priority: Normal
- Status: Done
- Depends on: [NEM-085](#nem-085)
- References: [Discovery and detector v2 plan](features/gridreplay-discovery.md)

### Outcome

Give cards a meaningful preview of event shape without downloading every full replay.

### Done when

- Define/cache versioned price or demand previews from immutable snapshots with bounded context, point count, payload and requests; unavailable data never becomes a fabricated curve.
- Reduction preserves extrema, event boundaries and gaps; card scale/window labels prevent misleading comparisons. Preview failure never blocks selection or changes highlight ranking.
- Wire lightweight preview rendering to both modes, with accessible textual equivalents and theme support. Measure page bytes/query count/mobile rendering and record budgets.
- Test sparse/missing/edge/extreme data, cache version isolation, context boundaries and no per-card full-replay fan-out; visually verify on desktop and mobile.

### Completion evidence

Done 2026-10-08 (backend `5e01125`, frontend `67c1cd6`). `GET /api/v1/events/{id}/preview` derives `preview-v1` min/max slot bands from the event's immutable replay snapshot: ≤48 slots, ±12 intervals context, gap flags, event ranges, `peakSlot` marker for reversals, `localScale: true`. Missing slots stay null/gap — no fabricated curve; preview failure renders an empty spark and never affects selection. Cards render an inline SVG band (one bounded request per visible card, ~3 KB typical payload, no replay fetch); aria-label describes the series. Backend preview tests cover bounds/ranges/markers; browser tests assert sparklines render on both desktop and mobile.

<a id="nem-087"></a>

## NEM-087 — Calibrate and freeze detector v2 definitions

- Repository: backend
- Milestone: Post-M5 GridReplay discovery refinement
- Priority: Normal
- Status: Done
- Depends on: None (existing GridReplay implementation)
- References: [Discovery and detector v2 plan](features/gridreplay-discovery.md), [decision 022](decisions/022-detector-v2-definitions.md)

### Outcome

Turn the accepted unusual-ramp, price-reversal and grouped-episode directions into evidence-backed versioned rules.

### Done when

- Evaluate the starting parameters in the discovery spec against hand-labelled fixtures and available stored NSW1 evidence; record counts, representative examples and false/redundant candidates without targeting an arbitrary event quota.
- Freeze demand baseline membership/completeness/quantile/floor, reversal look-ahead/equalities/deduplication, and episode gap/aggregate-gap/boundary semantics.
- Document wider historical coverage needed for unusual ramps; insufficient baseline must remain explicit and cannot be solved by treating missing days as zero. Additional imports stay bounded operator work.
- Freeze highlights-v2 type slots, overlap suppression and labels using concrete examples; define new-type compatibility, immutable evidence and calibration/version changes before production implementation.

### Completion evidence

Done 2026-10-08 (backend `5e01125`, decision `decisions/022-detector-v2-definitions.md`). Frozen constants live in `nemlab_core/detectors.py`: reversal look-ahead 72 intervals, peak/rise ≥ 300 AUD/MWh; episode gap ≤3 intervals at price <50, total gap ≤6 intervals, ≥2 members; ramp baseline 90 days, ≥60 complete days, ≥20 same-class samples, nearest-rank P90, 1,000 MW floor. Fixture calibration covered boundary/tie/gap cases in `core/tests/test_detectors_v2.py`. Live NSW1 Sept-2023 v2 publication: 5 reversals, 10 episodes, 0 unusual ramps with per-day `insufficient_baseline` recorded in coverage — the documented outcome given no Jun–Aug history is imported. highlights-v2 reason set/caps and constituent suppression fixed in `nemlab_core/highlights.py`. Residual: the $300 reversal threshold produced only 5 NSW1 events in September, so the permissive-threshold concern did not materialise for this publication; revisit if other regions/months show high counts.

<a id="nem-088"></a>

## NEM-088 — Detect and explain unusually large demand ramps

- Repository: both
- Milestone: Post-M5 GridReplay discovery refinement
- Priority: Normal
- Status: Done
- Depends on: [NEM-087](#nem-087), [NEM-085](#nem-085)
- References: [Discovery and detector v2 plan](features/gridreplay-discovery.md), [decision 022](decisions/022-detector-v2-definitions.md)

### Outcome

Surface ramps exceeding a documented comparable historical baseline while retaining daily v1 ramps.

### Done when

- Implement the frozen same-region preceding-history comparison with candidate-day exclusion, minimum sample counts, explicit quantile method and absolute floor.
- Persist baseline bounds/sample count/threshold/revisions; insufficient history returns an eligibility reason, not a normal or rare label.
- Integrate new type/version into publication, API, filters/cards/replay and highlights-v2 with underlying-ramp duplicate suppression; old links remain readable.
- Verify exact-quantile ties, missing days, weekday/weekend membership, no future leakage, revised references, insufficient history and real examples when coverage permits.

### Completion evidence

Done 2026-10-08 (backend `5e01125`, frontend `67c1cd6`). `unusual_demand_ramp` classifies each v1 ramp's rise against the same-weekday/weekend-class distribution of daily maximum ramps over the preceding 90 days (nearest-rank P90, ≥60 complete days, ≥20 class samples, 1,000 MW floor). Publication loads the extended baseline window; per-day classification is recorded in coverage (`unusual`, `ordinary`, or `insufficient_baseline` — never "normal"), and event `detail` persists baseline window, class, sample counts, quantile value, minimum rise and baseline revision pins; baseline changes re-version the event. Tested in `test_detectors_v2.py`/`test_grid_events_v2.py` incl. insufficient-history and re-versioning cases. Live: every Sept-2023 NSW1 day reports `insufficient_baseline` — importing ~90 days of prior demand history remains a separate bounded operator task.

<a id="nem-089"></a>

## NEM-089 — Detect and replay negative-to-high price reversals

- Repository: both
- Milestone: Post-M5 GridReplay discovery refinement
- Priority: Normal
- Status: Done
- Depends on: [NEM-087](#nem-087), [NEM-085](#nem-085)
- References: [Discovery and detector v2 plan](features/gridreplay-discovery.md), [decision 022](decisions/022-detector-v2-definitions.md)

### Outcome

Show a bounded transition from a negative-price run to a later high-price episode.

### Done when

- Implement the frozen threshold/look-ahead/gap and overlapping-candidate rules; include trough, peak, elapsed time and linked source events.
- Publish immutable compound evidence and support typed API/filter/card/replay rendering, with both phases visible and truthful observation-only copy.
- Add highlights-v2 integration and overlap suppression; preserve one-day BatteryLab handoff semantics and original event links.
- Tests cover exact thresholds and six-hour boundary, high-before-low, gaps, incomplete look-ahead, equal peaks, shared peaks, cross-midnight events and corrected-source versions.

### Completion evidence

Done 2026-10-08 (backend `5e01125`, frontend `67c1cd6`). `price_reversal` pairs a negative-price run with the highest price inside the next 72 intervals where peak ≥ 300 AUD/MWh (rise bound redundant given trough < 0 — retained as documentation); dedupe keeps the first-run/earliest candidate on shared peaks. `detail` persists trough, peak, rise, riseMinutes, run/peak instants, peakPosition and memberRuns (linked run ranges + ids). Highlights-v2 selects `largest_price_reversal`; replay shows a "Detected:" evidence line and the preview carries a `peakSlot` marker; the negative-run shading already shows both phases. Tests cover boundary, gap, equal-peak and cross-midnight cases. Live Sept-2023 NSW1: 5 reversals, led by the Sept-4 −11.40 → 16,599.89 rise.

<a id="nem-090"></a>

## NEM-090 — Group related negative-price episodes for exploration

- Repository: both
- Milestone: Post-M5 GridReplay discovery refinement
- Priority: Normal
- Status: Done
- Depends on: [NEM-087](#nem-087), [NEM-085](#nem-085)
- References: [Discovery and detector v2 plan](features/gridreplay-discovery.md), [decision 022](decisions/022-detector-v2-definitions.md)

### Outcome

Summarize related runs in a compound event without redefining consecutive negative prices or restoring day-grouped cards.

### Done when

- Implement frozen gap length/price and total-gap limits over complete continuous context, with deterministic membership and cross-midnight handling.
- Retain member event IDs and distinguish span, actual negative duration and intervening nonnegative duration; missing prices prevent joining.
- Support typed API/filter/card/replay with separately shaded member runs and access to originals; highlights-v2 suppresses constituent duplicates only in its selected view.
- Tests cover interval-boundary arithmetic, exact limits, chained gaps, missing observations, source edges, publication chunking, no eligible grouping and original-link reproducibility.

### Completion evidence

Done 2026-10-08 (backend `5e01125`, frontend `67c1cd6`). `negative_price_episode` joins complete v1 runs when the intervening gap is ≤3 intervals and all gap prices stay < 50 AUD/MWh, with total gap ≤6 intervals and ≥2 members; runs separated by missing prices or touching the source edge never join. `detail` persists memberCount, negativeMinutes, gapMinutes, spanMinutes and member ranges, and the member run events are linked. Individual runs stay in All events; highlights-v2 suppresses constituents only in the selected view. Episode replays show all member runs via the existing negative-price shading plus a member-count evidence line. Tests cover boundary/gap/missing/member cases. Live Sept-2023 NSW1: 10 episodes, widest 2023-09-15 00:50–04:20 at −59.79.

<a id="nem-091"></a>

## NEM-091 — Verify discovery releases and detector v2 journeys

- Repository: both
- Milestone: Post-M5 GridReplay discovery refinement
- Priority: Normal
- Status: Done
- Depends on: [NEM-083](#nem-083), [NEM-084](#nem-084), [NEM-085](#nem-085), [NEM-086](#nem-086), [NEM-087](#nem-087), [NEM-088](#nem-088), [NEM-089](#nem-089), [NEM-090](#nem-090)
- References: [Discovery and detector v2 plan](features/gridreplay-discovery.md)

### Outcome

Record separate Release A and Release B acceptance evidence and preserve the existing catalogue/replay behavior.

### Done when

- Checkpoint A after NEM-083–086: backend/contract/frontend/live checks pass, desktop/mobile theme screenshots match the accepted demo direction, and real September examples surface with correct scoped reasons. Release A need not wait for B.
- Checkpoint B after NEM-087–090: each new type passes labelled detector, storage/version, HTTP and UI/live checks; unavailable baseline/coverage remains honest and wider evidence is documented.
- Record stable saved links, whole-publication filtering/ranking, duplicate suppression, query/preview payload/render measurements and operator publication behavior.
- Only mark this task Done when both checkpoints pass. Record any remaining evidence/data gaps as explicit follow-ups; no hosted CI/public launch completion is implied.

### Completion evidence

Done 2026-10-08. Both checkpoints recorded in `journal/2026-10.md` ("GridReplay discovery releases A+B delivered").

- Backend: 462 pytest passed; ruff/format/mypy-strict (57 files)/import-linter clean; OpenAPI 2.0.0 verified — 114 HTTP responses across 23 operations.
- Frontend: `npm run check` — contract verified, prettier/tsc clean, vite build, 126 browser tests pass (desktop + mobile).
- Live: alembic `nemlab_v7_detector_v2` applied; NSW1 republished via admin API with `detectorSuite=v2` → publication `232be228`, 114 events (68 runs, 30 ramps, 1 spike, 5 reversals, 10 episodes, 0 unusual ramps — every day `insufficient_baseline`, honest since no Jun–Aug history is imported). UI live check on the built bundle: Highlights default shows the Sept-4 $16,599.89 spike first with `#1 highest price of 1`, previews render per card, replay opens and charts render; All events + `sort=longest` surfaces the 9h5m run top. Old event ids and replays (incl. superseded versions) still return 200; `?event=` links unchanged.
- Follow-ups recorded: (a) unusual ramps need ~90 days of prior demand history imported per region before any can qualify; (b) run the v2 publication for QLD1/SA1/TAS1/VIC1 if cross-region v2 catalogues are wanted; (c) revisit the 300 AUD/MWh reversal floor if other regions/months show high counts.
