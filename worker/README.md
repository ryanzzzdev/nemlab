# NEMLab worker

The non-web Spring Boot worker polls the durable queue and runs one price refresh at a time.
It is disabled by default. Migrate the database explicitly before enabling it; startup checks
connectivity and queue-table availability but does not apply migrations.

## Enable locally

Use Java 25. Build the executable jar with `./gradlew :worker:bootJar`.
Export the variables from the root `.env.example` after supplying real database credentials
and the OE key locally. Java and Gradle do not automatically load `.env`.

```sh
# If using your trusted local .env file:
set -a
. ./.env
set +a

# Run migrations once before starting the worker.
./gradlew :infrastructure:prices --args='migrate'

export NEMLAB_WORKER_ENABLED=true
export NEMLAB_WORKER_SCHEDULE_ENABLED=true
export NEMLAB_WORKER_REGIONS=NSW1
"$JAVA_HOME/bin/java" -Xmx256m -jar worker/build/libs/worker.jar
```

Setting `NEMLAB_WORKER_ENABLED=true` with scheduling disabled only consumes existing queued
jobs. Scheduling and manually submitted jobs share `RefreshJobService.submit` and the same
claim/fetch/commit path. Protected HTTP submission/status/cancellation is available through the [operator API](../api/README.md).
The direct-import CLI `start`/`resume` commands are retired; manual imports now use the queue.

## Settings

| Variable | Default | Behaviour |
| --- | --- | --- |
| `NEMLAB_WORKER_ENABLED` | `false` | Enables database readiness checks and polling. |
| `NEMLAB_WORKER_SCHEDULE_ENABLED` | `false` | Submits daily jobs when the worker is enabled. |
| `NEMLAB_WORKER_REGIONS` | Required if scheduled | Comma-separated NSW1, QLD1, SA1, TAS1, VIC1; choose explicit coverage. |
| `NEMLAB_WORKER_POLL_MS` | `5000` | Delay after each completed poll; allowed range 1000–60000. |
| `NEMLAB_DB_URL`, `NEMLAB_DB_USER`, `NEMLAB_DB_PASSWORD` | Required if enabled | PostgreSQL connection; connect timeout 5 seconds, socket timeout 10 seconds. |
| `OPEN_ELECTRICITY_API_KEY` | Required if enabled | Passed to the fetch child through its environment, never through arguments. |

Environment variables also have the equivalent Spring properties `nemlab.worker.enabled`,
`nemlab.worker.schedule-enabled`, `nemlab.worker.regions`, and `nemlab.worker.poll-ms`.
`--nemlab.worker.enabled=true` is useful for development; keep credentials out of command arguments.

## Daily scheduling and recovery

At or after 00:15 fixed UTC+10 NEM time, submit the preceding market day for each configured
region. Before 00:15, the eligible target remains the previous day's target. Polling and active
work can delay submission past that time. This uses NEM time, not daylight-saving wall time.

Each region/day uses a persistent `daily-price-v1` request key. Repeated polls, worker restarts,
and multiple worker instances cannot create duplicate scheduled work for the same target.
The scheduler only targets the latest eligible day; it does not backfill days missed during
extended downtime or automatically revisit earlier price corrections. Those need explicit
refresh requests. A terminal failed/cancelled daily job needs a new manual request key.

The database admits at most one current claim globally and 100 pending jobs. Expired claims
recover when polling resumes, with the existing maximum of three attempts and 30/60-second
backoff. Current deployments should still run one worker process.

## Deadlines and shutdown

Each fetch runs in a child JVM with `-Xmx128m`. The parent enforces a 240-second wall-clock
limit, forcibly terminates the child when necessary and waits up to five seconds for exit.
A child watchdog also exits after 240 seconds if its parent has died. The child has no database
credentials and never writes to the database; the parent publishes validated results inside
the existing token-fenced transaction. The five-minute claim leaves room for cleanup and the
30-second transaction budget. Simulation execution has separate limits below.

Stopping the application interrupts polling and kills the active child. The worker attempts
to record `WORKER_STOPPED` and release the claim for retry; if the database is unavailable,
lease recovery handles it later. Already completed work remains committed. Cancellation revokes
write permission immediately, but an in-flight fetch may continue until it returns or reaches
its deadline. An unkillable child stops further polling and emits an operator-intervention log.

## Failure diagnostics

| Code | Behaviour and next action |
| --- | --- |
| `HTTP_401`, `HTTP_403`, other non-429 HTTP 4xx | Terminal immediately; correct access/request conditions before a new refresh. |
| `INVALID_SOURCE_DATA_OR_CONFIGURATION` | Terminal; investigate source format or configuration before a new refresh. |
| `RETRY_AFTER_EXCEEDS_BUDGET` | Terminal; respect the provider's delay and request a later refresh. |
| `FETCH_DEADLINE_EXCEEDED` | Bounded retry; inspect source responsiveness if repeated. |
| `FETCH_PROCESS_FAILED`, `FETCH_FAILED`, transport/429/5xx codes | Bounded retry; inspect worker resources and source availability. |
| `WORKER_STOPPED` | Retry after the worker restarts. |
| `LEASE_EXPIRED` | The previous worker did not finish; polling recovers the claim. |

Logs contain job IDs and fixed messages, not credentials or raw provider responses. Fetch results
use an owned temporary file that is deleted after the child finishes; abrupt parent termination
can leave a price-only temporary file for normal OS temporary-file cleanup.

## Verification

`./gradlew build` exercises actual subprocess termination and PostgreSQL job transitions.
The packaged-worker test forces local source validation before any network call; no live OE
access is required. See [worker evidence](../docs/project/evidence/jobs/worker-findings.md).


## Simulation execution

NEM-040 adds independently enabled polling for the simulation queue. Apply migrations through
V3 before enabling `NEMLAB_SIMULATION_ENABLED=true`; set `NEMLAB_SIMULATION_POLL_MS` to
1000–60000 (default 5000). Database settings are shared with price refreshes. Simulation-only
mode needs no OE credential; both flags can be enabled together, with independent polling
threads and queue limits. Both are disabled by default.

```sh
export NEMLAB_SIMULATION_ENABLED=true
export NEMLAB_WORKER_ENABLED=false
"$JAVA_HOME/bin/java" -Xmx256m -jar worker/build/libs/worker.jar
```

Submit through the [public simulation API](../api/README.md#public-simulation-lifecycle),
which uses `SimulationJobs.submit(SimulationRequest)`. It captures exact normalised parameters,
version metadata and a complete immutable price revision in the same transaction as job
creation. Equivalent requests reuse the same job, including terminal jobs. Failed jobs
are not reset by resubmission; the public API preserves that rule. Retention remains launch work.

The simulation queue admits 100 pending jobs and one running claim globally, independent
of the refresh queue. Claims last 60 seconds. Crashes, deadlines and worker shutdown get
at most three attempts with 5/10-second retry delays. Expiry recovers when polling resumes;
late completion cannot publish. Invalid child output and unsupported stored versions fail
terminally. Internal claim tokens must never appear in public response DTOs.

Each simulation child has `-Xmx512m -XX:ActiveProcessorCount=2`, a cleared environment,
and no database/provider credentials. The existing 5-second/100,000-iteration solver
budget is cooperative. A 15-second parent deadline and child watchdog bound execution;
termination gets up to five seconds, and an unkillable child stops polling. Heap limits
are not total RSS/container limits. Temporary JSON files contain simulation inputs/results,
are bounded on read, and are deleted on normal exit/failure; abrupt parent death can leave
files for ordinary OS temporary-file cleanup.

The parent checks fixed-policy dispatch, physical constraints, every accounting total and
optimality metadata before atomically storing both results and terminal job status.
`SUCCEEDED` means certified `OPTIMAL`; `FEASIBLE_NOT_PROVEN` and other solver outcomes
produce `FAILED` jobs with immutable diagnostic results. Never display these as proven
hindsight. Engine diagnostic text is internal; NEM-041 maps public errors without exposing this text.
Hard process failures have safe job codes and no result payload. Inputs and saved results
remain unchanged when current source prices are corrected.

See [execution evidence](../docs/project/evidence/engine/execution-findings.md) and
[decision 016](../docs/project/decisions/016-durable-simulations.md).
