# Python rebuild parity baseline and gate (NEM-065, NEM-080)

Frozen: 2026-10-01. Task: [NEM-065](../../backlog.md#nem-065). Scope: exact delivered
behavior of the Java backend before any move or port. The parity matrix is filled in
and the local parity gate was closed under [NEM-080](../../backlog.md#nem-080) on
2026-10-02; see [Final verification](#final-verification-nem-080) and
[Cutover rehearsal](#cutover-rehearsal-nem-080).

Layout note: this document records the baseline at the pre-move layout. NEM-066 moved all
Java assets under `reference/java/`; module paths cited below (`core/`, `infrastructure/`,
`api/`, `worker/`, `scripts/`, Gradle files) now resolve under `reference/java/`, and the
`api/build/contract-responses/` capture output still lands at the repository root.

## Baseline record

| Item | Value |
| --- | --- |
| Backend HEAD | `0d881bf9348486e470349e4c60fd77a905979c50` (docs-only over `5ff5106`; Java source identical to plan baseline `e93142c`) |
| Frontend HEAD | `b48295e3533086f9c76ca66bc8802b27334ff29c` |
| Backend working tree | Clean except this task's additions. Planning docs committed as `5ff5106`/`0d881bf` during the session; `docs/project/todo.md` deletion committed there; `docs/project/zzz.md` untracked+ignored — user edits preserved. New build inputs: `infrastructure/src/test/java/au/nemlab/infrastructure/parity/ParityExport.java` and the `parityExport` task in `infrastructure/build.gradle` (this task's deliverable). |
| Frontend working tree | Clean |
| Toolchain | OpenJDK 25.0.4+7 at `/usr/lib/jvm/java-25-openjdk-amd64` (PATH `java` is 21 — JAVA_HOME must be explicit); Gradle 9.7.1 wrapper; Node 22.23.1/npm 10.9.8; Python 3.14.4 system / uv 0.11.29 (provisions CPython 3.13); Docker 29.7.2; no local `psql` — tests use Testcontainers `postgres:18.6-alpine`; project compose Postgres binds `127.0.0.1:55432` (5432 is held by an unrelated container). |

## Verification performed at baseline

| Check | Command | Result |
| --- | --- | --- |
| Full build + 150 tests | `JAVA_HOME=… ./gradlew clean build --offline --no-daemon` | PASS, 2m08s |
| Contract validation | `:api:checkContract` (inside build) | PASS — OpenAPI 1.3.0, 120 HTTP captures, 10 operations + error codes |
| Packaged startup | `python3 scripts/smoke_apps.py` | PASS — api + worker start credential-free, disabled features |
| Parity fixture export | `./gradlew :infrastructure:parityExport --offline` | Wrote `fixtures/parity-fixtures.json` (417 KB) |
| Frontend static check | `npm run check` in `nemlab-ui` | PASS — contract sync, prettier, tsc+vite build, 102 Playwright tests (39s) |
| Live stack harness | `npm run test:live` | PASS — 6 tests vs disposable Postgres 18.6 + packaged jars (1.7m). Visitor fetch hits real OE with a placeholder key and terminates HTTP_401 as designed. |

First `npm run check` failed 102/102 on missing Playwright `chromium-headless-shell` —
environment provisioning, not a regression; resolved by `npx playwright install chromium`.

## Frozen fixtures

| File | Contents | Regeneration |
| --- | --- | --- |
| `fixtures/parity-fixtures.json` | Decimal canonicalisation rows; request normalisation canonical strings + error field/code; per-day `contentHash`; scenario-key inputs (canonical + example key under fixed revision UUID); 10 full strategy runs (fixed/threshold/ordered-hindsight with per-interval dispatch, accounting, solver state/objective/bound/gap); stored `SimulationComparison` JSON for two- and three-strategy results. `elapsedNanos` deliberately excluded (nondeterministic). | `./gradlew :infrastructure:parityExport --offline` |
| `fixtures/http-responses/` | 120 sanitised captures (`method/path/status/headers/body`; never request bodies, credentials or query strings — see `ContractCapture`). | `./gradlew :api:test` writes `api/build/contract-responses/`; copy contents here. |
| `fixtures/saved-result-legacy-two-strategy.json` | Pre-NEM-049 stored shape: `fixedDispatch`, `fixedAccounting`, `hindsight` — **no `threshold` key** (vs `threshold: null` in the current writer). | Derived from `savedResults.twoStrategy` minus the key. |
| `core/src/test/resources/prices/*.csv` | Two validated NSW1 days (2026-09-11, 2023-09-11), 288 interval-end decimals each; already versioned. | Checked-in; update only deliberately. |

Notable frozen behaviors the port must reproduce:

- `BigDecimal("-0.00")` → plain `0.00`, canonical `0` — Java drops the sign on zero.
- Field bound check order: precision>38 or |scale|>18 → `DECIMAL_LIMIT` is checked on the
  *raw* input before `stripTrailingZeros`; range check uses `compareTo`; canonical output is
  `stripTrailingZeros().toPlainString()` (`1E+2` → `100`, `0.10` → `0.1`).
- `roundTrip` efficiency expands to legs via `sqrt` then `BigDecimal.valueOf(leg).stripTrailingZeros()`
  — the canonical string contains the float-derived decimal, e.g. rt 0.9 → legs `0.9486832980505138`.
- ojAlgo returns solver state `DISTINCT` (not `OPTIMAL`) on the degenerate no-headroom case;
  OPTIMAL publication still succeeds because the dual certificate + gap + accounting reconcile.
  Python must not require a specific native status name — use success + independent validation.
- `refresh_job.attempts` is incremented at claim; retry delay = `30 * attempts` (30s, 60s)
  before terminal failure at 3 attempts. Simulation delay = `5 * attempts` (5s, 10s).
- Daily schedule submits `daily-price-v1:{region}:{day}` for the *previous* NEM day once
  local time is ≥ 00:15+10:00 (`now − 15min → date − 1`). Visitor keys `visitor-price-v1:…`,
  `:rN` retry suffixes, max 3/day and 10 pending globally.

## HTTP surface (10 operations, OpenAPI 1.3.0)

| Route | Flag | Notes |
| --- | --- | --- |
| `GET /api/v1/prices/{region}/coverage` | `NEMLAB_DATA_ENABLED` | 1–31 completed days; NOT_IMPORTED gap state |
| `GET /api/v1/prices/{region}/{day}` | `NEMLAB_DATA_ENABLED` | 288 intervals; null prices ≠ missing ≠ zero |
| `POST /api/admin/v1/price-refreshes` | `NEMLAB_ADMIN_ENABLED` + bearer | Idempotency-Key binds region/day; 202/400/401/409/429 |
| `GET /api/admin/v1/price-refreshes` | same | bounded `limit` 1–100 |
| `GET /api/admin/v1/price-refreshes/{id}` | same | 404 unknown |
| `GET …/{id}/events` | same | int64 cursor pagination |
| `POST …/{id}/cancel` | same | 200/401/404 |
| `POST /api/v1/simulations` | `NEMLAB_SIMULATION_API_ENABLED` | ≤16384 B body, JSON media type only, strict parse; 202/200-dup/400/409/413/415/429/503 |
| `GET /api/v1/simulations/{id}` | same | status/Retry-After; 404 unknown |
| `GET /api/v1/simulations/{id}/result` | same | 200 stored comparison; 409 pending/failed |
| `GET /actuator/health` | always | liveness only |

Strict JSON (api `SimulationJson`): Jackson3 `STRICT_DUPLICATE_DETECTION` +
`FAIL_ON_TRAILING_TOKENS`, fixed field allowlists per object, decimals required as
strings, `day` must match `YYYY-MM-DD`, integer (not boolean) window minutes. Operator
auth: SHA-256(token) constant-time compare, `WWW-Authenticate: Bearer` on 401, plain 403
(not exercised by captures), actor `operator:<name>`; token `43–128` base64url chars.
Disabled routes return 404 without the application error body. Default serve
`SERVER_ADDRESS=127.0.0.1`, `PORT=8080`; `spring.jackson …fail-on-unknown-properties=true`.

## Environment / flags (defaults from `.env.example` + code)

| Variable | Used by | Default |
| --- | --- | --- |
| `NEMLAB_DB_URL` / `_USER` / `_PASSWORD` | api (enabled features), worker, CLI | `jdbc:postgresql://127.0.0.1:55432/nemlab`, `nemlab`, none |
| `OPEN_ELECTRICITY_API_KEY` | fetch child only | none — required to fetch |
| `NEMLAB_WORKER_ENABLED` | worker | `false` |
| `NEMLAB_WORKER_SCHEDULE_ENABLED` | worker | `false` (requires worker enabled) |
| `NEMLAB_WORKER_REGIONS` | worker schedule | `NSW1` (comma list) |
| `NEMLAB_WORKER_POLL_MS` | worker | `5000` |
| `NEMLAB_SIMULATION_ENABLED` | worker | `false` |
| `NEMLAB_SIMULATION_POLL_MS` | worker | `5000` |
| `NEMLAB_ADMIN_ENABLED` | api | `false` |
| `NEMLAB_ADMIN_OPERATOR` / `NEMLAB_ADMIN_TOKEN` | api | required when admin enabled |
| `NEMLAB_DATA_ENABLED` | api | `false` |
| `NEMLAB_SIMULATION_API_ENABLED` | api | `false` |

## Commands inventory

Backend: `./gradlew clean build [--offline] --no-daemon` (tests + `verifyModuleBoundaries` +
`checkContract`), `:api:bootJar`/`:worker:bootJar` then `java -jar`, `:api:checkContract`,
`:core:hindsightBenchmark`, `:infrastructure:prices --args='migrate|coverage|history|status|backfill…'`,
`:infrastructure:parityExport`, `python3 scripts/smoke_apps.py`,
`npm ci --ignore-scripts --prefix api/contracts`, `npm run generate --prefix api/contracts`,
`docker compose up -d postgres`.
Frontend: `npm run check` (`contract:check` + `format:check` + build + Playwright),
`npm run test:live`, `node scripts/contract.mjs [--sync]`.
CI: `.github/workflows/backend.yml` (temurin 25.0.4+7, Node 22.23.1, npm ci + gradle build +
smoke). Hosted run never executed — NEM-038.

## Schema objects (V1–V3, PostgreSQL 18.6)

Tables: `price_revision`, `price_current`, `price_import_attempt`, `price_snapshot`,
`price_backfill`, `refresh_job`, `refresh_request`, `refresh_job_event`,
`simulation_input`, `simulation_job`, `simulation_result`.
Functions/triggers: `reject_immutable_price_change` (UPDATE/DELETE on price_revision,
price_snapshot), `require_complete_price_snapshot` (INSERT on price_snapshot,
simulation_input), `reject_immutable_simulation_change` (simulation_input, simulation_result).
Indexes: `price_attempt_history`, `refresh_job_active_day` (partial unique),
`refresh_job_ready` (partial), `simulation_job_ready` (partial),
`simulation_one_running` (partial unique — global single-runner constraint).
Constraints encode the claim-token/lease invariant (`RUNNING ⇔ token+lease set`) and the
`FAILED ⇔ no revision` attempt invariant. Flyway `flyway_schema_history` holds V1–V3.

## Operational constants (verified against code)

| Queue | Advisory lock | Lease | Attempts | Backoff | Pending cap | Extra |
| --- | --- | --- | --- | --- | --- | --- |
| refresh | `pg_advisory_xact_lock(735028)` | 300s | 3 | `30*attempts` → 30s/60s | 100 | visitor: 10 pending, 3/day, keys `visitor-price-v1:*` |
| simulation | `pg_advisory_xact_lock(735040)` | 60s | 3 | `5*attempts` → 5s/10s | 100 | ≤1 RUNNING globally; tx timeout 30s (refresh) / explicit tx template |

Fetch child: `--fetch-price` mode, 240s in-child watchdog + parent deadline, `-Xmx128m`,
cleared environment + explicit vars only, OE client 10s connect/30s request timeout,
redirects NEVER, 2 MB body cap; retryable = everything except non-429 HTTP 4xx and
`RETRY_AFTER_EXCEEDS_BUDGET`; `IllegalArgumentException` → terminal
`INVALID_SOURCE_DATA_OR_CONFIGURATION`.
Simulation child: `--simulate` mode, 15s in-child watchdog `halt(124)`, parent timeout 15s
+ 5s termination, `-Xmx512m -XX:ActiveProcessorCount=2`, input file ≤ 512 000 bytes,
output = Jackson `SimulationComparison`; parent revalidates before publish.
Solver budget: `OrderedHindsight.Limits.standard()` = 5000 ms / 100 000 iterations;
OPTIMAL requires solver-optimal + finite nonnegative gap ≤ 0.01 + accounting reconcile
(`1e-6 + 1e-9·max`) + within budget. Energy tolerance `1e-7` in DispatchValidator.

## Java test inventory (150 @Test, all pass)

core (52): BatteryEngineTest 14, HindsightTest 10, PriceThresholdTest 13,
SimulationComparisonTest 5, SimulationRequestTest 9 (+ HindsightBenchmark harness).
infrastructure (45): RefreshJobServiceTest 12, ScenarioPreparationTest 6,
SimulationJobsTest 11, PriceImportCommandTest 1, PriceIngestionTest 15.
api (28): AdminHttpTest 8, PriceReadHttpTest 6, ApiApplicationTest 2,
SimulationHttpTest 12 (+ ContractCapture).
worker (25): WorkerApplicationTest 1, RefreshWorkerTest 9, PriceFetchProcessTest 4,
SimulationWorkerTest 5, SimulationProcessTest 7 (+ FetchFixture, SimulationFixture).
Frontend: 102 Playwright browser cases + 6 live-stack cases, all pass.

## Parity matrix (capability → sources → Python implementation → evidence)

All rows closed under NEM-080. Python test files run against real PostgreSQL 18.6
scratch databases unless noted; `tests/parity/test_java_parity.py` replays the frozen
`parity-fixtures.json` rows.

| Capability | Java sources / tests | Python module + tests | Evidence |
| --- | --- | --- | --- |
| Market time, decimal bounds, request normalisation | core `PriceDay`, `SimulationRequest`, `Efficiency`, `ScheduleWindows`, `Numbers`; SimulationRequestTest, BatteryEngineTest | `nemlab_core/{numbers,decimal_text,request,windows,prices}.py`; `core/tests/test_engine.py`, `tests/parity/test_java_parity.py` | `requests`/`decimalForms` fixture rows byte-equal; NEM-068 |
| Fixed schedule + accounting | core `FixedSchedule`, `BatterySimulation`, `DispatchValidator`, `Accounting` | `nemlab_core/{fixed,battery,dispatch,accounting}.py`; `core/tests/test_engine.py`, parity replay | `runs[*].fixed` per-interval + totals identical; NEM-068 |
| Threshold strategy | core `PriceThreshold`, `Thresholds`, `SimulationComparison`; PriceThresholdTest, SimulationComparisonTest | `nemlab_core/{threshold,comparison}.py`; `core/tests/test_threshold.py`, `test_comparison.py` | `runs[*].threshold`; strict `<`/`>` equality-hold; NEM-068 |
| Ordered hindsight LP + dual certificate | core `OrderedHindsight`; HindsightTest, HindsightBenchmark | `nemlab_core/hindsight.py` (SciPy `linprog(method="highs-ds")`); `core/tests/test_hindsight.py`, parity replay | `runs[*].hindsight` objective/bound/gap parity; OPTIMAL on success + independent validation, no native-status-name dependency; NEM-069 |
| OE import + revision/snapshot storage | infra `OePriceSource`, `PriceBatch`, `PriceStore`, `PriceBackfill`, `PriceImportCommand`; PriceIngestionTest, PriceImportCommandTest | `nemlab_infrastructure/prices/{source,batch,store,backfill,cli}.py`; `test_price_ingestion.py` (16), `test_price_command.py` | `priceDays[*].contentHash` asserted; V1–V3 schema, real-PG tests; NEM-071 (`23d7cd3`) |
| Refresh queue + visitor admission | infra `RefreshJobService`, `RefreshJob`; RefreshJobServiceTest | `nemlab_infrastructure/jobs.py` (+ `prices/store.py` tx internals); `test_refresh_jobs.py` (15 + adoption-read test) | locks/leases/claims matrix, concurrent-claim races, atomic rollback; NEM-072 (`17e5b05`) |
| Fetch/schedule worker | worker `RefreshWorker`, `RefreshSchedule`, `PriceFetchProcess`, `FetchCommand`; worker tests | `nemlab_worker/refresh.py`; `worker/tests/test_refresh.py` (16) + `fetch_fixture.py` child | process lifecycle cases, cleared-env child, failure classification; NEM-073 (`b316e86`) |
| Public price + operator HTTP | api `PriceReadController`, `AdminRefreshController`, errors, security; AdminHttpTest, PriceReadHttpTest | `nemlab_api/{prices,admin,errors,middleware,validation}.py`; `api/tests/test_price_http.py`, `test_admin_http.py` | `fixtures/http-responses/` shapes byte-identical; live captures validate against `api/contracts/openapi.json`; NEM-074 (`a3a8fdc`) |
| Simulation persistence | infra `ScenarioPreparation`, `SimulationJobs`; their tests | `nemlab_infrastructure/simulations.py`; `test_simulations.py` (18) | `scenarioKeys`, `savedResults`, legacy-shape read; NEM-075 (`692df46`) |
| Simulation supervision | worker `SimulationWorker`, `SimulationProcess`, `SimulationCommand`; their tests | `nemlab_worker/simulation.py`; `worker/tests/test_simulation.py` (15) + `simulation_fixture.py` | child lifecycle + parent revalidation; NEM-076 (`5e642b0`) |
| Simulation HTTP | api `SimulationController`, `SimulationJson`, errors; SimulationHttpTest | `nemlab_api/simulations.py`; `api/tests/test_simulation_http.py` (12) + `test_contract_captures.py` | strict-JSON cases, status matrix; `verify.mjs` 61 captures green; NEM-077 (`9cb9223`) |
| Runtime/ops | application.properties, READMEs, smoke_apps.py, workflow | `Dockerfile` (api/worker/migrate targets), `compose.yaml` apps profile, `.github/workflows/backend.yml`, `scripts/smoke_apps.py` | credential-free start, flags independent; clean-clone `uv sync` + all checks with no Java; NEM-078 (`5c9c94e`) |

## Discrepancies and resolutions

| # | Finding | Resolution |
| --- | --- | --- |
| 1 | `api/contracts/README.md` says "seven contracted operations"/"initially version 1.0.0"; the live contract is 1.3.0 with 10 operations. | Doc drift only; record here, fix wording when the file is next touched (NEM-078). |
| 2 | `docs/project/architecture.md` says tests "pass … 33 tests" style counts scattered in older evidence — superseded by this inventory (150). | Historical evidence stays historical; this file is the current count. |
| 3 | Plan lists visitor retry delays "30/60-second" and simulation "5/10-second"; actual formula is `30*attempts`/`5*attempts` after the claim increment (identical values). | Consistent — Python uses the formula, not a literal pair. |
| 4 | `test-live.py` seeds revisions with placeholder `content_hash='aaaa…'` — reads trust the stored hash; nothing recomputes it at read time. | Keep: Python reads must not recompute stored hashes either. |
| 5 | `versions.canonical()` includes `"ojAlgo 57.3.0"` as solver identity — new Python runs MUST NOT reuse it. | New `solver`/`executionProfile` strings for Python per plan; old rows keep their stored versions verbatim. |
| 6 | No stored result in any fixture lacks `threshold`; the legacy shape was reconstructed by removing the key. | Resolved: the NEM-080 populated-clone rehearsal read a real Java-era stored result through the Python API — all fields round-tripped and `ojAlgo 57.3.0` metadata survived verbatim. See `cutover-rehearsal.md`. |

## Populated-database / queue compatibility requirements

- Clone via `pg_dump`/`pg_restore` or a volume snapshot; snapshots stay outside Git.
- Expected `flyway_schema_history`: V1, V2, V3 success rows (checksums recorded at adoption time, NEM-070).
- Cutover prerequisites: Java API/worker stopped, schedules disabled, `refresh_job` and
  `simulation_job` have no QUEUED/RUNNING rows (drain or cancel via Java controls).
- Old `simulation_result` JSON must deserialize in both shapes (no `threshold` key;
  `threshold: null`). Old `solverState` strings (`OPTIMAL`, `DISTINCT`, …) are display
  metadata — never parsed for logic.
- The queue tables are version-agnostic — Python workers claim the same rows; mixed
  Java/Python worker operation is prohibited by the plan.

## Prerequisites inventory for the campaign

| Need | Status |
| --- | --- |
| JDK 25 + Gradle wrapper (reference builds, fixture regen) | present at `/usr/lib/jvm/java-25-openjdk-amd64`; PATH default is 21 — always set JAVA_HOME |
| Docker daemon | running; Testcontainers pulls `postgres:18.6-alpine` (already cached) |
| Node 22.23.1 / npm 10.9.8 | present; `api/contracts` tooling installed |
| Playwright chromium | installed this session (was missing) |
| Python 3.13 | system has 3.14; provision via `uv python pin`/`uv.lock` at NEM-067 |
| OE API key | present locally (`.env`, gitignored) — needed only for live fetches, not for parity fixtures |
| Compose Postgres on 55432 | compose file present; volume `nemlab-postgres` holds the user's data — never test destructive ops against it |

## Cutover rehearsal (NEM-080)

Full record: [cutover-rehearsal.md](cutover-rehearsal.md). Summary, 2026-10-02:

- Populated Java DB (10 revisions / 10 days / 10 refresh jobs / 13 simulation
  jobs + results, all queues drained) dumped and restored to `nemlab_rehearsal`.
- `migrate check` → `java-managed`; `adopt` stamped `nemlab_baseline_v1_v3`;
  `flyway_schema_history` preserved.
- Empty setup rehearsed on `nemlab_empty`: `check` → `empty`, `migrate` →
  `alembic-managed`.
- Python API read historical prices and a Java-era result verbatim
  (`ojAlgo 57.3.0` preserved); Python worker executed a new simulation to
  `SUCCEEDED` with `HiGHS 1.12.0 via SciPy 1.18.1 linprog/highs-ds` metadata.
- The reference Java API booted on the adopted clone (Flyway validate passed)
  and read the Python-written result plus Java-era prices — both-direction
  read compatibility confirmed.
- Rollback: restore pre-cutover dump into `nemlab_rollback` → `java-managed`,
  Java resumes unmodified; post-switch writes absent as expected. A forward
  dump/restore of the adopted clone preserved adoption state + Python writes.
  No automatic destructive restore exists by design.

## Final verification (NEM-080)

Combined gates run once against the final tree, 2026-10-02:

| Gate | Command | Result |
| --- | --- | --- |
| Locked deps | `uv sync --all-packages --locked` | PASS |
| Lint | `uv run ruff check .` | PASS |
| Format | `uv run ruff format --check .` | PASS (82 files) |
| Types | `uv run mypy` | PASS (45 source files) |
| Import boundaries | `uv run lint-imports` | PASS (1 contract kept) |
| Full tests | `uv run pytest` | 285 passed, 1 warning (78 s) |
| Contract | `(cd api/contracts && node verify.mjs)` | PASS — 61 captures, 10 operations, all error codes |
| Frontend | `npm run check` (nemlab-ui) | PASS — contract, format, build, 102 Playwright tests |
| Live stack | `npm run test:live` | PASS — 6/6 vs real Python API + worker + PostgreSQL |

Two repairs during the final pass (doc/script scope only): ruff `scripts/**`
per-file ignores for `smoke_apps.py` (S101/S607), and `FastAPI` typing on
`register_simulation_errors` (mypy untyped-decorator).

## Intentional differences (accepted)

- **Solver metadata**: stored `versions.solver` is provenance. Java-era rows
  keep `ojAlgo 57.3.0` verbatim forever; Python writes
  `HiGHS 1.12.0 via SciPy 1.18.1 linprog/highs-ds`. Both are display metadata —
  never parsed for logic.
- **Degenerate optimum**: ojAlgo reports `DISTINCT` where HiGHS reports
  `OPTIMAL` on the no-headroom case. Python publishes on success + independent
  validation (gap ≤ 0.01, accounting reconcile, budget), not on a native
  status name — matching the parity plan.
- **`test-live.py` placeholder `content_hash`**: reads trust stored hashes;
  neither implementation recomputes them at read time (discrepancy #4).

## Limits and pending gates

Recorded in [cutover-rehearsal.md](cutover-rehearsal.md#numerical-performance-and-resource-limits):
solver budgets/tolerances identical to Java; sim child ~110 MiB RSS / ~1.9 GiB
virtual / ~0.6 s with a 4 GiB **address-space** (not RSS) bound; queue caps and
backoffs unchanged. Pending: NEM-038 hosted CI (never run), NEM-020 deployment.
