# Frontend foundation — NEM-033

Date: 2026-09-18. Backend records committed as `19834eb`; frontend committed as `e963747`.

## Delivered

The separate `nemlab-ui/.git` repository contains an npm workspace with `apps/public`,
a React/TypeScript/Vite static application, pinned tooling and lockfile, Prettier,
EditorConfig, browser startup checks and a GitHub Actions workflow. Canonical project
records remain in the backend and are linked from frontend README/AGENTS instructions.
The initial landing page honestly labels BatteryLab/GridReplay as coming soon.

No empty Admin app, copied API models, operator credentials or product simulations
are included. Future Admin remains a separately built app within the frontend repo.

## Verification

Run from `nemlab-ui` with Node 22.23.1 and npm 10.9.8:

```sh
npm ci --ignore-scripts
npx --no-install playwright install chromium
npm run check
```

- Clean locked installation succeeds; npm reports zero known vulnerabilities at verification.
- Prettier passes for all checked files; both application and tooling TypeScript compile strictly.
- Production Vite build succeeds: JS 221.01 kB / 69.09 kB gzip and CSS 1.33 kB / 0.64 kB gzip.
  These are initial emitted sizes, not a load-performance claim or a product budget.
- Two Playwright cases pass against the production preview: desktop and mobile Chromium.
  They verify a successful page response, rendered headings/title, no browser errors and
  no horizontal overflow. Screenshots were visually inspected at both widths; text is
  readable, mobile cards stack and no clipping was observed.
- Frontend and backend `git rev-parse --show-toplevel` return their separate sibling roots.
  Frontend has no commits or remotes. Dependencies, build output and browser artifacts are ignored.
- Direct dependency licences and engine/peer compatibility were verified; see
  [decision 011](../../decisions/011-frontend-foundation.md).

Screenshots regenerate under ignored frontend `test-results/`. Playwright manages and
stops its preview process. CI is configured but has not run on a hosted service.
Backend Java code is unchanged in this task; backend tests were not rerun.

## Remaining scope

NEM-034 adds navigation and a reusable public shell. NEM-035 adds the typed real API
slice and contract provenance/drift checks. NEM-036 verifies linked chart behaviour.
NEM-015 and M3 remain in progress. This task is not a launch-ready frontend, an API
integration, a full accessibility audit or cross-browser compatibility verification.
