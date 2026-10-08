# M6 desktop redesign acceptance review — 2026-10-09

Final NEM-115 evidence against [the redesign acceptance criteria](../../features/admin-desktop-redesign.md#implementation-strategy-and-acceptance). Review run on the real stack (API :8080, PostgreSQL, admin dev server :5274) with seeded owner and viewer sessions. Screenshots in `m6-review/`; before-state baseline in `before-*.png`.

## Viewport / theme / density matrix

| Check | Result |
|---|---|
| 1440×900 standard density, coverage rows with inspector + activity open | 31 rows (target ≥10) — `01-*.png` |
| Compact density | 28px row height — `02-*-compact.png` |
| Comfortable density | 40px row height — `02-*-comfortable.png` |
| Dark theme | applies — `03-*.png` (light/auto exercised across the set) |
| 1280×720 | rail collapsed to 48px, zero horizontal overflow — `04-1280x720-*.png` |
| 1920×1080 | rail 176px, width used for columns/detail, zero overflow — `04-1920x1080-*.png` |
| 720px effective (≈200% zoom) | zero horizontal overflow — `05-*.png` |
| Console/page errors across all passes | none |

## Journeys with real data

- **Coverage → inspector**: row click selects `?sel=day:…`; day inspector shows exact series validity and ramp-baseline readiness — `01-*.png`.
- **Keyboard**: ArrowDown + Enter on the grid selects a row (`sel=day:2026-10-06`); Escape closes drawers — `06-*.png`.
- **In-place job inspection**: Loads & Jobs row opens the operation inspector (phase, next day, chunks, dispatch controls) without leaving the workspace — `07-*.png`.
- **Load drawer**: scope review renders real coverage truthfully; Escape closes with focus return — `08-*.png`. End-to-end load creation was verified in NEM-112.
- **Publish drawer**: coverage check runs against the scoped window and gates on gap acknowledgement — `09-*.png`. Explicit-v2 publish was verified in NEM-112 and the NEM-114 suite.
- **Access**: pending request approved from the table inspector — grant created, delivery audit shows the queued sign-in mail honestly (`pending`, mail drain off) — `14/15-*.png`; the fresh grant then revoked through the two-step reasoned flow — `16/17-*.png`. Audit tab renders real rows — `12-*.png`.
- **Viewer session**: `viewer · read-only` badge, zero owner action buttons, Access rail item absent, day inspector shows "owner action" copy, `/access` shows the owner-only fallback — `18/19-*.png`.

## Preservation reconciliation

Preserved through the rebuild (evidence per NEM-111–114 journals and the 19-test `tests-admin/` suite): bounded ≤31-day coverage/publication scopes; attempt-key reconciliation; no second dispatcher across panes; sort/filter labelled within loaded results; IDs-only URL state (no PII); server-authoritative owner/viewer separation with viewer redaction; recent-auth, conflict, resend and delivery-failure surfaces; single-use token lifecycle; draft persistence; no bulk operations.

## Verdict

All redesign acceptance criteria pass on real data. M6 desktop UI redesign accepted; deployment/hosted-CI/real-SMTP/TLS remain M7 launch gates, explicitly unverified here.
