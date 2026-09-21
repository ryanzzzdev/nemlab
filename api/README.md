# API: stored-price reads and protected operator controls

The API exposes public startup health at `/actuator/health`. Operator controls are disabled
by default and return 404 in that mode. Enabling them requires a migrated PostgreSQL database
and an explicit operator credential. The API never fetches OE data itself and does not need an OE key.

## Public stored-price reads

Set `NEMLAB_DATA_ENABLED=true` (Spring property `nemlab.data.enabled`) to expose stored price
reads. Export database settings and migrate explicitly first. This flag is independent of
`NEMLAB_ADMIN_ENABLED`; public reads require neither an operator token nor an OE key.
Both enabled features share one datasource. With both disabled, the API starts without database
credentials. No public read request submits jobs, fetches OE data or writes to storage.

```sh
export NEMLAB_DATA_ENABLED=true
"$JAVA_HOME/bin/java" -jar api/build/libs/api.jar
```

The following GET endpoints are anonymous when enabled:

| Path | Behaviour |
| --- | --- |
| `/api/v1/prices/{region}/coverage?start=YYYY-MM-DD&endExclusive=YYYY-MM-DD` | Every day in a range of 1–31 completed market days, including days never imported. |
| `/api/v1/prices/{region}/{day}` | Current stored revision for one completed market day, with exactly 288 interval entries. |

Dates use fixed UTC+10 NEM time, on/after 2021-10-01. Regions are NSW1, QLD1, SA1, TAS1, VIC1.
Ranges include `start` and exclude `endExclusive`; the current unfinished market day is rejected.
A supported region is not a promise that prices for it have been imported or validated broadly.

Coverage returns `region`, `start`, `endExclusive`, `marketOffset`, and `days`. Each day has:

- `day` and `availability`: `NOT_IMPORTED`, `COMPLETE`, or `INCOMPLETE`.
- `revision` and `retrievedAt`: current immutable revision ID and last accepted retrieval time.
- `valid`, `missing`, and `sourceNull`: interval counts for an imported day.

For `NOT_IMPORTED`, revision, retrieval time and counts are null. This distinguishes no stored
response from a response containing missing observations. A complete day has 288 valid prices.
The range is read in one database query; each day's revision and counts come from the same row.

A day series returns `region`, `day`, `source` (`Open Electricity`), `unit` (`AUD/MWh`),
`intervalSeconds` (300), `intervalLabel` (`END`), `marketOffset` (`+10:00`), `coverage`, and
`intervals`. Every interval contains UTC ISO `start` and `end` instants, a `state` (`VALUE`,
`MISSING`, `SOURCE_NULL`), and `price`. Valid prices are **decimal strings**, preserving exact
stored precision, negatives and zero. Both gap states have null prices; gaps are never filled.
Incomplete days return 200 with these explicit states; simulation eligibility still requires
complete coverage. The `retrievedAt` value describes the accepted data, not worker liveness.

Unimported series return 404 with `PRICE_DAY_NOT_IMPORTED`; coverage itself returns 200 with
`NOT_IMPORTED` rows. Invalid region/date/range/required parameters return 400 `INVALID_REQUEST`;
storage failures return 503 `STORAGE_UNAVAILABLE`. Errors have `code` and `message`, with no SQL
or credentials. Non-GET access does not expose mutations. Disabled routes return 404.

Current reads use `Cache-Control: no-store` because later corrections can advance the revision.
A response captures one immutable revision before loading its intervals, so a concurrent refresh
cannot mix old coverage with new prices. Historical revision/snapshot retrieval is not part of
these endpoints; saved simulation input access remains NEM-016. Formal OpenAPI and generated
client inputs are NEM-032. See [verification](../docs/project/evidence/data-foundation/read-api-findings.md).

## Enable operator controls locally

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
shared OpenAPI/client contract remains NEM-032 within NEM-014; simulation and GridReplay resources remain later feature work.

## Machine-readable contract

The versioned [OpenAPI contract and generated frontend types](contracts/README.md)
cover these seven price-read and operator operations. `:api:checkContract` checks the
specification, generated types and actual HTTP integration-test responses. Install
its locked Node tooling before running the backend build. Runtime applications do
not depend on Node or serve the specification automatically.


## Public simulation lifecycle

Set `NEMLAB_SIMULATION_API_ENABLED=true` and database settings after applying migrations
through V3. This feature is independent of `NEMLAB_DATA_ENABLED`, operator controls and
`NEMLAB_SIMULATION_ENABLED` on the worker. An enabled API can enqueue work while the worker
is offline; jobs stay queued until polling resumes. The feature defaults off.

| Request | Behaviour |
| --- | --- |
| `POST /api/v1/simulations` | Accept JSON scenario; 202 for pending work, 200 for an existing terminal job. Location points to status; pending responses include Retry-After: 2. |
| `GET /api/v1/simulations/{id}` | Read state, attempt count, safe failure code and relative status/result links. |
| `GET /api/v1/simulations/{id}/result` | Read saved proven comparison, original exact inputs/prices, revision/version metadata, both dispatch/accounting series and explicit units. |

Use the [illustrative JSON request](contracts/examples/simulation-request.json):

```sh
curl -i -H 'Content-Type: application/json' \
  --data-binary @api/contracts/examples/simulation-request.json \
  http://127.0.0.1:8080/api/v1/simulations
```

This fixture is an example, not a configured site preset or a promise that its day has been
imported. The selected completed day must already have complete stored prices. Submission
never fetches OE. See the [request contract](../docs/project/features/simulation-request-contract.md)
for physical limits and fixed UTC+10 windows. Decimal quantities must be JSON strings;
window minutes must be integers. Bodies are limited to 16384 bytes. Unknown/duplicate
fields, trailing JSON, numeric coercion and ambiguous efficiency choices are rejected.

Errors include field/reason details for 400 invalid requests, 409 unavailable/incomplete
prices, 404 unknown simulations, 409 RESULT_NOT_READY or SIMULATION_FAILED, 413 oversized
bodies, 415 unsupported content, 429 queue capacity (Retry-After: 5), and safe 503 storage
failure. All lifecycle responses use Cache-Control: no-store. Claim tokens, leases,
internal scenario keys and raw solver diagnostic text are excluded from public DTOs.

Identical normalised inputs and the same captured price revision reuse the job across all
states. No Idempotency-Key is needed; resubmitting a terminal failure does not reset its
attempts. Source corrections create a distinct scenario while old results retain their
original prices. Internal transient retries are bounded; there is no public retry-reset
or cancellation endpoint yet. A feasible-but-unproven solver result remains a failed job
and cannot be fetched as a successful comparison.

Only the input/price decimals are exact strings. Dispatch and accounting are unrounded
engine doubles, annotated with MW, MWh, AUD and AUD/MWh units; formatting belongs to the
frontend. Saved comparison links use opaque UUIDs. Retention, public rate limits and
production deployment remain launch work. The [OpenAPI 1.1 contract](contracts/openapi.json)
and generated types define the transport schema.
