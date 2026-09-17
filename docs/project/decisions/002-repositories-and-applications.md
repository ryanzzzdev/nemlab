# 002 — Repositories and applications

Date: 2026-09-13  
Status: Accepted

## Context

NEMLab lives in its own workspace and needs a shared backend for multiple features and a separately developed frontend.

## Decision

Use one Java/Spring Boot backend repository with API and worker applications, plus one frontend repository. House an eventual Admin app in that frontend repository. The backend project folder is `nemlab`; the frontend project folder is `nemlab-ui`.

## Alternatives

A single repository would simplify coordinated changes, while separate feature services/repos would increase boundaries. The user requested one backend and one frontend repository and the API/worker split.

## Consequences and follow-up

Maintain one shared API contract and project documentation set. Scaffolding, exact shared modules and deployment mechanics remain proposals. The backend directory exists but Git and application code do not.

## Acceptance source

User’s high-level architecture request and subsequent request to create the NEMLab backend folder in the shared workspace. Recorded 2026-09-13.

## References

[Architecture](../architecture.md), [NEM-011](../backlog.md#nem-011), [NEM-015](../backlog.md#nem-015).
