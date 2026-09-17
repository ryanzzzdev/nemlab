# NEM-011 — Backend application foundation

Date: 2026-09-17

## Delivered scope

Four Gradle modules: core (existing battery engine), infrastructure (adapter boundary, currently no implementation), API (Spring MVC plus Actuator) and worker (non-web Spring Boot application). Applications are packaged independently. Java 25 and Boot 4.1.1 are pinned; application dependencies are locked. No database driver, ingestion or scheduled job is introduced by this task.

The API defaults to loopback port 8080, exposes only the health Actuator endpoint, and hides health component details. The worker's `spring.main.keep-alive=true` keeps it running without requiring an HTTP server or a fake scheduled task. Their component scans stay in their own application packages; future infrastructure beans must be registered explicitly.

## Verification

- `JAVA_HOME=/usr/lib/jvm/java-25-openjdk-amd64 ./gradlew build --write-locks --no-daemon`: passed after initial dependency resolution and correction of one health test expectation.
- **49 tests passed**, zero failures/errors/skips: 47 engine tests plus one API HTTP test and one worker-context test.
- The first API test expected exactly `{"status":"UP"}`. Boot also returns health group names; the corrected assertion parses JSON and checks status and absence of component/detail payloads. This was a test expectation issue, not an application-startup failure.
- `python3 scripts/smoke_apps.py`: both executable jars start; API responds on a randomly allocated loopback port; worker remains alive without web dependencies or schedules. Child processes are terminated after checks, with forced cleanup if necessary.
- A temporary Gradle init script injected core -> api. `verifyModuleBoundaries` rejected it with `Forbidden dependency: core -> api`; no repository dependency was changed by the probe.
- Copied only source/configuration files into a fresh temporary directory, excluding `.git`, `.gradle`, generated builds and `.env`. `./gradlew clean build --offline --no-daemon` and packaged smoke checks both passed there. This proves a clean working-directory build using the machine's already populated Gradle cache; it is not a hosted CI run or a test with an empty dependency cache.

## CI

The [workflow](../../../../.github/workflows/backend.yml) targets GitHub Actions on ubuntu-24.04 with Temurin 25.0.4+7, a 15-minute job timeout and read-only repository permission. Official checkout and setup-java revisions were resolved from their published GitHub tag references. It runs the same build and smoke commands verified locally. Hosted execution is pending a remote repository and push; no push or remote configuration was performed.

## Remaining scope

Health currently means the application started, not that market data, database or job infrastructure is operational. Worker jobs, leases, retry handling, scheduling, operator access controls and simulation hard timeouts remain NEM-013. PostgreSQL/Flyway and ingestion belong to NEM-012; business API contracts belong to NEM-014. Frontend remains a separate repository. M3 is still in progress.

See [README](../../../../README.md) for commands, [architecture](../../architecture.md) for boundaries and [NEM-011](../../backlog.md#nem-011) for task evidence.
