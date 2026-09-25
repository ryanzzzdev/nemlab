# Running NEMLab locally

Created: 2026-09-24
Scope: Commands to run the backend (`nemlab/`) and frontend (`nemlab-ui/`) on a
local workstation. Module READMEs remain the detailed references; this page is the
quick orientation.

## Prerequisites

- JDK 25 with `JAVA_HOME` set, e.g. `export JAVA_HOME=/usr/lib/jvm/java-25-openjdk-amd64`.
- Node.js 22.23.1 and npm 10.9.8 (`nvm use` in `nemlab-ui/` reads `.nvmrc`).
- Docker — only for PostgreSQL-backed features and the disposable-container tests.
- A filled-in `.env` copied from `.env.example`; its comments say which variables
  are worker-only, API-only or shared. Nothing loads it implicitly.

## One-time setup

```sh
cd nemlab
npm ci --ignore-scripts --prefix api/contracts   # contract tooling used by the build
docker compose up -d postgres                    # PostgreSQL on 127.0.0.1:55432
set -a; . ./.env; set +a
./gradlew :infrastructure:prices --args='migrate'  # schema, once per deployment
```

`docker compose stop postgres` stops the database while keeping its volume.
Editing `NEMLAB_DB_PASSWORD` later does not change the existing database password;
the `postgres` volume is initialised once.

## Run the backend

From `nemlab/`, one process per terminal:

```sh
set -a; . ./.env; set +a   # required in every backend terminal
./gradlew :api:bootRun     # http://127.0.0.1:8080 — curl /actuator/health
./gradlew :worker:bootRun  # no HTTP port; quiet between polls
```

Packaged jars also work: `./gradlew :api:bootJar :worker:bootJar` then
`"$JAVA_HOME/bin/java" -jar api/build/libs/api.jar` (or `worker/.../worker.jar`).
Packaged-startup smoke check: `python3 scripts/smoke_apps.py`.

With `.env` sourced, the enabled flags take effect — database-backed price reads,
simulation endpoints and worker polling/scheduling all come up. With all flags
off, the API still starts (health only) and the worker idles with no credentials.

Running `ApiApplication`/`WorkerApplication` from IntelliJ needs the same
variables in the run configuration's environment (or an env-file plugin) —
the IDE does not read `.env` either.

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
