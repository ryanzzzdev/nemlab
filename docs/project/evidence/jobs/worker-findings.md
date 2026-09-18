# Worker execution verification

Date: 2026-09-18  
Scope: NEM-029, built on the queue committed as `c5cd5a3`.

## What this proves in plain language

The worker can pick up a queued price refresh, fetch the prices in an isolated process, and
save the result. It can also submit the previous day's refresh automatically. Restarting it
does not duplicate scheduled work. A stalled fetch is killed; stopping the worker releases
its work for retry or leaves an expiring lease if the database is unavailable.

## Verified

The Java 25 offline Gradle build passes 88 tests: the previous 75 plus 13 worker/subprocess cases.
These use PostgreSQL 18.6 and actual Java child processes, not only mocks:

- A manually submitted queue job reaches successful persisted coverage.
- A new worker recovers an abandoned expired claim and rejects the old token.
- Permanent credential failure is recorded after one attempt.
- Graceful shutdown kills an active child and leaves the job queued for retry.
- Fixed UTC+10 scheduling crosses the 00:15 boundary and deduplicates after restart.
- Enabled configuration starts against a migrated database; disabled configuration needs no credentials.
- Invalid polling interval, region or missing OE credential rejects startup.
- Child-result JSON round-trips exact prices and removes its temporary output.
- A shortened one-second test deadline kills a stalled process before returning failure.
- Closing the fetcher kills its child and rejects subsequent fetches.
- Crashed/malformed child output becomes a safe failure code.
- The packaged Boot jar starts its own fetch child and persists terminal source-validation failure.
  This test deliberately uses a future day so validation happens before any OE network request.

The packaged API health and disabled-worker startup smoke checks also pass. Smoke checks
explicitly disable worker execution so inherited environment settings cannot trigger OE traffic.

The production fetch deadline is 240 seconds, followed by at most five seconds to confirm child
termination. Child heap is 128 MiB. Its own 240-second watchdog bounds orphaned work. The worker
retains the five-minute queue lease and 30-second transaction budget. Cancellation prevents
publication; it does not promise immediate provider-request termination.

## Limits and remaining work

No live OE calls, persistent development database migrations, or production scheduling were
performed. Process tests shorten the parent timeout rather than waiting four minutes. This is
functional recovery evidence, not a measured production throughput or total-memory claim.

Daily scheduling targets only the latest eligible day. Extended downtime, terminal daily failures
and later price corrections require explicit new refresh requests. Protected operator HTTP
controls are NEM-030; the shared submission service is currently an internal boundary.
Simulation subprocess limits remain NEM-016. Hosted CI has not run in this workspace.

The initial build caught eager Gradle test-classpath resolution; moving that resolution to test
execution fixed it. Subsequent full builds pass. Implementation and documentation remain uncommitted.


Follow-up (2026-09-18): worker execution was committed as `dc170bf`. NEM-030 operator controls
are now verified in [operator findings](admin-findings.md), including retirement of direct CLI ingestion.
