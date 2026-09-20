# 005 — Infrastructure and frontend stack

Date: 2026-09-13  
Status: Partially superseded; PostgreSQL/Flyway/JDBC accepted in [decision 008](008-price-data-foundation.md), React/TypeScript/Vite foundation accepted in [decision 011](011-frontend-foundation.md). Remaining UI library choices are Proposed.

## Context

The API and worker share data and jobs, and the frontend needs forms, synchronised charts, saved scenarios, event browsing and possible Admin tables.

## Decision

Carry forward the PostgreSQL/Flyway and durable database-job design, with React/TypeScript/Vite, React Router, TanStack Query, React Hook Form/Zod, shadcn/ui/Tailwind, ECharts and TanStack Table. Use a generated API client. Exact versions and licence/compatibility checks belong to scaffolding tasks.

## Alternatives

A broker or workflow engine adds infrastructure before measured need. Server-rendered frontend frameworks remain possible if future content/SEO requirements justify them. Alternative chart libraries can be reconsidered if an ECharts interaction spike fails the required experience.

## Consequences and follow-up

Use a static frontend and Java API boundary; implement job recovery/idempotency explicitly. Keep public/Admin build boundaries inside one frontend repository. Introduce new infrastructure only for a demonstrated requirement.

## Acceptance source

Not accepted as a final technology baseline. These are recommendations from architecture planning; the frontend choice was delegated to the assistant, but compatibility and implementation proof remain outstanding.

## References

[Architecture](../architecture.md), [NEM-011](../backlog.md#nem-011)–[NEM-015](../backlog.md#nem-015).

## 2026-09-18 implementation update

NEM-033 verifies the separate frontend repository, React/TypeScript/Vite baseline,
formatting/build tooling and Chromium startup. Decision 011 supersedes only that
portion of this proposal. Routing, query caching, forms, styling, charts and tables
remain proposals for their focused implementation tasks.

## 2026-09-18 navigation update

NEM-034 accepts React Router 8.4.0 for the public routes under
[decision 012](012-public-navigation.md). The shell uses existing plain CSS; Tailwind
and shadcn remain proposals to assess when richer controls are implemented.

## 2026-09-20 price-client closeout

[Decision 013](013-typed-price-client.md) accepts the tested openapi-fetch/TanStack Query
versions and traced contract snapshot workflow for NEM-035. Charts and richer form/UI
libraries remain subject to their focused implementation checks.

## 2026-09-20 chart proof update

[Decision 014](014-linked-chart-prototype.md) accepts Apache ECharts 6.1.0 for the bounded
288-interval linked-chart slice after browser and real-API checks. Its on-demand bundle
cost and local render observations are recorded; larger/product workloads need later checks.
