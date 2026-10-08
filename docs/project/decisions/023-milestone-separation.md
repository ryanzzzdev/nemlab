# 023 — Separate GridReplay, Admin and launch milestones

Date: 2026-10-08. Status: Accepted for milestone sequencing at the user's request. Admin UI scope remains undecided.

## Context and decision

The user requested a fresh M5 review and asked to discuss Admin separately after GridReplay. Use M5 for GridReplay, M6 for Admin, and M7 for launch readiness and release. The [state review](../evidence/m5-state-review-2026-10-08.md) supports local feature completion with explicitly retained verification exceptions; it does not certify launch readiness.

Reconcile stale NEM-018/NEM-059/NEM-064 records with delivered evidence. Track reduced-motion, chart-failure and maximum-window evidence as open NEM-094 launch work rather than representing them as passed. This makes the local feature completion boundary explicit; the earlier broader verification wording is not retrospectively satisfied.

## Consequences

- NEM-093 scopes the Admin experience next. NEM-082 and NEM-092 belong to M6. Creating a milestone does not authorize an assumed UI/authentication design or establish that Admin is delivered.
- NEM-020 becomes M7; hosted CI NEM-038 and all other release gates remain open where recorded.
- Decision 021 remains evidence of the M5 operator rehearsal and UI deferral. Its blanket release deferral is superseded by a dedicated M6 scope discussion; no decision to build a particular Admin UI is implied.
- Keeping Admin bundled with M5 would obscure completed GridReplay delivery; marking the whole project release-ready would conceal known verification and operational work. Separate milestones preserve both distinctions.

See the [roadmap](../roadmap.md), [Admin specification](../features/admin.md), and [backlog](../backlog.md).
