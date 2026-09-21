# NEM-041 — Simulation HTTP lifecycle

Date: 2026-09-21. Included with the NEM-041 implementation commit.

## Delivered

Independently enabled public submission, status and result routes reuse the existing
request boundary and durable queue. Strict JSON preserves decimal strings and rejects
unknown/duplicate fields, trailing documents, invalid types and oversized bodies.
Responses use explicit statuses, field/reason errors and safe DTOs; claim tokens, leases,
internal scenario keys and raw solver diagnostics are excluded. Only proven comparisons
return successful results. Terminal duplicate submissions never reset attempts.

OpenAPI 1.1.0 adds three operations. Existing price/operator paths and schemas were
compared structurally against HEAD and remain unchanged. Generated TypeScript declarations
are reproducible; an illustrative request and typed consumer checks document handoff.

## Verification

- Java 25 `./gradlew build --offline --no-daemon`: 150 tests, zero failures/errors/skips
  (core 57, infrastructure 43, API 24, worker 26). The nine new API cases passed in the
  focused run and remained up-to-date in the full build.
- Contract checks validate 94 actual HTTP responses across ten operations, all documented
  application error codes, required response headers and strict response schemas.
- TypeScript consumer checks and byte-for-byte regeneration pass. Request-schema mutation
  checks reject numeric decimals, ambiguous efficiency, extra actor fields and invalid windows.
- Packaged API and disabled-worker startup smoke checks pass. The smoke script explicitly
  disables the new API flag as well as both existing worker flags.
- Documentation links and diff whitespace checked. No live OE, persistent database change,
  hosted CI run or deployment occurred.

HTTP tests run real Spring Boot/PostgreSQL. They cover queued/running/successful lifecycle,
exact decimal/time preservation, fixed/hindsight manual oracle, terminal/pending duplicates,
source corrections without saved-result mutation, strict malformed/domain validation,
missing/null coverage, absent IDs, body/media limits, queue saturation and safe storage
failures on all three operations. Unproven solver diagnostics stay private and cannot be
retrieved as a successful comparison. Default-disabled routes return 404.

Computation in these HTTP tests uses the real engine and queue service; packaged subprocess
execution remains independently covered by NEM-040 tests in the full build. This is not a
new hosted or deployed end-to-end test. The first focused and final full builds passed.

## Frontend handoff and remaining scope

Commit backend contract files before syncing the frontend snapshot so provenance identifies
an actual source commit. NEM-017 must use these typed routes for forms, progress, real result
charts and reopening shared results; none of those browser journeys is implemented here.
Snapshot sync verification will be recorded after the backend commit. Final public quotas,
retention and production resource policy remain NEM-020; hosted CI remains NEM-038.
