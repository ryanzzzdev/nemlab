# Running NEMLab locally

Created: 2026-09-24
Updated: 2026-10-01 — the Python backend is the active local runtime; Java remains
under `reference/java/` for comparison.
Scope: Commands to run the backend (`nemlab/`) and frontend (`nemlab-ui/`) on a
local workstation. Module READMEs remain the detailed references; this page is the
quick orientation.

## Prerequisites

- uv 0.11.29+ — `uv sync` provisions the pinned CPython 3.13.14 automatically.
- Node.js 22.23.1 and npm 10.9.8 (`nvm use` in `nemlab-ui/` reads `.nvmrc`).
- Docker — for PostgreSQL, the PostgreSQL-backed tests and container packaging.
- A filled-in `.env` copied from `.env.example`; its comments say which variables
  are worker-only, API-only or shared. Nothing loads it implicitly.
- JDK 25 is only needed when running the Java reference under `reference/java/`.

## One-time setup

```sh
cd nemlab
npm ci --ignore-scripts --prefix api/contracts   # contract tooling
uv sync --all-packages --locked                  # Python 3.13.14 + locked deps
docker compose up -d postgres                    # PostgreSQL on 127.0.0.1:55432
set -a; . ./.env; set +a
uv run python -m nemlab_infrastructure.migrate check    # report DB state first
# then exactly one of:
uv run python -m nemlab_infrastructure.migrate migrate  # if check reports `empty`
uv run python -m nemlab_infrastructure.migrate adopt    # if check reports `java-managed`
```

See [infrastructure/README.md](../../infrastructure/README.md) for the adoption
workflow and backup/restore rehearsal.

## Run the backend

From `nemlab/`, source the environment, then run each process in its own
terminal:

```sh
set -a; . ./.env; set +a   # required in every backend terminal
uv run nemlab-api          # http://127.0.0.1:8080 — curl /actuator/health
uv run nemlab-worker       # no HTTP port; idles with all flags off
```

The API honours `NEMLAB_DATA_ENABLED` (public price reads),
`NEMLAB_ADMIN_ENABLED` (operator routes and browser auth, requiring
`NEMLAB_ADMIN_OPERATOR`, a 43–128 character base64url `NEMLAB_ADMIN_TOKEN`
and `NEMLAB_ADMIN_BASE_URL` — the Admin UI origin+path used in sign-in
links, e.g. `http://127.0.0.1:5274/admin` for the local dev server) and
`NEMLAB_SIMULATION_API_ENABLED` (public simulation lifecycle).
`SERVER_ADDRESS` and `PORT` select the bind. With all flags off the API starts
health-only; any enabled flag requires `NEMLAB_DB_*` and a migrated schema.
Sessions use Secure cookies by default; `NEMLAB_ENVIRONMENT=development`
plus `NEMLAB_INSECURE_COOKIES=true` relaxes that for local http — the
combination refuses to start under `production`. Auth rate limits tune via
`NEMLAB_ADMIN_MAIL_PER_EMAIL_HOUR` (5), `NEMLAB_ADMIN_MAIL_PER_IP_HOUR`
(20), `NEMLAB_ADMIN_RESEND_COOLDOWN_SECONDS` (60),
`NEMLAB_ADMIN_EXCHANGE_FAIL_PER_IP` (10/15 min) and
`NEMLAB_ADMIN_MAIL_BUDGET_PER_DAY` (200).

Browser sign-in is email-link only: `POST /api/auth/v1/sign-in-requests`
queues a durable outbox row, `POST /api/auth/v1/sessions` exchanges the
fragment token for an HttpOnly cookie, and `POST /api/auth/v1/logout`
revokes (CSRF + same-origin required). Sessions last 72 hours absolute with
a 24-hour idle window that slides on each request.

Three ways to get an owner session locally. All `nemlab_infrastructure.admin`
commands need the `.env` values (`NEMLAB_DB_URL`/`NEMLAB_DB_PASSWORD`) in the
environment — load them once per shell:

```sh
set -a && . ./.env && set +a
```

Then bootstrap the owner once:

```sh
uv run python -m nemlab_infrastructure.admin bootstrap-owner \
    --name "Owner" --email "owner@example.test" --confirm
```

**1. One-off sign-in link** (handiest — dev only):

```sh
NEMLAB_ENVIRONMENT=development \
    uv run python -m nemlab_infrastructure.admin sign-in-link \
    --email "owner@example.test"
```

Prints a ready-to-open `…/admin/sign-in#token=…` URL — the real single-use
15-minute token path, minus the mail hop. Each invocation mints a fresh link.

**2. Seed a session cookie directly** (no mail needed — dev only):

```sh
NEMLAB_ENVIRONMENT=development \
    uv run python -m nemlab_infrastructure.admin seed-session \
    --email "owner@example.test"
```

The command prints a `token:` — store it as the `nemlab_session` cookie on
`127.0.0.1` (DevTools → Application → Cookies → `http://127.0.0.1:5274`,
new cookie named `nemlab_session`, value = the token), then reload
`http://127.0.0.1:5274/admin/`.

**3. Real sign-in flow** — exercises the actual auth path end to end:

1. Open `http://127.0.0.1:5274/admin/sign-in`, enter `owner@example.test`,
   submit. The response is a generic `202` either way.
2. With mail delivery off, read the link from the outbox:

   ```sh
   docker exec nemlab-postgres-1 psql -U nemlab -d nemlab -tA -c \
     "SELECT substring(body from 'https?://[^[:space:]]*sign-in#token=[A-Za-z0-9_-]+') \
      FROM admin_email_outbox \
      WHERE kind='sign_in' AND recipient='owner@example.test' \
      ORDER BY created_at DESC LIMIT 1"
   ```

   (Or enable `NEMLAB_MAIL_ENABLED=true` + `NEMLAB_MAIL_DIR=/tmp/nemlab-mail`
   on the worker and `cat` the newest `.eml`.)
3. Open the link — it's a single-use 15-minute token. Note the resend
   cooldown: rapid resubmits return generic `202` without minting a fresh
   token, so reuse the newest outbox link instead of resubmitting.

The worker honours `NEMLAB_WORKER_ENABLED` (refresh polling — requires
`OPEN_ELECTRICITY_API_KEY`), `NEMLAB_WORKER_SCHEDULE_ENABLED`,
`NEMLAB_WORKER_REGIONS`, `NEMLAB_WORKER_POLL_MS`, `NEMLAB_GRID_IMPORT_ENABLED`
(GridReplay imports — also requires `OPEN_ELECTRICITY_API_KEY`),
`NEMLAB_GRID_IMPORT_POLL_MS`, `NEMLAB_SIMULATION_ENABLED`,
`NEMLAB_SIMULATION_POLL_MS`, and `NEMLAB_MAIL_ENABLED` with `NEMLAB_MAIL_DIR`
(Admin outbox drain — writes captured `.eml` files, never a live recipient)
and `NEMLAB_MAIL_POLL_MS`. Fetch and simulation children run isolated
with cleared environments and bounded deadlines; stopping the worker releases
claims as `WORKER_STOPPED`.

The mail drain also runs access retention hourly: unverified requests are
deleted after 7 days, rejected requests after 30, approved-request messages
are scrubbed 30 days post-decision, lapsed visitor contact data is
pseudonymised 90 days after their last grant ends, and access-audit rows are
deleted after 180 days — the product defaults, not a compliance
certification. A real mail provider, sender domain and credentials are
deployment inputs (M7); the only transport in this build is the captured
`.eml` mailbox.

Operator grid imports are submitted on the admin surface:

```sh
curl -X POST http://localhost:8080/api/admin/v1/grid-imports \
  -H "Authorization: Bearer $NEMLAB_ADMIN_TOKEN" \
  -H "Idempotency-Key: sep2023-nsw1" \
  -H "Content-Type: application/json" \
  -d '{"region":"NSW1","startDay":"2023-09-01","endExclusive":"2023-10-01"}'
```

The returned job view carries `nextDay` (the durable resume checkpoint),
`optionalFailures` (power-series fetch failures, distinct from core market
failures) and `status`; `GET .../events` audits it and `POST .../{id}/cancel`
revokes a running claim. A `FAILED` job keeps `nextDay` — resubmitting the
remaining window is safe: day saves deduplicate by content hash.

The full operator pipeline — grid import, per-day price refreshes and
catalogue publication, with monitoring, failure semantics and recovery — is
documented in [runbook-grid-data.md](runbook-grid-data.md).

Packaged startup smoke check:

```sh
python3 scripts/smoke_apps.py
```

## Run the backend in containers

```sh
docker build --target api -t nemlab-api .
docker build --target worker -t nemlab-worker .
docker build --target migrate -t nemlab-migrate .
docker compose --profile apps up -d
```

`docker compose --profile apps up` builds the API and worker images and starts
them alongside PostgreSQL; the in-network database URL is set to
`jdbc:postgresql://postgres:5432/nemlab`. Migrate first — either with
`uv run ... migrate` against `127.0.0.1:55432`, or containerised:

```sh
docker run --rm --network nemlab_default \
  -e NEMLAB_DB_URL=jdbc:postgresql://postgres:5432/nemlab \
  -e NEMLAB_DB_USER=nemlab -e NEMLAB_DB_PASSWORD=... nemlab-migrate migrate
```

`docker compose stop postgres` stops the database while keeping its volume.
Editing `NEMLAB_DB_PASSWORD` later does not change the existing database
password; the `nemlab-postgres` volume is initialised once.

## Run the Java reference

The preserved Java tree still builds and runs from `reference/java/`:

```sh
export JAVA_HOME=/usr/lib/jvm/java-25-openjdk-amd64
cd reference/java
./gradlew :api:bootRun     # http://127.0.0.1:8080
./gradlew :worker:bootRun  # non-HTTP worker
python3 scripts/smoke_apps.py   # packaged-jar startup check
```

It honours the same `NEMLAB_*` flags and database contract; run it for
behaviour comparison or regression evidence.

## Run the frontend

From `nemlab-ui/`:

```sh
npm ci --ignore-scripts
npm run dev         # http://127.0.0.1:5173 — public app
npm run dev:admin   # http://127.0.0.1:5274/admin — Admin console
```

The shell works without the backend. It proxies `/api/v1/prices` to
`http://127.0.0.1:8080` (override with `NEMLAB_API_TARGET`), so stored-price
pages only show data when the API runs with `NEMLAB_DATA_ENABLED=true` against
a migrated, populated database.

Other commands: `npm run build` then `npm run preview` (port 4173);
`npm run check` for contract/format/type/build/Playwright verification;
`npm run test:live` exercises the real API and PostgreSQL.

If a dev port is already in use, stop the process holding it:

```sh
fuser -k 5274/tcp                     # admin dev server (5173 public, 8080 API)
lsof -ti tcp:5274 | xargs -r kill     # same, without fuser
ss -tlnp | grep 5274                  # only inspect who owns the port
pkill -f nemlab-worker                # worker has no port — kill by name
pkill -f nemlab-api                   # API alternative to the 8080 port kill
```

## Detailed references

- Backend overview and build: [README.md](../../README.md)
- API endpoints and operator setup: [api/README.md](../../api/README.md)
- Worker settings and simulation execution: [worker/README.md](../../worker/README.md)
- Database, migrations and ingestion: [infrastructure/README.md](../../infrastructure/README.md)
- Frontend setup, proxying and checks: [nemlab-ui README](../../../nemlab-ui/README.md)
