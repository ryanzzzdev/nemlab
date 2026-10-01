# NEM-040 — Durable simulation execution and results

Date: 2026-09-20. Implementation and records committed as `a151677`.

## Delivered

V3 adds immutable inputs/result records and a separately bounded simulation queue.
Submission persists the captured complete price revision, normalised request and all
version metadata atomically. Scenario keys deduplicate concurrent and terminal requests.
Claim tokens/expiry fence publication; recovery/retries are bounded to three attempts.
Refresh and simulation queues can each run one job independently.

Opt-in simulation polling uses an isolated 512 MiB child JVM with two active processors,
the existing cooperative solver limits and a 15-second hard parent/child deadline.
The cleared child environment contains no provider/database credentials. Parent validation
checks fixed policy, physical constraints, all accounting totals and optimality metadata
before atomically storing both strategy results and terminal job status. Only OPTIMAL
succeeds. Unproven and failed solver outcomes remain explicit diagnostic results.

## Verification

`JAVA_HOME=/usr/lib/jvm/java-25-openjdk-amd64 ./gradlew build --offline --no-daemon`
passes **141 tests**, zero failures/errors/skips: core 57, infrastructure 43, API 15,
worker 26. This adds 25 cases to the previous 116-test baseline. The existing contract
check validates 46 real HTTP responses across seven operations; no API contract changed.
`python3 scripts/smoke_apps.py` with the same JAVA_HOME passes packaged API and disabled
worker startup. Both worker flags are explicitly disabled by that smoke script.

New evidence includes:

- Three core comparison cases: valid engine output, tampered physical/accounting/proof
  metadata, nonfinite/expired optimality claims and failed outcomes without dispatch.
- Ten PostgreSQL queue/result cases: V3 migration and safe repeat; concurrent submission
  and claiming; durable deduplication; exact 230 AUD manual oracle for both strategies;
  immutable stored results/inputs after corrections and service recreation; three-attempt
  crash recovery; delayed retries and permanent failure; feasible-but-unproven preservation;
  invalid-accounting rejection; injected transaction failure/lease expiry during result
  publication; submission rollback; queue saturation; independence from running refreshes.
- Seven subprocess cases: real solver JSON round-trip with empty environment; executable
  Boot-jar child mode; parent timeout; shutdown and temporary-file cleanup; malformed,
  oversized and crashed children; unsupported-version rejection; the actual 15-second
  orphan watchdog firing while the test parent's deadline is 25 seconds.
- Five worker/database cases: restart from abandoned claims to saved actual child output;
  graceful shutdown/retry; deadline exhaustion after three attempts; disabled, simulation-only
  and combined worker configuration (including invalid poll rejection); a packaged worker
  polling PostgreSQL, launching its own real solver child and persisting results.

The initial targeted run passed storage checks but exposed a race in the new test helper:
status and attempt count were read separately across a claim transition. It now reads one
job snapshot, and the await helper does not re-evaluate an already satisfied condition.
No production retry logic was weakened. The full build subsequently passed.

Tests use disposable PostgreSQL containers, synthetic prices and existing local fixtures.
No live OE request or persistent database migration was performed. Existing integration
fixture cleanup lists now include the three simulation tables to respect foreign keys.
Frontend code did not change; browser tests were not repeated. Documentation links and
diff whitespace checks pass.

## Operational limits and follow-up

Both execution flags default off. Migrations remain an explicit operator step; no migration
runs at worker startup. The queue lease is 60 seconds, retry delays 5/10 seconds, pending
capacity 100 and transaction budget 30 seconds. An unkillable process stops polling.
The child heap ceiling is not a total-process/container memory guarantee. Host sizing,
load tests, retention and final public quotas remain NEM-020.

Terminal failures are retained and deduplicated; this slice does not reset failed jobs or
expose a user retry endpoint. NEM-041 owns public HTTP submission/status/results, safe
response DTOs, retry semantics and generated contracts. Claim tokens and internal solver
diagnostic text must not leak through those DTOs. No frontend simulation workflow, hosted
CI run, commit, push or deployment is implied. See [decision 016](../../decisions/016-durable-simulations.md)
and [worker setup](../../../../reference/java/worker/README.md#simulation-execution).
