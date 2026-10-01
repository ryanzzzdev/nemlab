# NEM-012 — Price ingestion and storage findings

Date: 2026-09-17

## What this adds

The backend can save historical prices without overwriting old versions. Importing the same
prices again does not duplicate the version. A correction creates another version, while a
saved simulation's price reference still points at its original data. Missing prices are
visible and stop the creation of a simulation snapshot.

Backfills work one day at a time and remember their next day in PostgreSQL. If a fetch fails,
data is incomplete, or a process restarts, the same backfill can resume without starting over.
This is a price-first implementation, not an importer for every OE metric.

## Verification

A clean offline build passed 63 tests. After adding operator history/failure-code verification,
the final offline `build` passed **64 tests**, zero failures/errors/skips: 49 existing engine/app
cases and 15 PostgreSQL/price-ingestion cases. Gradle dependencies and Docker images were
already cached for the final run. The tests used a real disposable PostgreSQL 18.6 container;
no existing database was modified and no live OE request was made.

Checks cover:

- Applying Flyway migrations and applying them again safely.
- Parsing the saved 289-point historical OE response into the correct 288 interval endings,
  including its six negative and two zero values.
- Rejecting wrong units/regions, duplicate timestamps and misaligned intervals.
- Distinguishing absent rows, explicit nulls and zero; incomplete snapshots are rejected.
- Repeated and concurrent imports creating one revision with separate attempt records.
- Source corrections creating a new revision while old snapshots retain their exact prices.
- Older fetches not replacing fresher current coverage; reverting content reusing its old revision.
- Database enforcement against ordinary changes/deletes of immutable revisions/snapshots.
- Restarting from the persisted next day after a failed second day.
- Pausing an incomplete day and completing it after a later refresh.
- Injecting a checkpoint-update failure and proving the data and attempt writes also roll back.
- Rejecting stale checkpoint commits and invalid/unbounded date ranges.
- Local HTTP stub responses exercising 429 recovery, permanent 401 failure, bounded 503/429
  retries, request-boundary parameters, sanitized diagnostics and response-size cancellation.
- Operator status/history preserving the safe HTTP_401 diagnostic without response bodies.

Packaged API/worker smoke checks also passed after persistence libraries were added. Compose
configuration was validated without starting a persistent development database. No hosted CI
run was performed.

## Stored records and provenance

`price_revision` holds immutable canonical 288-slot days with SHA-256 content identities and
valid/missing/null counts. Its identity includes region, date, metric/unit, interval-end
interpretation and fixed UTC+10 semantics. Decimal trailing zeros are normalised for identity;
no source value is rounded. Price values are finite, with at most 38 significant digits and
absolute scale <=18; unsupported extreme values are rejected rather than expanded/truncated.

`price_current` selects the latest fetched accepted version. `price_import_attempt` records
retrieval time, complete/incomplete/failed status, raw response hash, source API version and
safe error code. The endpoint and query construction are fixed in the source adapter and
reconstructible from region/day; raw response bodies and credentials are not persisted.

`price_snapshot` references a complete immutable day, protected by a foreign key and database
validation. It is a price-input snapshot only; NEM-016 owns simulation parameters and results.
`price_backfill` stores bounded dates, next day and active/paused/complete status. Each accepted
day and checkpoint update shares one database transaction; stale checkpoint commits roll back.
This is an optimistic checkpoint fence, not a distributed worker lease.

PostgreSQL administrative privileges can bypass normal application protections. Final
application/migration role separation and retention procedures remain deployment work.

## Versions and ownership

PostgreSQL image: `postgres:18.6-alpine`. Boot 4.1.1 dependency management and lockfiles resolve
Spring JDBC 7.0.9, Flyway 12.4.0, PostgreSQL JDBC 42.7.13, Jackson 3.1.5 and Testcontainers 2.0.5.
The infrastructure code is explicit Java/JDBC; no Spring data-source or migration auto-start is
enabled in the API/worker shells. The local `prices` command invokes migrations/imports on request.

See [operator instructions](../../../../reference/java/infrastructure/README.md),
[storage decision](../../decisions/008-price-data-foundation.md) and [NEM-012](../../backlog.md#nem-012).

## Limits and next work

Dates are post-2021-10-01, completed NEM days, one region at a time, at most 31 days per backfill.
Structural completeness is not an independent audit of OE's historical values or broader
regional coverage. Current-day refresh delays and overlap scheduling, leases, cancellation,
protected manual triggers and hard execution limits belong to NEM-013. Business read APIs
belong to NEM-014. GridReplay metric adapters are scoped with NEM-018 after timing/representation
questions are resolved. NEM-020 owns coverage claims, retention, deployment and load validation.
