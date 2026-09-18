# Why the OE price adapter lives in `infrastructure/`

- Project: NEMLab backend (`nemlab`)
- Created: 2026-09-18
- Updated: 2026-09-18
- LLM model: SWE-2 High (Cognition; session-declared)
- Agent: Devin Desktop

## Question

`docs/project/architecture.md` lists `infrastructure/` as "OE price adapter, JDBC
revisions/coverage, backfill checkpoints". Why is an external provider integration
(OE price adapter) placed inside a module that sounds like it should be the
technical foundations of the backend?

## Answer

`infrastructure/` is used in the hexagonal / ports-and-adapters sense — the module
for *all* outward-facing I/O adapters — not in the "platform/DevOps foundations"
sense. The OE client sits there for the same reason `PriceStore` (JDBC) does.

### Documented dependency rule

`architecture.md` states: "API and worker depend on core/infrastructure;
infrastructure implements interfaces defined by core; core does not depend on
either runnable app or infrastructure."

Intended split:

- `core/` — pure domain (battery math, prices-as-data), "free of Spring and
  database concerns"
- `infrastructure/` — every adapter crossing a process boundary on behalf of the
  domain: PostgreSQL/JDBC (`PriceStore`, revisions, coverage), backfill
  checkpoints (`PriceBackfill`), the refresh-job locking service
  (`RefreshJobService`), and external HTTP providers (`OePriceSource`)
- `api/`, `worker/` — runnable Spring Boot shells on top

An external provider client is the canonical outbound adapter in this pattern —
symmetric with the database. `OePriceSource` is pure `java.net.http` + Jackson
implementing a `PriceSource` port (see
`infrastructure/.../prices/OePriceSource.java` and `PriceSource.java`).

### Why not a separate `integrations/`/`clients/` module

- Decision 005 carries an austerity rule: "Introduce new infrastructure only for a
  demonstrated requirement", and `architecture.md` warns against a "catch-all
  shared utilities module".
- More adapters are coming: GridReplay needs additional OE metric adapters
  (NEM-018), so the OE client is not a one-off.

### Runtime topology

Only the worker calls OE (`Worker --> OE` in the architecture flow diagram), and
"public traffic never directly triggers an unbounded OE fetch." The adapter is
worker-side machinery, layered alongside the persistence it feeds.

## Open inconsistency (flagged)

The stated rule is "infrastructure implements interfaces defined by core", but
today the `PriceSource` port itself lives *inside* infrastructure
(`au.nemlab.infrastructure.prices.PriceSource`), and `core` only contains the
`batterylab` package — the planned `marketdata`/`jobs` core packages do not exist
yet. The port is currently colocated with its adapter rather than in core. Read
strictly, `PriceSource` (and the `jobs` service interfaces) should migrate into
core once those packages land; until then "ports in core" is aspirational rather
than implemented.

## References

- `docs/project/architecture.md` — module tree, dependency rule, runtime flow
- `docs/project/decisions/005-infrastructure-and-frontend.md` — austerity rule
- `docs/project/decisions/008-price-data-foundation.md` — price storage/ingestion decision
- `docs/project/evidence/data-foundation/findings.md` — ingestion verification
- `infrastructure/src/main/java/au/nemlab/infrastructure/prices/` — `OePriceSource`,
  `PriceSource`, `PriceStore`, `PriceBackfill`
