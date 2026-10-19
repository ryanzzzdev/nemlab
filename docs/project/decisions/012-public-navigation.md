# 012 — Public navigation and shell styling

Date: 2026-09-18
Status: Accepted and locally verified under delegated frontend implementation authority.

## Decision

Use React Router 8.4.0 (MIT) in declarative mode with BrowserRouter, Routes and NavLink.
The public app has `/`, `/batterylab`, `/gridreplay`, `/methodology` and a wildcard
not-found page. Shared header/footer, page headings and introductory content use
small React components. Titles update per route, active links expose aria-current,
and client route changes move focus to the new heading. Initial loads retain normal
browser focus. A skip link targets the main content.

The npm registry and installed metadata verify React >=19.2.7 and Node >=22.22.0
requirements; the existing React 19.3.0 and pinned Node 22.23.1 satisfy them. The root
engine constraint now reflects this tighter minimum. Exact dependency and lockfile
updates accompany the implementation.

Use the existing plain CSS with shared colour variables, responsive layout and visible
focus styles for this small shell. No additional styling runtime/build dependency is
needed yet. Tailwind/shadcn from decision 005 remain candidates for richer controls,
to assess during the form implementation rather than installing unused libraries now.

## Alternatives and consequences

Browser-history routes give ordinary shareable URLs; hash routing would avoid a host
fallback but change those URLs. Framework/server rendering is unnecessary for these
static descriptions; query/data integration remains NEM-035. Navigation stays visible
and wraps on mobile, avoiding an unnecessary collapsible-menu interaction.

A static host must fall back to index.html for page routes while excluding missing
assets and API requests. Direct unknown paths display an in-app not-found page, but
SPA hosting generally returns HTTP 200. No deployment-level 404 or SEO claim is made.
The [frontend README](https://github.com/ryanzzzdev/nemlab-ui#readme) documents the required host setup.

## Evidence and scope

Selected under the user's frontend delegation and instruction to proceed. Strict build,
format checks and 16 Chromium browser cases pass; see [evidence](../evidence/frontend/navigation-findings.md).
Feature pages describe planned work and clearly state it is unavailable. No simulated
market results, data fetches, Admin entry points or operator credentials are introduced.

Primary documentation: [routing](https://reactrouter.com/start/declarative/routing),
[navigation and active links](https://reactrouter.com/start/declarative/navigating).
This accepts the router portion of decision 005; other libraries remain proposals.
