# NEMLab

The backend runs on Python (uv workspace, CPython 3.13.14). The Java implementation is preserved as a runnable reference under [`reference/java/`](reference/java/README.md) for comparison and regression until the parity gate closes — see the [rebuild plan](docs/project/python-backend-rebuild.md) and [ordered backlog](docs/project/backlog.md#python-rebuild-tasks).

NEMLab explores Australia's National Electricity Market through historical analysis and experiments. BatteryLab compares simulated battery trading strategies; GridReplay helps visitors investigate notable market periods.

This is the backend project and the home of shared project documentation. The backend has separate runnable API and worker applications. The [frontend](../nemlab-ui/README.md) lives in the separate sibling `nemlab-ui` Git repository.

## Project documentation

- [Roadmap and milestone progress](docs/project/roadmap.md)
- [Backlog and next work](docs/project/backlog.md)
- [Architecture](docs/project/architecture.md)
- [Blockers and open questions](docs/project/blockers.md)
- [Data foundation](docs/project/features/data-foundation.md)
- [BatteryLab](docs/project/features/batterylab.md)
- [BatteryLab static demo](docs/demos/batterylab/index.html) — mocked-data preview of the simulation journey
- [GridReplay](docs/project/features/gridreplay.md)
- [GridReplay static demo](docs/demos/gridreplay/index.html) — mocked-data preview of the event catalogue and replay
- [Admin](docs/project/features/admin.md)
- [Decision records](docs/project/decisions/)
- [Running locally](docs/project/running-locally.md)
- [Documentation workflow](docs/project/documentation-guide.md)
- [Work journal](docs/project/journal/)
- [Original project ideas](docs/initial-ideas/nemlab-project-ideas.md)

## Development setup

The backend contains the battery-engine `core`, an `infrastructure` package for versioned price ingestion/storage, and separate FastAPI `api` and non-HTTP `worker` applications mirroring the Java boundaries: `nemlab_core`, `nemlab_infrastructure`, `nemlab_api`, `nemlab_worker`. PostgreSQL price ingestion and resumable backfills are available through explicit commands. Opt-in worker scheduling and protected [operator endpoints](api/README.md) are available; public [stored-price reads](api/README.md) and [simulation endpoints](api/README.md) are implemented.

Use uv 0.11.29+ (the workspace pins CPython 3.13.14 via `.python-version`) and Node.js 22.23.1/npm 10.9.8 for the [API contract checks](api/contracts/README.md). A running Docker daemon is required for the PostgreSQL integration tests and the container packaging; no Java, Gradle or OE credentials are needed for the Python path.

```sh
uv sync --all-packages --locked   # provisions Python 3.13.14 + locked deps
uv run pytest                     # all package tests (PostgreSQL via NEMLAB_DB_*)
uv run ruff check . && uv run ruff format --check . && uv run mypy
uv run lint-imports               # module-boundary contract
npm ci --ignore-scripts --prefix api/contracts && (cd api/contracts && node verify.mjs)
```

The engine is `nemlab_core`: `comparison.run` accepts an explicit battery, ordered windows, costs and complete price day, and `comparison.validate` independently checks results. The ordered-hindsight solver runs on SciPy/HiGHS and reports certified outcomes only — only `OPTIMAL` permits the optimal-within-tolerance label. See the [engine contract](docs/project/features/battery-model-contract.md) for units, input rules and limits.

Local OE credentials remain in ignored configuration; never commit them.

## Run the applications

Source `.env` (copy `.env.example` first), start PostgreSQL, migrate the schema, then run each application:

```sh
set -a; . ./.env; set +a
docker compose up -d postgres
uv run python -m nemlab_infrastructure.migrate migrate   # or: adopt (Java-managed DB)
uv run nemlab-api      # http://127.0.0.1:8080 — /actuator/health
uv run nemlab-worker   # non-HTTP; idles with all flags off
```

`SERVER_ADDRESS` and `PORT` override the API bind. Feature flags stay disabled by default — `NEMLAB_DATA_ENABLED`, `NEMLAB_ADMIN_ENABLED`, `NEMLAB_SIMULATION_API_ENABLED` (API) and `NEMLAB_WORKER_ENABLED`, `NEMLAB_WORKER_SCHEDULE_ENABLED`, `NEMLAB_SIMULATION_ENABLED` (worker). Enabled database features require `NEMLAB_DB_*`; each startup probes the schema and fails fast. See [api/README.md](api/README.md) and [worker/README.md](worker/README.md).

Automated packaged startup checks:

```sh
python3 scripts/smoke_apps.py
```

The script starts `nemlab-api` and `nemlab-worker` with all features off, checks actuator health and worker liveness on a random loopback port, then stops only its own children.

## Containers

`Dockerfile` builds three targets from the locked uv workspace: `api`, `worker` and `migrate` (schema management). All run non-root on `python:3.13.14-slim`; SciPy/HiGHS ship as binary wheels, no system solver libraries needed.

```sh
docker build --target api -t nemlab-api .
docker build --target worker -t nemlab-worker .
docker build --target migrate -t nemlab-migrate .
docker run --rm --network <db-network> -e NEMLAB_DB_URL=... -e NEMLAB_DB_USER=... -e NEMLAB_DB_PASSWORD=... nemlab-migrate migrate
docker compose --profile apps up -d   # postgres + api + worker built from source
```

The `postgres` service and its `nemlab-postgres` volume are unchanged — existing data persists across rebuilds.

## Java reference

The Java tree under `reference/java/` remains runnable: `./gradlew clean build`, `java -jar api/build/libs/api.jar`, `python3 reference/java/scripts/smoke_apps.py`. Use it for behaviour comparison and regression evidence. The reference workflow [reference/java/ci/backend.yml](reference/java/ci/backend.yml) records the Java-era hosted checks.

## CI and module boundaries

[The active workflow](.github/workflows/backend.yml) runs the Python checks: locked uv sync, ruff format/lint, strict mypy, `lint-imports`, the full PostgreSQL-backed pytest suite, contract verification (`verify.mjs`), packaged smoke and container builds.

`lint-imports` enforces the module direction the Java build checked with `verifyModuleBoundaries`: API and worker may depend on core/infrastructure; infrastructure may depend on core; core has no project dependencies.

## Price ingestion and local PostgreSQL

See [infrastructure instructions](infrastructure/README.md) for Compose setup, migrations/adoption,
bounded backfills, resume/status, coverage and import history. The importer preserves immutable
price revisions and snapshot references, and pauses rather than filling missing data. Tests
use scratch databases on the configured PostgreSQL server; ordinary application startup still
needs no database. The `.env.example` includes local database fields; real secrets stay in
ignored configuration.

Read [AGENTS.md](AGENTS.md) before working on this project.
