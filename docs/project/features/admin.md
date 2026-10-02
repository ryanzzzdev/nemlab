# Admin

Updated: 2026-09-25

Status: Conditional feature; the UI is not committed to initial launch.

## Purpose and boundary

Help the operator inspect data and jobs, request bounded OE refreshes, retry failed work, and audit administrative actions. Admin would be a separate app inside the frontend repository, sharing components and the API client. The existing API application serves protected administrator endpoints; no additional backend service is planned.

## Required operations before launch

- Inspect coverage, freshness, failed ingestion and job progress.
- Request a refresh/backfill for a specified region/metric/window and see its job ID.
- Retry eligible failed work safely and see the attempt history.
- Inspect validation failures and resource/queue limits.
- Authenticate the operator and record who requested which operation.

These operations must exist through authenticated endpoints or documented operator commands even when the UI is deferred. Raw database editing is not the normal correction path: reingest or use a validated, auditable operation.

## Optional first UI

Coverage table, job list/detail, refresh form, retry action, and audit list. Forms show exact scope before submitting work and enforce the same bounds as the backend. Distinguish queued requests from completed data changes. Do not offer arbitrary SQL, credential display, unrestricted historical refreshes, or generic table CRUD.

Use the same durable job mechanism for schedules, commands and UI requests. Backend authorisation, safe retry semantics, and deduplication are mandatory regardless of frontend controls. Determine identity/session handling and any CSRF protections from the chosen authentication mechanism.

## Decision gate and acceptance

At M5, exercise the operator workflow through the available endpoints/commands. Include the UI if it materially improves coverage inspection and recovery within the release scope; otherwise document the tested alternative and defer the app.

If included, unauthorised requests fail server-side, refresh/retry produces one logical operation, progress and errors are inspectable, and actor/scope/result can be traced. If deferred, equivalent critical operations pass a documented operator rehearsal before M6 completes.

See [NEM-019](../backlog.md#nem-019), [BLK-006](../blockers.md#blk-006), and [architecture](../architecture.md).


## Implemented operator API — NEM-030

The opt-in [operator API](../../../reference/java/api/README.md) now supports authenticated one-day price refreshes,
bounded recent-job and audit-event lists, status and idempotent cancellation. Audit identity is
server-derived from one configured operator token; browser login and multiple operator accounts
remain outside this slice. Direct CLI execution is retired. Coverage inspection remains available
through read-only commands until NEM-014. The optional Admin frontend decision is unchanged.


## M5 assessment plan — 2026-09-25

Recommendation: deliver GridReplay and prove the protected operator workflow before building a second frontend. This is not a final decision to include or defer Admin. [NEM-063](../backlog.md#nem-063) owns the rehearsal and decision evidence; NEM-019 remains the parent package.

The current price-refresh controller supports submit, recent jobs, job status, audit events and cancellation. It does **not** expose a dedicated manual retry endpoint. Existing automatic retries and submitting another operation are not interchangeable; the rehearsal must verify an explicit safe recovery procedure. Grid imports, event detection and catalogue publication still need operator surfaces in NEM-056/NEM-058.

Rehearse: inspect metric/day coverage → request a bounded import → follow job progress → inspect a failure → recover safely → detect/publish events → check the public replay → refresh corrected input → confirm old links still reproduce their original evidence. Record the authenticated actor, exact requested scope and resulting operation IDs. Exercise unauthorized calls, deduplication, cancellation/restart and failure diagnostics without exposing credentials. No raw database edits as the routine workaround.

If this remains comfortable through documented commands/endpoints for a single operator, recommend deferring the UI and keeping that tested runbook. If repeated inspection/recovery proves awkward, propose a minimal separate `apps/admin`: coverage, jobs/detail, bounded refresh, eligible recovery action and audit list. Add authentication/session/CSRF requirements appropriate to the selected mechanism before any browser implementation; the current server token must never be embedded in the public application or a Vite bundle. No account-management suite, arbitrary SQL or generic CRUD console.

Record the include/defer decision explicitly after the rehearsal. If included, split it into focused tasks and make their completion part of M5 acceptance; if deferred, the tested operator alternative is the deliverable. Hosting, retention and final launch identity policy remain M6/BLK-006 work.

## M5 decision — 2026-10-02

**Deferred.** [Decision 021](../decisions/021-admin-ui-deferred.md) records the outcome of the NEM-063 rehearsal: the operator API was exercised end-to-end on the live stack (imports, dedupe, cancel, crash recovery, publication, link preservation) and is the documented operational path. Revisit triggers and the grid-coverage gap (NEM-082) are listed there.
