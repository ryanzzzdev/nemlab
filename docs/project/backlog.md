# NEMLab backlog

Updated: 2026-09-20

Task sections own status. The index is navigation, not a second status tracker. Next: NEM-037 shared-foundation exit review, then refine NEM-016 into focused simulation API tasks. NEM-036 chart interaction proof is verified. NEM-035 typed price reads are verified. NEM-034 public navigation and shell is verified. NEM-033 repository/tooling is verified. NEM-032 delivers the formal OpenAPI contract and generated client inputs. NEM-031 stored-price read endpoints are implemented. NEM-028/NEM-029/NEM-030 complete the price-refresh jobs and operator-controls package. The price-first NEM-012 slice is implemented; M3 remains in progress. Earlier illustrative IDs did not create tasks.

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

Verification: `JAVA_HOME=/usr/lib/jvm/java-25-openjdk-amd64 ./gradlew clean build --no-daemon --offline` passed on 2026-09-17: **33 tests, zero failures/errors/skips**, including 200 seeded scenarios inside one invariant test and both validated NSW1 price days. [Tests](../../core/src/test/java/au/nemlab/batterylab/BatteryEngineTest.java) cover negative/zero/losing prices, efficiency/fees, connection limits, partial allocation, terminal inventory, price independence, missing/duplicate/wrong-region data, DST-independent market days, invalid windows, overflow and tampered dispatch. No solver or API is claimed. Changes are uncommitted; setup is in [README](../../README.md).

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

Price-first implementation complete through NEM-024–NEM-027. [Findings](evidence/data-foundation/findings.md) record 64 passing tests, real PostgreSQL migrations/revision/snapshot/checkpoint tests, bounded HTTP stub tests and packaged application smoke checks. [Operator instructions](../../infrastructure/README.md) cover explicit migration/import/resume/coverage/history. GridReplay adapters remain NEM-018; worker integration and scheduling remain NEM-013. No live OE request or hosted CI run was performed. Changes are uncommitted.

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

Refined 2026-09-20 during NEM-037. NEM-039 request preparation and NEM-040 durable execution/results are complete; NEM-041 HTTP integration is Ready. The user directed local implementation to continue while the separate M3 hosted CI gate remains open.

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

### Notes

A static mock-data demo of the catalogue/replay concept lives at [docs/demos/gridreplay/index.html](../demos/gridreplay/index.html) (2026-09-18) for discussion; illustrative only — detector definitions and scope remain unsettled per the feature spec and [BLK-005](blockers.md#blk-005).

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

Implemented opt-in worker configuration, lifecycle-managed polling, fixed UTC+10 daily submission, child-process fetch deadlines and shutdown/restart recovery. Full offline build: 88 passing tests, including real child-process and PostgreSQL worker tests plus executable-jar child launching without live OE calls. See [worker evidence](evidence/jobs/worker-findings.md) and [setup](../../worker/README.md). Committed as `dc170bf`.

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

Implemented opt-in bearer authentication, server-derived audit identity, refresh submission, status/recent jobs, paginated events and idempotent cancellation. Direct CLI ingestion is retired. Full build: 97 passing tests; see [HTTP/PostgreSQL evidence](evidence/jobs/admin-findings.md) and [operator guide](../../api/README.md). Committed as `8d7c4b1`.

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
- Status: Ready
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

Not yet reviewed as a complete milestone.
