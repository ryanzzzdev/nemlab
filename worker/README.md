# Worker: refresh polling and isolated simulation execution

`nemlab_worker` is the non-HTTP application. With every flag off it idles
without credentials and exits cleanly on SIGTERM/SIGINT. Enabled polling runs
against the fenced PostgreSQL queues — advisory-locked claims, lease fencing
and audit events are shared with the API.

## Run it

```sh
set -a; . ./.env; set +a
NEMLAB_WORKER_ENABLED=true uv run nemlab-worker     # price-refresh polling
NEMLAB_SIMULATION_ENABLED=true uv run nemlab-worker # simulation execution
```

Both flags may be enabled in one process; the two loops are independent.
Container: `docker build --target worker -t nemlab-worker .` then
`docker run --env-file .env -e NEMLAB_DB_URL=jdbc:postgresql://postgres:5432/nemlab nemlab-worker`.

## Refresh polling (`NEMLAB_WORKER_ENABLED`)

Requires `OPEN_ELECTRICITY_API_KEY`, `NEMLAB_DB_*` and a migrated schema.
`NEMLAB_WORKER_SCHEDULE_ENABLED` adds the fixed UTC+10 daily schedule per
`NEMLAB_WORKER_REGIONS`; `NEMLAB_WORKER_POLL_MS` bounds the poll interval
(1000–60000). Each claimed job runs the fetch in an isolated child —
`python -m nemlab_worker --fetch-price REGION DAY OUT` — with a cleared
environment carrying only the OE key, a 240 s watchdog and a 256 KB output cap.

## Admin mail outbox (`NEMLAB_MAIL_ENABLED`)

Drains `admin_email_outbox` on `NEMLAB_MAIL_POLL_MS` (1000–60000) — the
spec's "existing worker poll cycle" for transactional Admin email
(NEM-096). `NEMLAB_MAIL_DIR` is required and names the captured-mailbox
directory: the only M6 transport writes one `.eml`-style file per message
(`To:`/`Subject:`/body), so this build can never reach a live recipient.
Deliveries retry with linear backoff and go terminally `failed` after
five attempts with a classified diagnostic.

## Simulation execution (`NEMLAB_SIMULATION_ENABLED`)

No OE credential needed. `NEMLAB_SIMULATION_POLL_MS` bounds the poll interval.
Each claimed job runs the comparison in an isolated child —
`python -m nemlab_worker --simulate IN OUT` — with an empty environment,
a 15 s self-watchdog, a 4 GiB address-space bound and bounded input/output
files. The parent independently validates results before publishing; failed or
unproven runs surface only a whitelisted failure code.

Stopping the worker terminates in-flight children and releases claims as
`WORKER_STOPPED`, so jobs remain claimable by the next run.
