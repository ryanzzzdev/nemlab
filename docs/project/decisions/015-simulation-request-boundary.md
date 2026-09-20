# 015 — Exact simulation inputs and revision-bound identity

Date: 2026-09-20
Status: Accepted under delegated implementation authority for NEM-039.

## Decision

Keep request normalisation in the plain Java core and stored-price resolution in
infrastructure. The [request contract](../features/simulation-request-contract.md)
defines fields, numeric admission bounds, errors and canonical identity. Reuse the
existing Battery, Efficiency, ScheduleWindows and TradingCosts constructors.

Preserve normalised BigDecimal physical/cost inputs and derived efficiency legs, while
using the existing double-based engine for execution. Validate exact energy ordering
before conversion. Keep numeric ceilings explicit and distinct from proof tolerances:
an admitted request may still yield a non-optimal solver status and must be handled
honestly by later execution/result code.

Capture the current price revision once. Read and carry that immutable revision with
the prepared parameters; do not fetch OE, queue refresh work or create a snapshot row
during validation. NEM-040 will persist the revision linkage and parameters with job
submission in a transaction, avoiding snapshots orphaned by validation or duplicate work.

Hash a fixed-order versioned representation with all result-affecting inputs and version
identifiers, including solver limits. Decimal trailing zeros and efficiency input form do
not change identity after normalisation. Different price revisions do. Identity is local
to the repository's stored revision IDs, not a portable cross-database result identifier.

## Alternatives and consequences

Hashing request JSON would make keys sensitive to field order and formatting. Hashing
only doubles would discard input provenance. Creating a snapshot during preparation
would add writes before deduplication/job submission can commit atomically. None is needed.

HTTP parsing/status mapping, durable jobs, process bounds, stored results and generated
API extensions remain NEM-040/NEM-041. No new public endpoint is enabled by this change.
Launch admission policy may tighten these local bounds under an explicitly versioned
contract; they are not recommendations for battery sizing or guarantees of solver proof.

## Sequence

The user directed work to proceed after the M3 review reported the hosted CI gap.
NEM-039 therefore proceeds against locally verified dependencies while NEM-038 remains
blocked on authorised remote publication. M3 stays open; local M4 work can progress.

## Verification

See [request-boundary findings](../evidence/engine/request-findings.md).
