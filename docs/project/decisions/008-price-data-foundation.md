# 008 — Versioned price-day storage and resumable ingestion

Date: 2026-09-17  
Status: Accepted

## Decision

Use PostgreSQL 18.6 with Flyway migrations and Spring JDBC for the first persistent data slice:
five-minute regional NEM prices. Store immutable normalised day revisions, a mutable current
pointer, append-only import history, complete-day price snapshot references and persisted
backfill checkpoints. Each day has exactly 288 slots; missing and explicit source null are
separate from zero. Whole-day immutable JSONB is adequate for this bounded first slice; avoid
premature universal observation schemas before other metric semantics are settled.

Use explicit migration/import commands now. Keep automatic database configuration out of
application startup until worker/API integration is implemented. Commit a day and checkpoint
in one transaction, resume at the next unfinished day and reject stale checkpoint commits.
Scheduling, worker leases and authenticated operator APIs remain NEM-013.

## Alternatives and consequences

Overwriting prices would make old simulations unreproducible. A per-observation revision
schema would support wider metric/query needs but adds complexity before those adapters are
specified. No time-series extension is needed for the measured initial scope. GridReplay may
need additional storage structures; do not force uncertain metric semantics into this schema.

Retain original price revisions referenced by snapshots. A final retention and role/permission
policy is required before public operation. Data completeness and request freshness are
separate; failures preserve the previous accepted day and are visible in attempt history.

## Evidence and acceptance

Agent selection under the user's instruction to implement the next data-foundation task.
[Findings](../evidence/data-foundation/findings.md) record real PostgreSQL integration tests,
HTTP stub tests and exact saved OE fixture parsing. This accepts the PostgreSQL/Flyway/JDBC
part of decision 005; unrelated frontend recommendations remain proposed.

Versions are pinned by the image tag, Boot dependency management and Gradle lockfiles.
[PostgreSQL version policy](https://www.postgresql.org/support/versioning/) identified 18.6 as
the maintained 18.x release at implementation. The [OE market endpoint documentation](https://docs.openelectricity.org.au/api-reference/market/get-network-data/)
and our [validated price gate](../evidence/oe-validation/price-gate.md) inform the adapter.
Observed exclusive upper-bound behaviour takes precedence over generic documentation:
request boundary padding and select interval endings explicitly.
