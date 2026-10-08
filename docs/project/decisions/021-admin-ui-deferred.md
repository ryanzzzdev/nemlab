# 021 — Admin UI deferred for M5

Date: 2026-10-02. Status: Partially superseded by [decision 023](023-milestone-separation.md) on 2026-10-08: the M5 deferral/rehearsal remains historical evidence; release-wide UI deferral is reopened for M6 scope discussion. Task: [NEM-063](../backlog.md#nem-063). Evidence:
[operator rehearsal](../evidence/m5-ops-rehearsal.md).

## Decision

**Defer the Admin UI.** A second frontend application is not built for
this release. The tested operator alternative — the authenticated
`/api/admin/v1/*` endpoints driven by documented commands — is the
deliverable.

## Evidence

The live rehearsal exercised every required operator operation through
endpoints alone: bounded grid imports (submit, dedupe, cancel, per-day
audit), failure classes (immediate permanent failure vs bounded retry),
crash recovery via lease expiry and checkpointed resume, detection +
catalogue publication, and old-link preservation across republication.
See the rehearsal table for commands and observed results.

## Rationale

- One operator, infrequent bounded operations; the REST surface is
  complete and auditable, so a UI adds an authentication/session/CSRF
  surface without proportional benefit.
- Keeping the public bundle free of operator credentials stays trivial:
  there is nothing to embed.
- The mandatory properties (server-side authorisation, safe retry
  semantics, deduplication, actor audit) already hold in the API.

## Revisit triggers

- Multiple operators or delegated access (needs identity/accounts).
- Repeated manual recovery proves error-prone (needs the coverage
  endpoint NEM-082 and possibly an in-place retry action).
- Pre-launch hardening under NEM-020 wants an operator console.
