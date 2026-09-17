# NEMLab

NEMLab explores Australia's National Electricity Market through historical analysis and experiments. BatteryLab compares simulated battery trading strategies; GridReplay helps visitors investigate notable market periods.

This is the backend project and the home of shared project documentation. The planned Java/Spring Boot backend has separate API and worker applications. The frontend will live in a separate repository.

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

The backend repository contains a plain Java battery-engine `core` module. API/worker applications, database and frontend are future work.

Use JDK 25 (verified locally with OpenJDK 25.0.4+7). The checked-in Gradle 9.7.1 wrapper verifies its distribution checksum; JUnit 6.1.3 and transitive test dependencies are locked. No globally installed Gradle or OE credentials are required.

```sh
# Point JAVA_HOME at your JDK 25 installation. On this workstation:
export JAVA_HOME=/usr/lib/jvm/java-25-openjdk-amd64
./gradlew clean build
```

The first run downloads Gradle and test dependencies. Once cached, `./gradlew clean build --offline` runs without network access. Tests include synthetic reference cases and saved OE price fixtures. Open `core/build/reports/tests/test/index.html` for the generated report.

The entry point is `au.nemlab.batterylab.BatterySimulation.run`, accepting an explicit battery, ordered windows, costs and complete price day. `FixedSchedule.plan` accepts only physical inputs and windows; `DispatchValidator` independently checks the resulting trajectory. Results include immutable inputs, unrounded dispatch/accounting and model/strategy versions. This is a library, not yet a runnable web application. See the [engine contract](docs/project/features/battery-model-contract.md) for units, input rules and limits.

Local OE credentials remain in ignored configuration; never commit them. `OrderedHindsight.solve` provides the certified equal-window comparison using ojAlgo 57.3.0. Always inspect its outcome status: only `OPTIMAL` permits the optimal-within-tolerance label. Solver budgets are cooperative; worker-level hard termination is future work. Whole-day/unrestricted optimisation, display formatting and persistence remain outside this increment.

For the explicit solver experiment, run `./gradlew :core:hindsightBenchmark`. It rewrites the tracked benchmark CSV evidence; ordinary `build` does not. See [measurements and limitations](docs/project/evidence/engine/findings.md).

Read [AGENTS.md](AGENTS.md) before working on this project.
