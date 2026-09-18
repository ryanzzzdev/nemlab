# API and protected operator controls

The API exposes public startup health at `/actuator/health`. Operator controls are disabled
by default and return 404 in that mode. Enabling them requires a migrated PostgreSQL database
and an explicit operator credential. The API never fetches OE data itself and does not need an OE key.

## Enable locally

Export `NEMLAB_DB_URL`, `NEMLAB_DB_USER` and `NEMLAB_DB_PASSWORD` for the migrated database.
Choose an operator identifier and generate a separate random token. Do not reuse the OE API key.
The following shell command sets a token without printing it:

```sh
export NEMLAB_ADMIN_OPERATOR=local-operator
export NEMLAB_ADMIN_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export NEMLAB_ADMIN_ENABLED=true
./gradlew :api:bootJar
"$JAVA_HOME/bin/java" -jar api/build/libs/api.jar
```

Keep the same token securely for subsequent requests; rotating it and restarting the API revokes
the old token. Tokens must contain 43–128 base64url characters. Operator identifiers allow
letters/digits, dots, underscores and hyphens, up to 64 characters. Blank/invalid configuration
fails startup when enabled. API and worker startup check the database but do not migrate it.

The default bind address is `127.0.0.1`. Use HTTPS through the deployment ingress when accessing
these endpoints remotely. This is a single configured operator credential for initial operation,
not multi-user identity management. Do not share it across people if individual attribution is needed.
Browser login, role administration and the optional Admin UI remain later work.

## Make requests

Use `Authorization: Bearer <token>` on each request. HTTP Basic, query-string tokens and cookies
do not authenticate. No session is created. Actor fields/headers cannot override the server-derived
`operator:<configured identifier>` audit identity. Keep the token out of URLs, command arguments,
source control and frontend bundles.

In a separate terminal with the same token exported, this helper passes the header through stdin:

```sh
admin_curl() {
    printf 'header = "Authorization: Bearer %s"\n' "$NEMLAB_ADMIN_TOKEN" |
        curl --fail-with-body --config - "$@"
}

admin_curl -X POST http://127.0.0.1:8080/api/admin/v1/price-refreshes \
    -H 'Content-Type: application/json' \
    -H 'Idempotency-Key: local-refresh-2023-09-11' \
    -d '{"region":"NSW1","day":"2023-09-11"}'

admin_curl 'http://127.0.0.1:8080/api/admin/v1/price-refreshes?limit=20'
admin_curl 'http://127.0.0.1:8080/api/admin/v1/price-refreshes/<job-id>'
admin_curl 'http://127.0.0.1:8080/api/admin/v1/price-refreshes/<job-id>/events?after=0&limit=50'
admin_curl -X POST 'http://127.0.0.1:8080/api/admin/v1/price-refreshes/<job-id>/cancel'
```

Start the [worker](../worker/README.md) to execute queued jobs. Submission itself performs no
OE call. Manually submitted and scheduled jobs use the same durable submission/claim path.
The former direct ingestion CLI `start` and `resume` commands now exit with code 2 before
reading credentials or contacting a database/provider. Migration, legacy checkpoint inspection,
coverage and price history commands remain available.

## Contract

Base path: `/api/admin/v1/price-refreshes`.

| Method/path | Input | Result |
| --- | --- | --- |
| POST base | JSON `region`, `day`; required `Idempotency-Key` | 202, `Location`, current job view. |
| GET base | `limit` 1–100, default 50 | Most recent jobs first; bounded operational view, not a full archive. |
| GET `/{id}` | UUID | Current job view, or 404. |
| GET `/{id}/events` | `after` nonnegative event ID, `limit` 1–100 | Audit events in ascending ID order; use the final ID as the next cursor. |
| POST `/{id}/cancel` | UUID | Current job view; repeated/terminal cancellation is a no-op, recorded as `CANCEL_NOOP`. |

One submission covers one completed market day, interpreted in fixed UTC+10, on/after
2021-10-01. Allowed regions are NSW1, QLD1, SA1, TAS1, VIC1. Unknown JSON fields, invalid dates,
missing fields, malformed identifiers and invalid list bounds return 400. For a date range,
submit each day separately within the queue's 100-pending-job limit.

Idempotency keys are 1–120 characters, starting with a letter/digit and then allowing letters,
digits, underscore, dot, colon, slash and hyphen. A key permanently identifies its original
region/day and job. Reusing it for different input returns 409. New keys deduplicate against
an active job for the same day. To refresh a completed, failed or cancelled day again, use a
new key. A repeated submission can return an already completed job; inspect its status.

Job views contain `id`, `region`, `day`, `status`, `attempts`, `availableAt`, and `diagnostic`.
Timestamps are UTC ISO instants. Claim tokens, leases, internal backfill IDs and credentials
are not exposed. Events contain `id`, `occurredAt`, `actor`, `action`, and `diagnostic`.
Mutation audit entries commit with the operation; read requests are not appended to job history.
Unknown job IDs return 404. Cancellation revokes a running claim's permission to save results;
it does not promise immediate termination of an already running provider request.

| Status | Code / meaning |
| --- | --- |
| 400 | `INVALID_REQUEST` |
| 401 | `UNAUTHORISED`; bearer authentication required |
| 403 | Authenticated caller lacks operator authority |
| 404 | `JOB_NOT_FOUND`, or unavailable route when disabled |
| 409 | `IDEMPOTENCY_CONFLICT` |
| 429 | `QUEUE_FULL`, with `Retry-After: 30` |
| 503 | `STORAGE_UNAVAILABLE`; no SQL/credentials in response |

Successful authentication does not make a failed queue operation successful. Storage failures
roll back through the existing transaction boundaries. Public health remains a startup/liveness
check, not a live database/provider readiness guarantee.

## Security design and verification

Spring Security handles bearer extraction and authentication with a local opaque-token
introspector. Only a SHA-256 digest is retained by the verifier and comparison uses
`MessageDigest.isEqual`. Token entropy comes from secure generation, not from hashing.
CSRF is disabled for this stateless header-only API; no form login, Basic login or session
cookie is configured. No external identity/introspection service is contacted.
See the [Spring Security reference](https://docs.spring.io/spring-security/reference/servlet/oauth2/resource-server/opaque-token.html).

The implementation is verified by real HTTP requests against a running API and disposable
PostgreSQL. See [operator evidence](../docs/project/evidence/jobs/admin-findings.md). A formal
shared OpenAPI/client contract, coverage endpoints and public product APIs remain NEM-014.
