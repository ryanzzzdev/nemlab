# Durable refresh queue verification

Date: 2026-09-18  
Scope: NEM-028 within NEM-013; worker polling and operator HTTP endpoints are not implemented.

## What this proves in plain language

Several requests for the same price day do not create competing active jobs. Only one worker gets
permission to process a job at a time. If that worker stops responding, its permission expires and
another worker can retry. The old worker cannot later overwrite the result. Saving prices and
marking a job complete happen together: a database failure leaves neither half committed.

## Verification

Java 25 offline Gradle build passes with 75 tests: the existing 64 plus 11 queue integration cases.
Tests run Spring transaction proxies against disposable PostgreSQL 18.6, not mocks. They cover:

- Concurrent submissions, durable idempotency aliases and rejection of mismatched key reuse.
- Concurrent claim requests with multiple queued days and one global current claim.
- Expiry, replacement tokens, stale success/failure rejection and crash-loop exhaustion.
- Three-attempt retry limits and delayed availability.
- Cancellation that revokes write permission and records its actor.
- An injected completion failure rolling back prices, retrieval history and checkpoint changes.
- Expiry during price writes rolling back both complete and incomplete results.
- Incomplete coverage retained for diagnosis, followed by a successful retry.
- Input validation and the 100-job queue limit.

Flyway applies V1 and V2 to an empty test database and a second migration call is a no-op.
The existing ingestion tests still pass with V2 installed. No live OE calls or persistent local
schema migrations were performed. Changes remain uncommitted after baseline `9b5536e`.

## Limits and next work

This is a tested persistence service, not a running ingestion worker. NEM-029 adds worker
configuration, polling, scheduled submissions, execution bounds and shutdown handling. NEM-030
adds authorised operator submission/status/cancellation. Caller-provided actor strings are not
trusted authentication until that boundary exists. A lease fences database results; it does not
stop expired processes. Simulation dispatch and its process watchdog remain NEM-016.

The queue and retries are bounded; completed history retention and audit access controls still
need launch operational policy. Broad performance, live-provider and deployment claims are excluded.


Follow-up (2026-09-18): this queue slice was committed as `c5cd5a3`. NEM-029 worker execution
is now verified separately in [worker findings](worker-findings.md); NEM-030 remains outstanding.
