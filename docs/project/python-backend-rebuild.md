# Python backend rebuild plan

Date: 2026-10-01  
Status: Accepted direction and stack under delegated selection authority; implementation and parity verification pending.  
Tracking: [NEM-065–NEM-080](backlog.md#python-rebuild-tasks). Decision: [019](decisions/019-python-backend-rebuild.md).

## Goal and scope boundary

Replace the Java backend with Python in the existing `nemlab` Git repository, retaining separate API and worker applications and the core/infrastructure dependency boundaries. Preserve Java as a runnable reference, the repository history, canonical docs, existing data and saved-result links. Finish one coordinated rebuild campaign with incremental verification gates; a single unreviewable change or uninterrupted session is not an acceptance requirement.

Baseline inspected: backend HEAD `e93142cc35aa8bdf1fc5722612a2c58a48aacbdc`. Record the actual backend and frontend revisions again before implementation. Existing user changes (`docs/project/todo.md` deleted and untracked `docs/project/zzz.md`) are outside this plan and must be preserved.

Port delivered M1–M4 backend functionality, including NEM-046 visitor refresh and NEM-049–NEM-050 price thresholds. NEM-052 makes thresholds a frontend default, while the backend still accepts old two-strategy requests/results. M5 GridReplay ingestion, detectors, catalogue/replay APIs and optional Admin UI are not implemented and are not rebuild scope. Keep their backlog for after parity. Hosted CI (NEM-038) and public launch (NEM-020) remain separate gates.

## Selected stack

Reassessed using [Australian, US, EU and UK energy-role research](evidence/python-rebuild/energy-python-stack-research.md) on 2026-10-01. FastAPI remains selected for the optimisation/data-platform focus; SQLAlchemy 2 Core is now the active persistence layer over Psycopg 3. Hiring evidence supports relevant usage, not an industry-wide popularity ranking.

| Layer | Selection | Reason / constraint |
| --- | --- | --- |
| Runtime | CPython 3.13; pin a supported patch at bootstrap | Conservative scientific-library wheel baseline; validate actual Linux/CI installation before locking |
| Packaging | uv workspace, four installable packages, one `uv.lock` | Mirrors existing modules, explicit app dependencies and reproducible installs |
| API | FastAPI, Uvicorn, Pydantic v2 / pydantic-settings | Typed HTTP boundary and configuration; adapters preserve the existing contract rather than accepting framework defaults |
| Domain | Dataclasses, enums, Decimal at exact input/storage boundaries; float64 for existing numerical model | Preserve current decimal strings/hashes and documented numerical tolerances |
| Database | PostgreSQL, SQLAlchemy 2 Core with Psycopg 3 driver; bounded Engine pool and explicit SQL | Keep locking, immutable revisions, triggers and transactional queue behavior inspectable |
| Migrations | Alembic with explicit SQL revisions and SQLAlchemy connection | One explicit migration command; no ORM rewrite or competing startup migrations |
| OE client | HTTPX synchronous client in isolated fetch child | Bounded streaming, timeouts, retry classification and secret handling |
| Optimisation | SciPy `linprog(method="highs-ds")` / bundled HiGHS | Ordered-window LP with independent validation and dual certificate; acceptance requires parity/performance evidence |
| Worker | Separate Python process, PostgreSQL polling/scheduling, supervised subprocesses | Retain durable queue, restart recovery and hard termination; no broker required |
| Quality | pytest, Hypothesis for invariants, Ruff, mypy, import-linter | Domain, real PostgreSQL, subprocess, contract and import-boundary checks |
| Packaging/delivery | Docker image with independent API/worker commands, Compose and CI | Verify native solver dependencies and independent process lifecycle; cloud provider remains a launch decision |
| End-to-end | Existing Node contract checks and frontend Playwright suites | Prove current consumers work against Python |

Use one SQLAlchemy Engine/pool per application process and explicit transaction contexts; no parallel psycopg_pool or domain ORM coupling. Preserve parameterised SQL/advisory locks and use Core expressions where clearer.

Pin exact stable dependencies and uv/Python versions during NEM-067 after wheel/license/compatibility checks. Do not treat documentation's latest/dev versions as tested pins. API handlers using synchronous database calls must run off the event loop; long fetch/compute work belongs exclusively to the worker. Start with one API process and one worker; PostgreSQL continues enforcing global per-job-type concurrency.

Primary documentation consulted for this selection: [FastAPI process deployment](https://fastapi.tiangolo.com/deployment/server-workers/), [uv workspaces](https://docs.astral.sh/uv/concepts/projects/workspaces/), [Psycopg transactions](https://www.psycopg.org/psycopg3/docs/basic/transactions.html), [Alembic cookbook](https://alembic.sqlalchemy.org/en/latest/cookbook.html), [SciPy HiGHS interface](https://docs.scipy.org/doc/scipy/reference/optimize.linprog-highs.html). These establish available mechanisms, not NEMLab performance or parity.

## Repository layout and history

Target layout (created during implementation):

```text
nemlab/
  .git/                         existing history, never reinitialised
  AGENTS.md, README.md
  docs/                         existing canonical docs, evidence, demos and chats
  api/
    pyproject.toml
    src/nemlab_api/
    tests/
    contracts/                  existing canonical contract stays at this path
  worker/                       pyproject.toml, src/nemlab_worker/, tests/
  core/                         pyproject.toml, src/nemlab_core/, tests/
  infrastructure/               pyproject.toml, src/nemlab_infrastructure/, tests/
  migrations/                   Alembic configuration/revisions, explicit SQL
  tests/parity/                 provenance-backed cross-runtime fixtures
  scripts/                      active Python checks, migration and smoke commands
  pyproject.toml, uv.lock, .python-version
  compose.yaml, .env.example, .github/workflows/
  reference/java/
    README.md                   baseline SHA, path map and reference commands
    build.gradle, settings.gradle, gradlew, gradlew.bat, gradle/
    core/, infrastructure/, api/, worker/
    scripts/, ci/               retained Java-only launch/check references
```

Move tracked Java sources/tests/resources, Gradle files/locks/wrapper and module Java READMEs to `reference/java/` with `git mv` during NEM-066. Leave `api/contracts/`, `docs/`, root AGENTS/README, Compose, configuration examples and active workflow locations in place. Move the old Java smoke script to the reference tree before replacing the active script. Preserve a reference copy of the Java workflow under `reference/java/ci/`; update the active workflow during NEM-078. Do not move `.git`, local secrets, build caches, virtual environments or database volumes. Inventory tracked paths first, including hidden files.

Prefer a move-only checkpoint separate from Python implementation when commits are authorised. Git records snapshots and detects renames; same-content moves make history easy to follow with `git log --follow`. No commits, tags, pushes or actual moves are part of this planning turn. At implementation time follow then-current commit authorisation; checkpoint diffs can remain uncommitted. Repair Java reference paths explicitly and verify the retained build and contract checks still run. Historical evidence stays historical; update active setup links and add a reference path map rather than rewriting old findings as Python evidence.

Retaining `api/contracts` avoids breaking `nemlab-ui/scripts/contract.mjs`, including its `git show <revision>:api/contracts/...` provenance check. `nemlab-ui/scripts/test-live.py` does hard-code Gradle/JAR launches and must be adapted under NEM-079. Read frontend AGENTS before changing it.

## Definition of parity and source map

Each implementation task must read both the relevant specification/decision and Java production code plus tests. Record a matrix linking requirement → Java class/test → Python module/test → evidence in `docs/project/evidence/python-rebuild/parity.md`. Documentation describes intent; Java describes current behavior. Neither automatically wins a conflict: record the discrepancy and resolve it explicitly, retaining externally consumed behavior unless an intentional correction is documented and tested.

All Java paths below are current paths; after NEM-066 prefix them with `reference/java/` except `api/contracts/`.

| Capability | Required references | Python acceptance |
| --- | --- | --- |
| Market time and requests | `features/battery-model-contract.md`, `features/simulation-request-contract.md`; core `PriceDay`, `SimulationRequest`, `Efficiency`, `ScheduleWindows` and request tests | 288 five-minute interval-end prices; fixed UTC+10 rather than Sydney DST; decimal syntax/bounds, canonicalisation, physical validation and error reasons agree |
| Fixed schedule and accounting | core `Battery`, `FixedSchedule`, `BatterySimulation`, `Accounting`, `DispatchValidator`; `BatteryEngineTest` | Same dispatch policy, efficiency/losses/costs and physical/terminal-energy invariants |
| Ordered hindsight | decision 007; core `OrderedHindsight`, `HindsightTest`, `HindsightBenchmark`, engine evidence | Same restricted ordered-window formulation, proven optimality rules and budget; no unrestricted optimisation |
| Threshold strategy | `features/price-threshold-strategy.md`; `PriceThreshold`, `Thresholds`, `SimulationComparison`, corresponding tests | Strict inequalities, equality hold, all-day operation, partial intervals and differing ending energy; optional old-result compatibility |
| OE import and storage | data-foundation specification, decision 008; `OePriceSource`, `PriceBatch`, `PriceStore`, `PriceBackfill`, import commands/tests | Bounded source validation, null vs missing vs zero, revisions/provenance, content hashes, coverage, resume and snapshots |
| Refresh queue and execution | decisions 009/010; `RefreshJobService`, refresh worker/process/schedule, queue and process tests | Claims, fencing, retries, cancellation, deduplication, caps, audits, schedule and fetch isolation |
| Public price/operator HTTP | `PriceReadController/Errors`, `AdminRefreshController/Errors`, security config, HTTP tests | Routes, filters/limits, headers, auth and safe errors match |
| Simulation persistence/execution | decisions 015/016; `ScenarioPreparation`, `SimulationJobs`, simulation worker/process/command and tests | Immutable input/result linkage, safe version handling, independent validation and fenced atomic completion |
| Simulation HTTP/visitor fetch | decision 017, NEM-046/050; `SimulationJson`, controller/errors, `SimulationHttpTest`, `api/contracts` | Exact lifecycle, strict JSON, old/new result shapes, visitor eligibility/caps/deduplication and refresh errors |
| Runtime and frontend | app configs/READMEs, `scripts/smoke_apps.py`, workflows, frontend live harness | Independent feature flags, credential-free disabled startup, health/logging, shutdown and existing browser journeys |

NEM-065 captures exhaustive endpoints, environment variables/defaults, commands, schema objects and test cases; this table is the work map rather than a claim that every case has already been captured.

## Numerical and solver migration

Preserve exact decimal values at request/price/canonical-hash boundaries. Explicitly reproduce Java trailing-zero stripping/plain-string formatting, signed zero behavior, exponent bounds, newline/field ordering and UTF-8 SHA-256. Python Decimal context must not silently round source values. Reject nonfinite JSON numbers and integer booleans. Float calculations retain the current model rather than switching all mathematics to Decimal.

Fixed and threshold policies must reproduce per-interval dispatch within existing tolerances. Preserve energy tolerance `1e-7` and accounting reconciliation `1e-6 + 1e-9 * max(abs(expected), abs(actual))`; retain the hindsight absolute optimality-gap ceiling of AUD 0.01. Do not loosen tolerances to make the port pass.

Port the actual primal LP and its independent dual upper-bound/certificate logic. SciPy minimises while the existing objective is margin maximisation: test sign conversion, dual marginal conventions, bounds, costs, zero coefficients and negative prices. A solver success flag alone is insufficient. Record solver/library/build metadata truthfully. Multiple optimal dispatches can differ: compare feasibility, objective, certified bound and gap rather than requiring identical tied dispatch arrays. Fixed/threshold output and unique-optimum cases still need interval comparisons.

Use a new execution-profile/solver identity for Python-generated results and keys, while preserving unchanged model/strategy versions only where justified. New runs must never claim ojAlgo provenance. Read old Java results without recomputation or relabelling. Prove synthetic exact cases, frozen sampled price days, property invariants, degenerate cases and bounded aborts. Keep the existing five-second/100,000-iteration cooperative limit and 15-second parent simulation deadline as initial acceptance targets; benchmark cold imports and native library startup within the parent deadline. If they cannot be met, record an explicit decision and blocker instead of silently increasing limits.

## Database transition and saved results

Keep the existing PostgreSQL schema and immutable stored data; rebuilding the language does not authorise dropping databases. Inspect all V1–V3 SQL, triggers, indexes, constraints, Flyway history and JSON payloads. Preserve explicit SQL semantics and transaction isolation/locking. Verify new database creation and upgrade of a populated Java database clone.

Alembic's baseline revision creates the equivalent V1–V3 schema on an empty database. For existing databases, a dedicated adoption command validates expected Flyway versions/checksums and actual schema, then stamps the baseline without replaying DDL. Unknown, partially migrated or drifted schemas must fail closed. Keep Flyway history for provenance. Normal Alembic upgrade follows adoption; never unconditionally stamp an arbitrary database. Run migrations once before either application starts, with deployment-level exclusivity. Additive schema changes require separate revisions and explicit rollback implications.

Clone-based rehearsal includes price corrections, import checkpoints/audits, queued/failed/completed jobs, two- and three-strategy saved results and UUID links. Preserve old successful results byte-for-byte in storage and equivalent JSON responses. Stop Java submissions/scheduling and drain queued/running work before local cutover; do not run mixed-version workers against the same queue. If legacy pending jobs remain, fail the cutover check and finish/cancel them through the Java controls, preserving audit history. Do not rerun old requests under new solver provenance. A restore rehearsal uses a dedicated clone and verified backup, never overwrite the user's database as a test.

## Durable execution and HTTP compatibility

Port PostgreSQL advisory locks, unique indexes, row locks and conditional claim-token writes, including atomic price/checkpoint/job transitions. Network and solver execution stay outside DB transactions. Keep refresh and simulation concurrency independently bounded. Preserve the current refresh cap 100, five-minute lease, three attempts and 30/60-second retry delays; simulation cap 100, 60-second lease, three attempts and 5/10-second retries. Capture remaining exact limits from code in NEM-065, including visitor eligibility, three day attempts and ten pending visitor jobs.

Fetch children retain a 240-second parent deadline. Simulation children receive bounded files and a cleared environment without OE/database secrets. Implement kill/reap of process groups, orphan watchdog/parent-loss behavior, shutdown cleanup and bounded output. JVM heap limits do not translate directly to Python/native RSS: measure SciPy/BLAS footprint, cap native thread counts, select and document Linux process/container resource bounds in NEM-076, and test enforcement. Never claim a virtual-memory limit is an RSS guarantee.

Keep `api/contracts/openapi.json` authoritative throughout parity. FastAPI's autogenerated schema and default 422 errors must not silently replace it. Preserve route paths, casing, decimal strings, omission/null behavior, UUIDs, status codes, Location/Retry-After/Cache-Control, content type, request-size limits and feature-disabled behavior. Strict raw-body JSON decoding must reject duplicate keys, trailing documents, unknown fields, numeric coercion and nonfinite values before domain validation. Public responses must not leak solver diagnostics, tokens or credentials. Preserve opt-in operator bearer authentication and server-derived audit identity; public routes remain independent. Record any necessary contract change explicitly and update both repositories together only when justified.

## Ordered execution campaign

1. **Freeze and scaffold (NEM-065–067):** capture baseline/oracles; preserve Java tree; bootstrap four Python packages and independent runnable entry points.
2. **Prove domain and schema (NEM-068–070):** requests/fixed/threshold, solver and migrations. Solver feasibility is an early stop gate before broad porting.
3. **Restore data and refresh (NEM-071–074):** OE/store/backfill, durable queue, isolated worker, price/operator HTTP.
4. **Restore simulation (NEM-075–077):** immutable jobs/results, isolated compute, HTTP lifecycle and visitor refresh.
5. **Integrate and switch (NEM-078–080):** Python checks/setup, frontend real-stack verification, clone migration and final parity/cutover review.

Tasks are ordered and dependency-linked for continuous execution. Promote dependent Backlog tasks to Ready as predecessors pass. Stop only the affected gate for a real discrepancy; record evidence and continue independent work where possible. Do not mark missing tests as passed to finish in one go.

## Verification and completion gates

- Freeze Java test/HTTP/numerical outputs with source revisions, inputs, commands and reproducible fixture generation. No unsanitised credentials or production dumps in Git.
- Port behavioral coverage, not merely Java test counts. Run unit/property checks, module boundary checks, real PostgreSQL integration and concurrent claim races.
- Test malformed requests, all feature flags, missing/incomplete/corrected prices, source 4xx/429/5xx, oversized/truncated fetches, retry exhaustion, cancellation and stale writes.
- Exercise child timeout/crash/orphan/shutdown, invalid output, unsupported versions and rollback of interrupted transactions. Test through packaged entry points as well as unit seams.
- Verify fresh schema and populated adoption, preserved snapshots/results, canonical hashes, deduplication and independent solver certificates.
- Run backend contract generation/checks, frontend `npm run check` and adapted `npm run test:live`; show all three strategies and reopen old two-strategy links against Python.
- Run locked setup and full checks from a clean source copy without Java installed for the active Python path. Java remains an optional reference-only verification dependency.
- Record representative cold/warm latency, solve time, peak memory and termination evidence; production load/resource approval remains NEM-020.
- NEM-080 may close local rebuild only when the parity matrix has no unexplained gaps, active runbooks use Python, and the rollback drill passes. NEM-038 remains blocked until hosted CI actually runs; M3 and launch must not be declared complete by local rebuild evidence.

## Cutover and recovery

Before switching the actual local runtime, verify a restorable backup and drained queues; stop both Java applications and disable their schedules. Adopt schema once, start Python API/worker with matching opt-in settings, check health/price reads, run a three-strategy simulation, reopen a Java-era result and exercise operator status. Keep secrets out of logs and fixtures.

If verification fails, stop Python, preserve diagnostics, and use the rehearsed Java reference start/backup recovery procedure. New Python jobs contain new execution versions and cannot be handed blindly to Java workers. Rollback must account for Python-era writes: use isolated rehearsal data, drain/version-check queues or restore the pre-switch backup only with explicit understanding that post-backup writes would be lost. No destructive restore is automatic. Record the actual outcome and next task in the existing journal/backlog.
