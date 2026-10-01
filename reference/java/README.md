# Java reference implementation

This directory preserves the Java/Spring Boot backend as a runnable reference while the
active backend is rebuilt in Python. Moved here unchanged (plus path repairs) during
NEM-066; see [the rebuild plan](../../docs/project/python-backend-rebuild.md) and
[parity baseline](../../docs/project/evidence/python-rebuild/parity.md).

- Baseline: moved at backend revision `0d881bf9348486e470349e4c60fd77a905979c50`;
  Java source identical to plan baseline `e93142cc35aa8bdf1fc5722612a2c58a48aacbdc`.
- Modules: `core`, `infrastructure`, `api`, `worker` — same Gradle build, tests and jars.
- `ci/backend.yml` is a reference copy of the pre-move CI workflow; the active workflow
  is replaced during NEM-078.

## Path map (old → new)

| Before | Now |
| --- | --- |
| `core/`, `infrastructure/`, `worker/` | `reference/java/{core,infrastructure,worker}/` |
| `api/` sources, build file, README, lockfile | `reference/java/api/` — `api/contracts/` stays at the repo root |
| `build.gradle`, `settings.gradle`, `gradlew`, `gradlew.bat`, `gradle/` | `reference/java/` |
| `scripts/smoke_apps.py` | `reference/java/scripts/smoke_apps.py` |
| `.github/workflows/backend.yml` | reference copy at `reference/java/ci/backend.yml` |

Repaired references: module `build.gradle` files resolve evidence/contract paths via
`../../` to the repository root. `settings.gradle`, module lockfiles and the wrapper are
unchanged.

## Reference commands

Run from `reference/java/` with `JAVA_HOME` pointing at JDK 25
(e.g. `export JAVA_HOME=/usr/lib/jvm/java-25-openjdk-amd64`):

```sh
./gradlew clean build --offline --no-daemon   # tests + module boundaries + contract check
python3 scripts/smoke_apps.py                 # packaged api/worker startup
./gradlew :core:hindsightBenchmark            # writes ../../docs/project/evidence/engine/
./gradlew :infrastructure:parityExport        # writes ../../docs/project/evidence/python-rebuild/fixtures/
./gradlew :infrastructure:prices --args='migrate'   # operator CLI, DB per ../../.env.example
```

The contract check still validates `api/contracts/` at the repository root. Do not treat
this tree as the active runtime once the Python gates pass.
