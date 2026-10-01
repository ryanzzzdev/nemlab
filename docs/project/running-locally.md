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
uv run python -m nemlab_infrastructure.migrate check    # report DB state
uv run python -m nemlab_infrastructure.migrate migrate  # empty database only
uv run python -m nemlab_infrastructure.migrate adopt    # adopt a Java-managed DB
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
`NEMLAB_ADMIN_ENABLED` (operator routes, requiring `NEMLAB_ADMIN_OPERATOR` and a
43–128 character base64url `NEMLAB_ADMIN_TOKEN`) and
`NEMLAB_SIMULATION_API_ENABLED` (public simulation lifecycle).
`SERVER_ADDRESS` and `PORT` select the bind. With all flags off the API starts
health-only; any enabled flag requires `NEMLAB_DB_*` and a migrated schema.

The worker honours `NEMLAB_WORKER_ENABLED` (refresh polling — requires
`OPEN_ELECTRICITY_API_KEY`), `NEMLAB_WORKER_SCHEDULE_ENABLED`,
`NEMLAB_WORKER_REGIONS`, `NEMLAB_WORKER_POLL_MS`, `NEMLAB_SIMULATION_ENABLED`
and `NEMLAB_SIMULATION_POLL_MS`. Fetch and simulation children run isolated
with cleared environments and bounded deadlines; stopping the worker releases
claims as `WORKER_STOPPED`.

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
npm run dev   # http://127.0.0.1:5173
```

The shell works without the backend. It proxies `/api/v1/prices` to
`http://127.0.0.1:8080` (override with `NEMLAB_API_TARGET`), so stored-price
pages only show data when the API runs with `NEMLAB_DATA_ENABLED=true` against
a migrated, populated database.

Other commands: `npm run build` then `npm run preview` (port 4173);
`npm run check` for contract/format/type/build/Playwright verification;
`npm run test:live` exercises the real API and PostgreSQL.

## Detailed references

- Backend overview and build: [README.md](../../README.md)
- API endpoints and operator setup: [api/README.md](../../api/README.md)
- Worker settings and simulation execution: [worker/README.md](../../worker/README.md)
- Database, migrations and ingestion: [infrastructure/README.md](../../infrastructure/README.md)
- Frontend setup, proxying and checks: [nemlab-ui README](../../../nemlab-ui/README.md)
