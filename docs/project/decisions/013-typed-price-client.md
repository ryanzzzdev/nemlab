# 013 — Typed public price client and contract handoff

Date: 2026-09-20
Status: Accepted under delegated frontend implementation authority.

## Decision

Import the backend OpenAPI document and generated declarations together into frontend
`contracts/`, recording the source Git commit, contract version and SHA-256 hashes in
`provenance.json`. Sync requires committed backend contract files. Verification checks
snapshot hashes and compares with the sibling backend when available. Isolated frontend
CI explicitly checks only its snapshot; `--backend` requires a coordinated comparison.
The backend remains the contract author; frontend snapshots are derived build inputs.

Use openapi-fetch 0.16.0 (MIT) and TanStack Query 5.103.1 (MIT). The tested client exposes
only the two public price GET operations, rejects other paths/methods/origins, strips
caller headers, omits credentials/cookies and rejects redirects. The full declaration
snapshot includes operator types but no runtime operator client or secrets are bundled.
The newer openapi-fetch 0.17.0 was evaluated and rejected because its helper types dropped
required null-only fields from responses; 0.16.0 preserves the generated gap-price types.

Query keys include region/day. Cache entries expire after five inactive minutes and are
immediately stale; window-focus refetch and automatic retries are disabled. Explicit
rechecks refresh the selected day. The client bounds each request to 15 seconds and
hides prior results while loading or after failure. Critical display fields have runtime
guards; this is not a complete client-side OpenAPI validator.

The browser requests same-origin URLs. Vite's development and preview proxy forwards
only public price paths to the configured API target. Production requires equivalent
reverse-proxy routing and must not return the SPA HTML for API errors. No CORS broadening
or operator authentication is needed for these public reads.

## Data semantics and alternatives

Display exact decimal strings, explicit missing/source-null states and fixed UTC+10
interval times. Request coverage first and fetch a day only if imported. Series metadata
is authoritative if a correction advances the revision between those requests.

A published schema package would add release infrastructure before it is needed. Traced
snapshots let the frontend build independently while retaining reviewable provenance.
Handwritten API models would duplicate the backend contract; they are not introduced.

## Evidence and references

See [price integration findings](../evidence/frontend/price-integration-findings.md) and
[frontend setup](../../../../nemlab-ui/README.md). No frontend/backend commit or deployment
is implied. Runtime client/query choices implement their portion of decision 005;
charts, forms and richer component libraries retain their later acceptance tasks.

Primary references: [openapi-fetch](https://openapi-ts.dev/openapi-fetch/),
[TanStack Query defaults](https://tanstack.com/query/latest/docs/framework/react/guides/important-defaults).
