# nemlab-infrastructure

PostgreSQL persistence, price ingestion, refresh/simulation queues, and schema
migrations. May depend on `nemlab_core` only; API and worker depend on this
package. Mirrors the Java `infrastructure` module under `reference/java/`.

## Schema migration

Alembic owns schema evolution. The baseline revision
(`migrations/versions/nemlab_baseline_v1_v3.py`) replays the Java Flyway V1–V3
DDL **byte-identically** — the SQL lives once, in
`src/nemlab_infrastructure/db/migration/*.sql`, and its Flyway checksums are
pinned by tests.

Migrations are **explicit, single-run commands** — no application performs
schema changes on startup.

```sh
# From the repository root, with NEMLAB_DB_URL / NEMLAB_DB_USER /
# NEMLAB_DB_PASSWORD set (same .env contract as the Java backend):

uv run python -m nemlab_infrastructure.migrate check    # report DB state
uv run python -m nemlab_infrastructure.migrate migrate  # apply pending revisions
uv run python -m nemlab_infrastructure.migrate adopt    # adopt a Java DB
uv run python -m nemlab_infrastructure.migrate stamp    # force-mark head (repair)
```

`check` reports one of: `empty`, `java-managed` (with adoption validation
result), `alembic-managed at <revision>`, or `unknown`.

### Empty database

`migrate` runs the baseline, creating all 11 tables with their checks,
immutability triggers, indexes, and functions. DDL runs transactionally — a
failed upgrade rolls back completely. Re-running `migrate` is a no-op.

### Existing Java-managed database

Never run `migrate` against a Java-managed database: Alembic would try to
replay the baseline DDL and fail (transactionally, leaving the schema
untouched). Instead:

```sh
uv run python -m nemlab_infrastructure.migrate adopt
```

`adopt` first verifies:

- `flyway_schema_history` contains exactly the V1–V3 applied SQL migrations,
  in order, each `success=true`;
- each recorded checksum equals the Flyway CRC32 recomputed from the packaged
  SQL bytes;
- the live schema carries every expected table, column (name, type,
  nullability), constraint kind count, trigger, function, and index.

It then stamps the baseline revision into `alembic_version`.
`flyway_schema_history` is preserved untouched — the audit trail survives —
and no DDL is replayed. Adoption **refuses** unknown (no Flyway history),
partial, or drifted databases; fix the database or migrate it by hand first.
After adoption, ordinary `migrate` applies future revisions.

### Backup and restore rehearsal

Rehearse before adopting a production clone, using the compose service:

```sh
# Backup (run while the compose stack is up):
docker compose exec postgres pg_dump -U nemlab -d nemlab \
    --format=custom --file=/tmp/nemlab-backup.dump
docker compose cp postgres:/tmp/nemlab-backup.dump ./nemlab-backup.dump

# Restore rehearsal — restore into a scratch database, then adopt:
docker compose exec postgres createdb -U nemlab nemlab_restore_test
docker compose cp ./nemlab-backup.dump postgres:/tmp/nemlab-backup.dump
docker compose exec postgres pg_restore -U nemlab -d nemlab_restore_test \
    /tmp/nemlab-backup.dump
NEMLAB_DB_URL=jdbc:postgresql://127.0.0.1:55432/nemlab_restore_test \
    uv run python -m nemlab_infrastructure.migrate adopt

# Inspect, then drop the scratch database:
docker compose exec postgres dropdb -U nemlab nemlab_restore_test
```

Never reset a live database destructively; there is no `reset` command.

## Admin identity

The V8 migration adds the M6 Admin account tables (`admin_*`): users,
access requests, viewer grants, hashed one-use tokens, sessions, the email
outbox, access audit and persisted rate-limit counters. Owner bootstrap and
recovery are **server-side commands** — there is no public route, no
default password and no account is created unless the owner identity is
supplied explicitly:

```sh
# Create the single enabled owner (idempotent for the same email):
uv run python -m nemlab_infrastructure.admin bootstrap-owner \
    --name "Owner Name" --email "owner@example.com" --confirm

# Audited recovery: disables the current owner, revokes its sessions and
# installs the replacement (requires a recorded reason):
uv run python -m nemlab_infrastructure.admin recover-owner \
    --name "Owner Name" --email "owner@example.com" \
    --reason "lost mailbox" --confirm
```

A partial unique index enforces exactly one enabled owner; concurrent
bootstraps race safely onto the same row. Bootstrap with a different email
than the enabled owner refuses and points at `recover-owner`, which writes
`OWNER_DISABLED`/`OWNER_RECOVERED` audit rows before the change commits.
Last-owner protection is an application rule on ordinary revoke/disable
paths — the recovery command itself is the escape hatch and always leaves
exactly one enabled owner.

## Tests

`uv run pytest infrastructure/tests` — schema/adoption integration tests
create and drop `nemlab_test_*` databases on the configured server and skip
when it is unreachable.
