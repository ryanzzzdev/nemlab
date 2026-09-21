# 017 — Public simulation lifecycle contract

Date: 2026-09-21
Status: Accepted and verified under delegated NEM-041 implementation authority.

Expose three independently enabled routes: POST /api/v1/simulations, GET its opaque UUID
status URL and GET its /result URL. Require application/json and at most 16384 request
bytes. Decimal inputs must be strings; no numeric coercion, unknown fields, duplicate
keys or trailing JSON documents are accepted. Core validation owns numeric/time/physical
semantics. Structured field/reason errors stay safe and do not echo arbitrary payloads.

Submission uses NEM-040 scenario identity. Pending jobs return 202 with Location and
Retry-After: 2; terminal duplicates return 200. Resubmission never resets terminal jobs.
A new source revision changes scenario identity. There is no public retry-reset or
client Idempotency-Key mechanism in this version; internal transient retries remain bounded.

Status DTOs include state, attempt count, allowlisted failure codes and relative links.
Do not expose claim tokens, leases, internal keys, raw solver states or diagnostic text.
Only successful proven comparisons have a public result (200); pending or failed runs
return distinct 409 errors. Results contain exact normalised decimal inputs/prices,
revision/version metadata, both unrounded dispatch/accounting series, units, interval
boundaries and solver objective/bound/gap. They reference the immutable saved input,
not current market data. All lifecycle responses use Cache-Control: no-store.

OpenAPI 1.1.0 is additive to 1.0.0. Generate TypeScript deterministically; actual HTTP
responses must validate against the schema. Source coverage and dates remain semantic
checks, not claims of availability. The sample request is illustrative, not a default
battery recommendation or a guarantee its day is imported.

NEMLAB_SIMULATION_API_ENABLED defaults false and is independent of both public price
reads and worker polling. Public access is stateless; operator routes retain their
bearer boundary. The bounded queue is implemented, but launch admission/rate limits,
retention and production resource policy remain NEM-020. No deployment is implied.

Verification: [HTTP findings](../evidence/engine/http-findings.md).
