# Public navigation and shell — NEM-034

Date: 2026-09-18. Changes committed: backend records `19834eb`, frontend `e963747`.

## Delivered

The public frontend has home, BatteryLab, GridReplay and methodology routes plus a
not-found recovery page. Shared layout includes visible responsive navigation, active
page indication, page titles, keyboard focus handling, skip link and footer.
BatteryLab/GridReplay explain their planned purpose without pretending the tools work.
Methodology explains fixed UTC+10, data gaps, ordered-window comparisons and model limits.

React Router 8.4.0 and the plain-CSS styling choice are recorded in
[decision 012](../../decisions/012-public-navigation.md). Static hosting requirements
and the distinction between in-app not-found and HTTP 404 are documented in the
[frontend README](../../../../../nemlab-ui/README.md).

## Verification

From `nemlab-ui`, `npm ci --ignore-scripts` and `npm run check` pass:

- Formatting and strict application/tooling TypeScript compilation.
- Production build: JS 265.21 kB / 84.20 kB gzip, CSS 2.81 kB / 1.13 kB gzip.
- 16 Chromium checks across desktop/mobile: startup, direct load/reload of all three
  named routes, correct title and active link, keyboard-only navigation, skip link,
  heading focus, browser back/forward, unknown nested route and home recovery,
  and navigation without horizontal overflow at 320 pixels.
- Desktop BatteryLab and mobile methodology screenshots visually reviewed: readable
  content, clear active navigation and no clipping. Screenshots regenerate in ignored
  frontend test-results; they are not project source files.
- Locked install reports zero known vulnerabilities at verification.

## Limits and next task

These are production-preview checks, not a full accessibility audit or cross-browser
claim. nginx fallback is a documented example, not a tested deployment. No hosted CI,
backend/API integration or live OE calls were performed. Backend code is unchanged.
NEM-035 is next: versioned contract handoff and typed public price integration.
NEM-015 and M3 remain in progress; no simulation or replay workflow is delivered here.
