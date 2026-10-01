# Protected operator API verification

Date: 2026-09-18  
Scope: NEM-030, completing the price-refresh jobs and controls package NEM-013.

## What this proves in plain language

An operator can request a price refresh, inspect its progress and history, or cancel it.
The server checks the operator's credential before granting access. It records the configured
operator identity rather than accepting a name supplied by the caller. Repeating a request
reuses the same job, and cancelling a running job prevents the worker from saving its result.

## Verified

The Java 25 offline build passes 97 tests: the prior 88, eight operator HTTP/database tests,
and one subprocess test covering both retired CLI commands. Actual HTTP requests reach a
running Spring Boot API backed by disposable PostgreSQL 18.6. Checks cover:

- Missing/wrong credentials, Basic authentication and query-string tokens are rejected before mutation.
- Authenticated submission, status and bounded recent-job/event retrieval work.
- No session cookie, claim token, internal backfill ID or configured token appears in job responses.
- Repeated request keys and active-day deduplication reuse jobs; mismatched reuse returns 409.
- Unknown JSON fields, spoofed actor input, invalid dates/regions/IDs and missing headers return 400.
- Caller-supplied actor headers do not change the authenticated `operator:alice` audit identity.
- Running cancellation is audited, revokes the claim, and repeated cancellation records a no-op.
- Event cursors return subsequent events; unknown jobs return 404 and list limits are bounded.
- A full 100-job queue returns 429 with Retry-After.
- SQL/table failure and connection failure return a safe 503 without SQL or connection details.
- Missing/invalid token configuration fails closed; disabled controls remain unavailable.
- Direct `start`/`resume` subprocesses exit with code 2 before accessing a database or OE.

No live OE calls, real operator credentials, persistent database migrations or deployment were
performed. API health remains public and reports application startup, not provider/database readiness.
The worker implementation was committed first as `dc170bf`; this operator implementation is committed as `8d7c4b1`.

## Boundaries

This is a single configured operator credential, not a multi-user identity provider or browser
login system. Remote access requires HTTPS; credential generation/rotation is documented in the
[operator guide](../../../../reference/java/api/README.md). Optional Admin UI work remains NEM-019. Public coverage,
series resources and formal generated API/client contracts remain NEM-014. Hosted CI has not run.

Administrative mutation audit records share the queue transaction. Read requests and rejected
unauthenticated traffic are not appended to job history. Privileged direct database access is
outside the API security boundary; normal direct CLI ingestion has been retired.
