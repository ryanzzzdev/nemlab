# Price data infrastructure

This module retrieves five-minute regional prices from Open Electricity and saves immutable
price-day revisions in PostgreSQL. Repeated content reuses a revision; a correction creates a
new revision. Saved price snapshots continue to reference the original values.

It depends on core. The API and worker do not automatically configure a database or run
migrations; the local operator command below explicitly opts into database access. Scheduled
polling, distributed leases and protected administrator endpoints belong to NEM-013.

## Local database

Requirements: JDK 25, Python 3 for application smoke checks, and Docker for PostgreSQL tests
or local Compose. Tests start a disposable PostgreSQL 18.6 container; they do not use the
configured local database or require an OE key. The first run needs access to Maven Central
and the PostgreSQL/Testcontainers container images; offline Gradle mode does not prevent a
missing Docker image from being downloaded.

For a persistent development database, choose and export a local password, then run:

```sh
export NEMLAB_DB_URL='jdbc:postgresql://127.0.0.1:55432/nemlab'
export NEMLAB_DB_USER='nemlab'
export NEMLAB_DB_PASSWORD='<your local password>'
docker compose up -d postgres
./gradlew :infrastructure:prices --args='migrate'
```

Compose exposes PostgreSQL on loopback port 55432 and stores data in its named volume.
`docker compose stop postgres` stops it without deleting that volume. Do not use `down -v`
unless deliberately discarding the local database.

Copy the field names from the root `.env.example` as needed. Compose reads `.env`; Gradle
and the Java command **do not**. Export the variables in the command's environment (including
`JAVA_HOME` pointing at JDK 25). The OE key is needed only for `resume`; do not put it in
command arguments. Migrations run explicitly, once per deployment, before ingestion.

## Bounded import and recovery

Each backfill covers one region and 1–31 completed market days. The end date is exclusive.
Dates before 2021-10-01 and incomplete current market days are rejected. For the previously
validated historical sample:

```sh
./gradlew :infrastructure:prices --args='start NSW1 2023-09-11 2023-09-12'
# Copy the returned UUID into the following commands.
./gradlew :infrastructure:prices --args='resume <backfill-uuid>'
./gradlew :infrastructure:prices --args='status <backfill-uuid>'
./gradlew :infrastructure:prices --args='coverage NSW1 2023-09-11'
./gradlew :infrastructure:prices --args='history NSW1 2023-09-11'
```

A resume invocation attempts at most 31 one-day steps and stops on failure/incomplete data.
It exits unsuccessfully if the range remains paused. Retrying `resume` uses the persisted next
day. Successfully saved days are not fetched again by that backfill. To refresh an already
completed range for source corrections, create another backfill for the same dates.

A one-day OE query includes the midnight boundary padding established by M1. Normalisation
selects interval endings in `(day start, next midnight]` and retains exactly 288 slots. Missing
rows, explicit nulls and numeric zero remain different states. Invalid metadata, duplicate or
misaligned timestamps and invalid values reject the response. No missing values are filled.

The adapter retries transport errors, HTTP 429 and 5xx at most three times. Default waits are
one and two seconds; Retry-After seconds or dates can extend a wait up to 60 seconds. Longer
requested delays pause the backfill instead of retrying early. Permanent HTTP errors do not
retry. Each request has a 30-second configured timeout and a two-megabyte response cap;
these are not a worker-level hard execution watchdog. Response bodies and keys are not
included in failure diagnostics.

## Coverage and snapshots

`coverage` shows the latest accepted revision, retrieval time and counts of valid, missing
and source-null slots. `history` shows individual attempt outcomes, response hashes, source
versions and safe failure codes; failed refreshes do not erase the previous accepted day.
An incomplete accepted response becomes current coverage, explicitly preventing a complete
simulation from silently using stale values. Old complete snapshots remain usable.

`PriceStore.snapshot(revisionId)` accepts only complete days. Snapshot prices are reconstructed
as the core's strict `PriceDay`. These are immutable **price-input references**; simulation
parameters/results and public sharing will be added in NEM-016. Current-pointer changes
never rewrite a revision or snapshot. Ordinary SQL updates/deletes of those records are
rejected; privileged database administration is outside that immutability guarantee.

## Tests and remaining scope

```sh
./gradlew clean build
```

Docker must be available: PostgreSQL tests fail rather than silently skip when it is missing.
See [data-foundation findings](../docs/project/evidence/data-foundation/findings.md) for evidence.
No live OE request was made during this implementation verification. Broader launch coverage,
non-price GridReplay ingestion, retention policy, worker scheduling and public APIs remain
separate work. Nothing here promises availability of every requested historical day.
