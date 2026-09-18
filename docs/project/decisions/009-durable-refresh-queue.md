# 009 — Durable price-refresh queue

Date: 2026-09-18  
Status: Accepted under the user's delegated implementation authority (“proceed to next task”).

## Context

NEM-013 is a planning package, split into queue persistence (NEM-028), worker execution
(NEM-029) and protected operator controls (NEM-030). Existing price storage uses explicit SQL.
The user requests readable code and has raised the need for conventional Spring transaction management.

## Decision

Use a Spring-managed service with `@Transactional` for all queue mutations. Keep targeted JDBC
SQL for atomic claims, row locking and lease fencing. Do not introduce JPA solely to wrap these
operations. This choice does not rule out JPA for ordinary application entities in later work.

Each refresh job owns a one-day backfill. Deduplicate active region/day jobs and persist request-key
aliases, rejecting reuse of a key for different input. Limit pending work to 100, current claims to one,
and attempts to three. Use database time, five-minute leases, and 30/60-second retry delays.
All successful, incomplete and failed result writes must belong to the live token's transaction.
Cancellation invalidates that token; replacement workers receive a new one.

## Alternatives and consequences

A broker adds deployment infrastructure before measured demand. In-memory scheduling cannot
recover durable state. JPA remains an option for other records, but explicit SQL makes locking
and fencing conditions visible here. The job record is a persistence view, not a battery-domain model.

Worker network calls must remain outside database transactions. A lease prevents stale commits;
it does not forcibly terminate a process. NEM-029 must implement execution bounds and classify
source failures before enabling polling. NEM-030 must authenticate operators and derive trusted
audit identities. Current queue methods are internal and do not provide authorisation themselves.
Simulation queueing and its external process watchdog remain NEM-016, before simulation jobs launch.

## Evidence

See [NEM-028](../backlog.md#nem-028) and [PostgreSQL verification](../evidence/jobs/findings.md).
