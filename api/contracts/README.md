# Shared API contract

`openapi.json` is the canonical OpenAPI 3.0.3 contract, initially version 1.0.0.
It covers two public price GET operations and five authenticated operator operations.
`generated/schema.d.ts` is the checked-in TypeScript input for the future frontend.
It has no runtime code, credentials or network behaviour. No frontend repository or
runtime client is created by this task.

## Install, regenerate and verify

Use Node.js 22.23.1 and npm 10.9.8 (CI pins Node); Java 25 and Docker are required
for the HTTP/PostgreSQL tests. From the backend root:

```sh
npm ci --ignore-scripts --prefix api/contracts
npm run generate --prefix api/contracts
./gradlew :api:checkContract
```

The ordinary `./gradlew build` also runs this check. Once dependencies are installed,
`./gradlew build --offline` needs no network or OE account. Generation never runs
implicitly during verification: stale checked-in output fails `--check`.

- Edit `openapi.json` together with the Java API, regenerate, then review both diffs.
- `package-lock.json` pins the entire tool tree; use `npm ci`, not floating installs.
- `examples/typecheck.ts` verifies price-string and gap-null narrowing and operation types.
- `verify.mjs` validates the OpenAPI document with Swagger Parser and actual HTTP test
  responses with Ajv, including required response headers. It requires successful
  evidence for all seven operations and evidence for every application error code.
- Response captures are disposable `api/build/contract-responses/` test outputs.
  Gradle clears them when tests execute. Request credentials, bodies and query strings
  are never recorded. IDE-only tests do not write captures unless configured explicitly.

The checks do not prove every possible HTTP/proxy failure or every combination of
route and status. In particular, framework-level malformed protocol requests and
403 are not exercised by these captures; this authentication model grants the one
operator role to valid tokens. Existing Java tests also check disabled routes,
input bounds, read-only behaviour, idempotency and cancellation semantics.

## Consumer rules

- Feature flags are independently opt-in. The document describes enabled surfaces;
  disabled routes return 404 and do not promise the application error body.
- Public GETs require no credentials. Operator bearer tokens belong only in trusted
  operator tooling. Importing generated admin types is not permission to expose an
  operator token in a public browser bundle. A future Admin requires its own access design.
- Dates use fixed NEM UTC+10, including daylight-saving periods. Instants are ISO timestamps.
- Prices are exact decimal **strings** in AUD/MWh. Convert explicitly only for display
  or charts. Missing and source-null intervals have null prices; neither means zero.
- NOT_IMPORTED coverage has null revision, timestamp and counts. Imported counts total
  288; COMPLETE means all 288 values exist. Series responses always contain 288 intervals.
- `Idempotency-Key` permanently binds to one region/day/job. Reuse it for submission
  retries; a conflicting payload returns 409. A full queue returns 429 and Retry-After 30.
- Event IDs/cursors are int64; generated TypeScript represents them as numbers. Consumers
  must reject values beyond `Number.MAX_SAFE_INTEGER` rather than silently round cursors.
- Handle transport errors and non-JSON responses before selecting a documented JSON type.
  Types are compile-time declarations, not runtime validation or an HTTP client.

## Compatibility

`info.version` versions the document/artifact; `/v1/` versions the wire interface.
Patch releases clarify documentation without changing behaviour. Minor releases add
compatible optional fields or operations. Removing/renaming fields, making optional
inputs required, changing units/types/nullability, or extending closed enums requires
an explicit compatibility review and a major contract version; incompatible wire
behaviour belongs on a new route version. Preserve existing operation IDs.

Schemas reject unexpected fields in producer tests to catch accidental data leakage.
An intentional additive response field therefore requires updating the contract and
regenerated types together; consumers should tolerate unknown response fields.
Copy the contract and generated declarations together at a recorded backend commit
when NEM-015 integrates the separate frontend; do not maintain a second hand-written
contract. Distribution as a package can be decided when that repository exists.

## Tooling and licences

Pinned development-only tools: openapi-typescript 7.13.0 (MIT), Swagger Parser 13.0.0
(MIT), Ajv 8.20.0 (MIT), ajv-formats 3.0.1 (MIT), TypeScript 5.9.3 (Apache-2.0).
No dependency is added to the Java runtime. OpenAPI 3.0.3 keeps validation and generated
inputs on the same supported dialect; Ajv natively supports its nullable keyword.

References: [generation and --check](https://openapi-ts.dev/cli),
[Swagger Parser](https://apidevtools.com/swagger-parser/),
[Ajv JSON Schema and nullable](https://ajv.js.org/json-schema).
