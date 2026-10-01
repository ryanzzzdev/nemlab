# Database cutover rehearsal (NEM-080)

Date: 2026-10-02. Scope: backup/restore, empty setup, populated Java-clone
adoption, post-switch reads and writes, and rollback — all on isolated clone
databases. The live compose database (`nemlab`) was never mutated.

## Source database (pre-cutover inventory)

Java-managed compose PostgreSQL 18.6 (`nemlab-postgres` volume, port 55432):

| Object | Count | State |
| --- | --- | --- |
| `price_revision` | 10 | immutable |
| `price_current` | 10 | complete NSW1/QLD1/VIC1 days, 2026-09-20 – 2026-10-01 |
| `refresh_job` | 10 | all `SUCCEEDED` — queue already drained |
| `simulation_job` | 13 | all `SUCCEEDED` — queue already drained |
| `simulation_result` | 13 | Java-era results, solver `ojAlgo 57.3.0` |

No QUEUED or RUNNING rows existed, satisfying the drain prerequisite. No Java
worker or scheduler was running during the rehearsal; mixed Java/Python worker
operation was avoided throughout.

## Backup and populated-clone restore

```sh
docker exec nemlab-postgres-1 pg_dump -U nemlab --format=custom nemlab > nemlab.dump
createdb nemlab_rehearsal && pg_restore -U nemlab -d nemlab_rehearsal < nemlab.dump
```

(Equivalently via `docker compose exec`/`cp` as in `infrastructure/README.md`.)
Restore completed without errors; the clone held the identical V1–V3 schema and
`flyway_schema_history`.

## Adoption

```sh
NEMLAB_DB_URL=jdbc:postgresql://127.0.0.1:55432/nemlab_rehearsal uv run python -m nemlab_infrastructure.migrate check
# → java-managed, valid V1-V3 flyway schema — run `adopt` to stamp
… migrate adopt
# → stamped baseline; flyway_schema_history preserved
… migrate check
# → alembic-managed at nemlab_baseline_v1_v3
```

Verified post-adoption: `alembic_version` = `nemlab_baseline_v1_v3`;
`flyway_schema_history` retains the original V1/V2/V3 success rows (installed
2026-09-25); no DDL was replayed.

## Empty setup

`createdb nemlab_empty` → `migrate check` reports `empty` → `migrate migrate`
applies `nemlab_baseline_v1_v3` → `migrate check` reports `alembic-managed`.
A fresh database reaches the identical schema the adoption path stamps.

## Python reads Java-era data

Against `nemlab_rehearsal` via `uv run nemlab-api`:

- `GET /api/v1/prices/NSW1/coverage?start=…&endExclusive=…` — historical days
  serve with real revision UUIDs, `COMPLETE`/`NOT_IMPORTED` states.
- `GET /api/v1/simulations/{id}` + `/result` for a Java-era job — status
  `SUCCEEDED`, result contains `fixed`, `hindsight`, `threshold`, `inputs`,
  `prices`, `versions`; `versions.solver` preserved verbatim as
  `ojAlgo 57.3.0`, `executionProfile` = `ordered-comparison-v1`. Old metadata
  is never rewritten or recomputed.

## Python executes new work post-switch

- `POST /api/v1/simulations` → `202 QUEUED`, id `3d5b6c20-485b-4d5c-8309-5089a4c53da6`.
- `uv run nemlab-worker` (simulation enabled) claimed the job, ran the
  `--simulate` child, validated, and published: `SUCCEEDED`, attempts 1.
- Stored result carries truthful Python metadata:
  `versions.solver = "HiGHS 1.12.0 via SciPy 1.18.1 linprog/highs-ds"` and
  `solverStatus OPTIMAL`.
- Final clone state: 14 simulation jobs / 14 results (13 Java-era + 1 Python).

## Java reads Python-written rows

The reference Java API (`reference/java/api/build/libs/api.jar`, JDK 25)
started against the adopted clone — Flyway `validate` passed because
`flyway_schema_history` is preserved; `alembic_version` is ignored by Flyway.
Java then served:

- The Python-written simulation result — all three strategies, HiGHS solver
  identity round-trips through Java's reader unchanged.
- Java-era price coverage and single-day series unchanged.

Reads are therefore compatible in both directions across the cutover boundary.

## Rollback

Recovery is **restore the pre-cutover backup into a fresh database and point
the application at it** — an additive operation, never a destructive in-place
restore:

```sh
createdb nemlab_rollback && pg_restore -U nemlab -d nemlab_rollback < nemlab.dump
migrate check → java-managed, valid V1-V3 flyway schema — run `adopt` to stamp
```

The rollback database is the untouched pre-cutover state: no `alembic_version`,
13 simulation jobs (the Python-written job is absent, as expected — rollback
discards post-switch writes). Java resumes against it with no further action.
Re-running a **forward** backup/restore of the post-cutover clone
(`nemlab_rehearsal` → `nemlab_forward`) preserves adoption state plus the
Python-written job: `alembic_version` present, 14 SUCCEEDED jobs, 14 results.

There is intentionally no automatic or destructive restore command —
`infrastructure/README.md` states the policy.

## Numerical, performance and resource limits

- Solver: `OrderedHindsight.Limits` = 5000 ms / 100 000 iterations; OPTIMAL
  requires solver-optimal + finite non-negative gap ≤ 0.01 + accounting
  reconcile (`1e-6 + 1e-9·max`) within budget; `DispatchValidator` tolerance
  `1e-7`. Identical in both implementations.
- Simulation child measured on this host: ~110 MiB RSS, ~1.9 GiB virtual
  (mostly reservations), ~0.6 s wall for a representative day. The 4 GiB
  `RLIMIT_AS` child self-bound is an **address-space** bound, not an RSS
  guarantee. Parent watchdog 15 s + 5 s termination bound; child 15 s
  `os._exit(124)` watchdog.
- Fetch child: 240 s watchdog, 256 KiB output cap, OE client 10 s connect /
  30 s request, 2 MiB body cap.
- Queues: refresh/simulation pending cap 100; visitor cap 10 pending,
  3 retries/day; backoffs `30*attempts` and `5*attempts`; leases 300 s/60 s.
- Full test suite wall time ~78 s including real-PostgreSQL integration.

## Pending gates (honest status)

- **NEM-038 hosted CI**: outstanding — the active workflow has never run on a
  hosted runner; local evidence does not imply hosted success.
- **NEM-020 deployment/provider**: outstanding — no hosted deployment exists.
- M3 and public launch are **not** claimed complete; this gate is local parity.
