# Shared API contract verification — NEM-032

Date: 2026-09-18. Changes are uncommitted.

## Delivered

[Contract and consumer guide](../../../../api/contracts/README.md): OpenAPI 3.0.3,
document version 1.0.0, seven existing price/operator operations and generated
TypeScript declarations. Exact decimal strings, null gaps, fixed market offset,
request bounds, errors, response headers and bearer security are documented.
The backend build and CI reject contract drift and stale generated declarations.
No Java production behaviour or runtime dependency changed in this task.

## Verification

- Locked `npm ci --ignore-scripts` succeeds; installation reports zero known vulnerabilities.
- `JAVA_HOME=/usr/lib/jvm/java-25-openjdk-amd64 ./gradlew clean build --offline --no-daemon`
  passes 103 Java tests, zero failures/errors/skips.
- Swagger Parser validates the document; Ajv validates 46 actual integration-test HTTP
  responses, requiring successful evidence for all seven operations and each of the
  seven application error codes. Required cache/auth/location/retry headers are checked.
- Generated declarations pass TypeScript compilation, including exact-price and gap
  narrowing. Schema mutation checks reject numeric prices, non-null gaps, unknown
  internal fields and malformed timestamps.
- Deliberately stale generated output is rejected; restored regeneration is byte-for-byte
  identical. The verification probe restores the generated artifact.
- `python3 scripts/smoke_apps.py` passes for both packaged API and worker applications.

## Limits and next work

Tests use disposable PostgreSQL and existing fixtures, with no live OE calls or
persistent database changes. Disabled routes and input semantics remain covered by
Java tests. Not every route/status combination or framework/proxy error is validated;
403 has no exercised path in the current single-role token configuration. CI is
configured but no hosted run is claimed. Node tools are development-only.

NEM-014 is complete for price reads and refresh jobs. Refine NEM-015 for the separate
frontend foundation. Simulation and GridReplay contracts belong to their later tasks;
this does not complete M3 or implement a runtime frontend client.
