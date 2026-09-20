# 011 — Frontend repository and build baseline

Date: 2026-09-18  
Status: Accepted and locally verified for the foundation; remaining UI libraries are still proposals.

## Context

The user requested separate backend/frontend Git repositories, delegated the frontend
stack choice and authorised proceeding with the next task. NEM-015 needs a reproducible
starting point before route, API and chart integration. The sibling `nemlab-ui/` was empty.

## Decision

Use an npm workspace with one static React/TypeScript/Vite application in `apps/public/`.
Initialise its own Git repository at `nemlab-ui/.git`; keep backend history in `nemlab/.git`.
Use Node 22.23.1/npm 10.9.8, matching the existing backend contract toolchain.

| Dependency | Pinned version | Licence |
| --- | --- | --- |
| React / React DOM | 19.3.0 | MIT |
| Vite | 8.3.0 | MIT |
| Vite React plugin | 6.1.1 | MIT |
| TypeScript | 5.9.3 | Apache-2.0 |
| Prettier | 3.9.8 | MIT |
| Playwright | 1.63.0 | Apache-2.0 |
| React / React DOM types | 19.3.0 | MIT |
| Node types | 22.20.3 | MIT |

Exact direct versions and the npm lockfile define the baseline. Installed package
metadata and npm registry peer/engine constraints were checked: the React plugin
supports Vite 8, React DOM requires the selected React line, and Vite's Node requirement
is satisfied. TypeScript 5.9.3 matches the contract producer and passes strict compilation.

Prettier and EditorConfig enforce readable formatting. CI runs a locked install,
formatting/type checks, static production build and Chromium startup at desktop/mobile
widths. The development/preview servers bind to loopback with fixed, strict ports.

Reserve `apps/admin/` for a future independently built/deployed app in this repository;
do not scaffold it or shared packages until needed. No admin token belongs in the public
bundle. Shared project tracking stays in the backend; frontend instructions link there.

## Alternatives and consequences

A server-rendered React framework would add a runtime and deployment boundary before
we need it. Our Java API supplies the data and computations, so a static client is an
appropriate initial fit. [React's guidance](https://react.dev/learn/build-a-react-app-from-scratch)
explains that Vite-based apps must supply their own routing and data-fetching choices;
NEM-034/NEM-035 explicitly own those decisions. Revisit rendering if public content/SEO
requirements justify it. [Vite's guide](https://vite.dev/guide/) documents its static build
and supported Node baseline.

Use npm workspaces now to preserve the accepted future Admin boundary with little setup.
Do not add the whole proposed UI stack as unused dependencies. React Router, TanStack
Query, forms, styling, charts and tables remain pending their focused implementation
and compatibility checks. This decision accepts only the baseline portion of decision 005.

## Acceptance and evidence

Selected under the user's delegated frontend choice and “Proceed to next” instruction.
A clean install, strict checks, build and both browser checks pass. See
[foundation evidence](../evidence/frontend/foundation-findings.md) and
[frontend setup](../../../../nemlab-ui/README.md). No commit, remote, deployment or hosted
CI run is claimed.
