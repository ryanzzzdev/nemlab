# NEMLab

NEMLab explores Australia's National Electricity Market through historical analysis and experiments. BatteryLab compares simulated battery trading strategies; GridReplay helps visitors investigate notable market periods.

This is the backend project and the home of shared project documentation. The Java/Spring Boot backend has separate runnable API and worker applications. The frontend will live in a separate repository.

## Project documentation

- [Roadmap and milestone progress](docs/project/roadmap.md)
- [Backlog and next work](docs/project/backlog.md)
- [Architecture](docs/project/architecture.md)
- [Blockers and open questions](docs/project/blockers.md)
- [Data foundation](docs/project/features/data-foundation.md)
- [BatteryLab](docs/project/features/batterylab.md)
- [GridReplay](docs/project/features/gridreplay.md)
- [Admin](docs/project/features/admin.md)
- [Decision records](docs/project/decisions/)
- [Documentation workflow](docs/project/documentation-guide.md)
- [Work journal](docs/project/journal/)
- [Original project ideas](docs/summaries/nemlab-project-ideas.md)

## Development setup

The backend contains the plain Java battery-engine `core`, an `infrastructure` module reserved for adapters, and separate Spring Boot 4.1.1 `api` and `worker` applications. Database integration, ingestion, jobs and frontend are future work.

Use JDK 25 (verified locally with OpenJDK 25.0.4+7). The checked-in Gradle 9.7.1 wrapper verifies its distribution checksum; JUnit 6.1.3 and transitive test dependencies are locked. No globally installed Gradle or OE credentials are required.

```sh
# Point JAVA_HOME at your JDK 25 installation. On this workstation:
export JAVA_HOME=/usr/lib/jvm/java-25-openjdk-amd64
./gradlew clean build
```

The first run downloads Gradle, application and test dependencies. Once cached, `./gradlew clean build --offline` runs without network access. Tests include synthetic reference cases and saved OE price fixtures. Open `core/build/reports/tests/test/index.html` for the generated report.

The entry point is `au.nemlab.batterylab.BatterySimulation.run`, accepting an explicit battery, ordered windows, costs and complete price day. `FixedSchedule.plan` accepts only physical inputs and windows; `DispatchValidator` independently checks the resulting trajectory. Results include immutable inputs, unrounded dispatch/accounting and model/strategy versions. The engine is a library; it is not yet exposed through a simulation API. See the [engine contract](docs/project/features/battery-model-contract.md) for units, input rules and limits.

Local OE credentials remain in ignored configuration; never commit them. `OrderedHindsight.solve` provides the certified equal-window comparison using ojAlgo 57.3.0. Always inspect its outcome status: only `OPTIMAL` permits the optimal-within-tolerance label. Solver budgets are cooperative; worker-level hard termination is future work. Whole-day/unrestricted optimisation, display formatting and persistence remain outside this increment.

For the explicit solver experiment, run `./gradlew :core:hindsightBenchmark`. It rewrites the tracked benchmark CSV evidence; ordinary `build` does not. See [measurements and limitations](docs/project/evidence/engine/findings.md).

## Run the applications

After building, start these in separate terminals:

```sh
"$JAVA_HOME/bin/java" -jar api/build/libs/api.jar
"$JAVA_HOME/bin/java" -jar worker/build/libs/worker.jar
```

The API binds to `127.0.0.1:8080` by default. Check `http://127.0.0.1:8080/actuator/health`; it returns status UP without component details. `PORT` and `SERVER_ADDRESS` override the API bind settings. Use Ctrl+C to stop either application.

The worker is a non-HTTP application kept alive by Spring Boot. It has no schedules or jobs yet. Neither application needs a database or OE credentials to start. API health currently confirms application startup only, not ingestion/solver/database readiness. Business endpoints and administrator access controls arrive with later tasks.

For development, `./gradlew :api:bootRun` and `./gradlew :worker:bootRun` are also available. Automated packaged startup checks use Python 3:

```sh
python3 scripts/smoke_apps.py
```

That script starts each executable jar, checks API health and worker liveness, then stops its own processes. It uses a random loopback port for the API. Reports are under each module's `build/reports/tests/test/` directory.

## CI and module boundaries

[The backend workflow](.github/workflows/backend.yml) runs the locked build/tests and packaged startup checks on Java 25. Its action revisions and JDK version are pinned. The same commands have passed locally and from a clean source-only copy; no hosted workflow run or remote publication has occurred. If another CI provider is selected, reuse these commands.

`./gradlew verifyModuleBoundaries` rejects forbidden project dependencies. API and worker may depend on core/infrastructure; infrastructure may depend on core; core has no project dependencies. Infrastructure currently has no adapters or Spring beans. See [foundation verification](docs/project/evidence/foundation/findings.md).

Read [AGENTS.md](AGENTS.md) before working on this project.
