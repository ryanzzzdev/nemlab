# NEMLab

Python rebuild in progress: see the [migration plan](docs/project/python-backend-rebuild.md) and [ordered backlog](docs/project/backlog.md#python-rebuild-tasks). The Java implementation is preserved as a runnable reference under [`reference/java/`](reference/java/README.md) — run its commands from that directory — until the Python replacement passes its parity gates.

NEMLab explores Australia's National Electricity Market through historical analysis and experiments. BatteryLab compares simulated battery trading strategies; GridReplay helps visitors investigate notable market periods.

This is the backend project and the home of shared project documentation. The Java/Spring Boot backend has separate runnable API and worker applications. The [frontend](../nemlab-ui/README.md) lives in the separate sibling `nemlab-ui` Git repository.

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

The backend contains the plain Java battery-engine `core`, an `infrastructure` module for versioned price ingestion/storage, and separate Spring Boot 4.1.1 `api` and `worker` applications. PostgreSQL price ingestion and resumable backfills are available through an explicit local operator command. Opt-in worker scheduling is available; protected [operator endpoints](reference/java/api/README.md) are also available. Public [stored-price reads](reference/java/api/README.md#public-stored-price-reads) are available separately. The frontend build foundation is available; public simulation APIs are available; GridReplay APIs and frontend product integration remain future work.

Use Node.js 22.23.1/npm 10.9.8 for the [API contract checks](api/contracts/README.md), alongside JDK 25 (verified locally with OpenJDK 25.0.4+7). The checked-in Gradle 9.7.1 wrapper verifies its distribution checksum; JUnit 6.1.3 and transitive test dependencies are locked. No globally installed Gradle or OE credentials are required for tests. A running Docker daemon is required for the PostgreSQL integration tests; the initial run downloads disposable container images.

```sh
# Point JAVA_HOME at your JDK 25 installation. On this workstation:
export JAVA_HOME=/usr/lib/jvm/java-25-openjdk-amd64
npm ci --ignore-scripts --prefix api/contracts
cd reference/java && ./gradlew clean build
```

The first run downloads Gradle, application and test dependencies. Once Java dependencies and contract tools are installed, `./gradlew clean build --offline` runs without network access. Tests include synthetic reference cases and saved OE price fixtures. Open `reference/java/core/build/reports/tests/test/index.html` for the generated report.

The entry point is `au.nemlab.batterylab.BatterySimulation.run`, accepting an explicit battery, ordered windows, costs and complete price day. `FixedSchedule.plan` accepts only physical inputs and windows; `DispatchValidator` independently checks the resulting trajectory. Results include immutable inputs, unrounded dispatch/accounting and model/strategy versions. The engine is a library exposed through the opt-in [simulation API](reference/java/api/README.md#public-simulation-lifecycle). See the [engine contract](docs/project/features/battery-model-contract.md) for units, input rules and limits.

Local OE credentials remain in ignored configuration; never commit them. `OrderedHindsight.solve` provides the certified equal-window comparison using ojAlgo 57.3.0. Always inspect its outcome status: only `OPTIMAL` permits the optimal-within-tolerance label. Solver budgets are cooperative inside the engine; the opt-in [simulation worker](reference/java/worker/README.md#simulation-execution) adds hard subprocess deadlines and immutable job/result storage. Public simulation endpoints are available; whole-day/unrestricted optimisation remains future work.

For the explicit solver experiment, run `./gradlew :core:hindsightBenchmark` under `reference/java/`. It rewrites the tracked benchmark CSV evidence; ordinary `build` does not. See [measurements and limitations](docs/project/evidence/engine/findings.md).

## Run the applications

After building, start these in separate terminals:

```sh
"$JAVA_HOME/bin/java" -jar reference/java/api/build/libs/api.jar
"$JAVA_HOME/bin/java" -jar reference/java/worker/build/libs/worker.jar
```

The API binds to `127.0.0.1:8080` by default. Check `http://127.0.0.1:8080/actuator/health`; it returns status UP without component details. `PORT` and `SERVER_ADDRESS` override the API bind settings. Use Ctrl+C to stop either application.

The worker is a non-HTTP application kept alive by Spring Boot. Its default mode has no active jobs or schedules and needs no credentials. Enable queue polling and daily refreshes explicitly using the [worker setup](reference/java/worker/README.md). The API shell still needs no database or OE credentials to start. API health currently confirms application startup only, not ingestion/solver/database readiness. Operator controls can be enabled separately using the [API setup](reference/java/api/README.md); simulation endpoints are independently enabled; GridReplay endpoints remain future work.

For development, `./gradlew :api:bootRun` and `./gradlew :worker:bootRun` are also available under `reference/java/`. Automated packaged startup checks use Python 3:

```sh
python3 reference/java/scripts/smoke_apps.py
```

That script starts each executable jar, checks API health and worker liveness, then stops its own processes. It uses a random loopback port for the API. Reports are under each module's `build/reports/tests/test/` directory.

## Python backend (rebuild in progress)

The backend is being rebuilt in Python under the [rebuild plan](docs/project/python-backend-rebuild.md); the Java tree under `reference/java/` remains the runnable reference until the parity gate closes. The Python workspace uses uv with CPython 3.13.14 pinned in `.python-version` and four packages mirroring the Java boundaries: `core` (`nemlab_core`), `infrastructure` (`nemlab_infrastructure`), `api` (`nemlab_api`) and `worker` (`nemlab_worker`).

```sh
uv sync --all-packages --locked   # provisions Python 3.13.14 + locked deps
uv run pytest                     # all package tests
uv run ruff check . && uv run ruff format --check . && uv run mypy
uv run lint-imports               # module-boundary contract
uv run nemlab-api                 # API on 127.0.0.1:8080 (SERVER_ADDRESS/PORT)
uv run nemlab-worker              # non-HTTP worker; idles with flags off
uv run python -m nemlab_infrastructure.migrate migrate   # Alembic schema
```

For an existing Java-migrated database, use `... migrate adopt` instead — see
[infrastructure/README.md](infrastructure/README.md) for state checks,
checksum validation and backup/restore rehearsal.

Environment variables are unchanged: `.env.example` still documents the shared `NEMLAB_*` contract, including the `jdbc:postgresql://` database URL format the Python settings translate for SQLAlchemy/Psycopg. The Python feature surface is still scaffold-only — parity lands task by task.

## CI and module boundaries

[The reference workflow](reference/java/ci/backend.yml) records the Java build/tests and packaged startup checks on Java 25 as they ran pre-move, repaired to run under `reference/java/`; no active hosted workflow runs the Python build yet (NEM-078). No remote publication has occurred. If another CI provider is selected, reuse these commands.

In the Java build, `./gradlew verifyModuleBoundaries` rejects forbidden project dependencies; the Python workspace enforces the same direction with `uv run lint-imports` (import-linter layers contract). API and worker may depend on core/infrastructure; infrastructure may depend on core; core has no project dependencies. Infrastructure contains the explicit price-source and JDBC adapters; opt-in worker wiring is implemented, while price-read/operator APIs are implemented and simulation APIs are implemented and GridReplay APIs remain future work. See [foundation verification](docs/project/evidence/foundation/findings.md).

## Price ingestion and local PostgreSQL

See [infrastructure instructions](reference/java/infrastructure/README.md) for Compose setup, explicit migrations,
bounded backfills, resume/status, coverage and import history. The importer preserves immutable
price revisions and snapshot references, and pauses rather than filling missing data. Tests
use disposable PostgreSQL containers; ordinary application startup still needs no database.
The `.env.example` includes local database fields; real secrets stay in ignored configuration.

Read [AGENTS.md](AGENTS.md) before working on this project.
