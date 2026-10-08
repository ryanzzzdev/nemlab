# 025 — Desktop-first enterprise Admin workspace

Date: 2026-10-08. Status: Accepted; implementation pending.

Acceptance source: user rejected the delivered public-style Admin UI, requested a full-screen desktop enterprise/CMS/CRM direction with higher information density and fewer pages, then explicitly requested a complete redesign plan.

Replace the public stylesheet/page-shell dependency with an independent Admin visual system. Consolidate operational pages into Data Operations with shared scope, table/matrix, inspector and activity pane; keep Access as a separate owner workspace. Help becomes contextual; authentication retains focused routes. Use desktop geometry/density, explicit table semantics and keyboard accessibility; mobile parity is not a redesign goal.

Preserve delivered backend/security/workflow semantics. This supersedes decision 024's centred public-style presentation and multi-page navigation, not its account or permission design. See [redesign specification](../features/admin-desktop-redesign.md) and [NEM-108–115](../backlog.md#nem-108).

A cosmetic CSS widening would retain fragmented work. A new backend or large CRM framework is unnecessary. Full-screen here means viewport-filling application layout, not the browser Fullscreen API. M6 reopens for this scope while prior completed tasks retain their evidence; M7 remains launch.
