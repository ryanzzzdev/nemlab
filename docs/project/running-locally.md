# Running NEMLab locally

Created: 2026-09-24
Scope: Commands to run the backend (`nemlab/`) and frontend (`nemlab-ui/`) on a
local workstation. Module READMEs remain the detailed references; this page is the
quick orientation.

## Prerequisites

- JDK 25 with `JAVA_HOME` set, e.g. `export JAVA_HOME=/usr/lib/jvm/java-25-openjdk-amd64`.
- Node.js 22.23.1 and npm 10.9.8 (`nvm use` in `nemlab-ui/` reads `.nvmrc`).
- Docker — only for PostgreSQL-backed features and the disposable-container tests.

## Backend API (port 8080)

From `nemlab/`:

```sh
export JAVA_HOME=/usr/lib/jvm/java-25-openjdk-amd64

# One-time: install the locked contract tooling used by the backend build.
npm ci --ignore-scripts --prefix api/contracts

# Build the runnable jars (or use ./gradlew clean build for the full test suite).
./gradlew :api:bootJar :worker:bootJar
```

Then either run the packaged jar or use bootRun for development:

```sh
"$JAVA_HOME/bin/java" -jar api/build/libs/api.jar
# or: ./gradlew :api:bootRun
```

Verify with `curl http://127.0.0.1:8080/actuator/health` (returns UP). `PORT` and
`SERVER_ADDRESS` override the bind. Ctrl+C stops it. With no optional features
enabled the API needs no database or credentials.

## Backend worker (no HTTP port)

The worker is a non-HTTP process. Its default mode is inert — no jobs, no
schedules, no credentials needed:

```sh
"$JAVA_HOME/bin/java" -jar worker/build/libs/worker.jar
# or: ./gradlew :worker:bootRun
```

Packaged-startup smoke check for both apps (uses Python 3, random loopback port):

```sh
python3 scripts/smoke_apps.py
```

## Frontend (port 5173)

From `nemlab-ui/`:

```sh
npm ci --ignore-scripts
npm run dev
```

Open http://127.0.0.1:5173. The dev server binds to loopback, fails if the port is
taken, and starts without a backend. It proxies `/api/v1/prices` to
`http://127.0.0.1:8080` (override with `NEMLAB_API_TARGET` in the dev-server
environment), so stored-price pages only show data when the API runs with
`NEMLAB_DATA_ENABLED=true` against a migrated, populated database.

Other useful commands: `npm run build` then `npm run preview` (serves the bundle at
http://127.0.0.1:4173); `npm run check` runs contract/format/type/build/Playwright
verification; `npm run test:live` exercises the real Java API and PostgreSQL.

## Optional: local PostgreSQL and data features

The API/worker start fine without a database. For stored prices, ingestion or
simulations, from `nemlab/`:

```sh
export NEMLAB_DB_URL='jdbc:postgresql://127.0.0.1:55432/nemlab'
export NEMLAB_DB_USER='nemlab'
export NEMLAB_DB_PASSWORD='<your local password>'

docker compose up -d postgres                              # loopback port 55432
./gradlew :infrastructure:prices --args='migrate'          # run once per deployment
```

`docker compose stop postgres` stops the database while keeping its volume. Or load
the same variables from a local `.env` (`set -a; . ./.env; set +a`) — Gradle and
`java` do not read `.env` automatically, Compose does.

Feature flags, all off by default:

| Flag | Process | Needs | Effect |
| --- | --- | --- | --- |
| `NEMLAB_DATA_ENABLED=true` | API | migrated DB | Public stored-price reads (`/api/v1/prices/...`), used by the frontend. |
| `NEMLAB_SIMULATION_API_ENABLED=true` | API | migrated DB (V3) | Public simulation submit/status/result endpoints. |
| `NEMLAB_ADMIN_ENABLED=true` + `NEMLAB_ADMIN_OPERATOR` + `NEMLAB_ADMIN_TOKEN` | API | migrated DB | Protected operator endpoints for queuing price refreshes. |
| `NEMLAB_WORKER_ENABLED=true` | worker | DB + `OPEN_ELECTRICITY_API_KEY` | Polls and executes queued price-refresh jobs. |
| `NEMLAB_WORKER_SCHEDULE_ENABLED=true` + `NEMLAB_WORKER_REGIONS=NSW1,...` | worker | worker enabled | Submits daily refresh jobs at 00:15 NEM time. |
| `NEMLAB_SIMULATION_ENABLED=true` | worker | DB only | Polls and executes queued simulation jobs. |

Keep `NEMLAB_ADMIN_ENABLED=false` for the public frontend slice, and never put OE
keys or operator tokens in frontend code or `VITE_` variables.

## Detailed references

- Backend overview and build: [README.md](../../README.md)
- API endpoints and operator setup: [api/README.md](../../api/README.md)
- Worker settings and simulation execution: [worker/README.md](../../worker/README.md)
- Database, migrations and ingestion: [infrastructure/README.md](../../infrastructure/README.md)
- Frontend setup, proxying and checks: [nemlab-ui README](../../../nemlab-ui/README.md)
