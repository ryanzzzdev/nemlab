# 005 — Infrastructure and frontend stack

Date: 2026-09-13  
Status: Proposed

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
