# NEM-039 — Simulation request preparation

Date: 2026-09-20. Implementation and records committed as `a151677`.

## Delivered

`SimulationRequest` preserves exact normalised decimals, validates energy ordering before
conversion to double, normalises round-trip efficiency through the existing engine,
and validates one pair of five-minute-aligned ordered windows in fixed NEM time.
It exposes field paths and stable validation codes. The [contract](../../features/simulation-request-contract.md)
records input bounds and canonical representation.

`ScenarioPreparation` reads current coverage once and then that immutable revision.
It returns exact prices, normalised parameters, engine/strategy/solver/profile versions,
cooperative limits and a SHA-256 input key. Preparation writes no snapshots or jobs;
NEM-040 will persist the captured revision and parameters with submission atomically.
Equivalent decimal scales and explicit derived legs share identity; corrections change it.

## Verification

- `JAVA_HOME=/usr/lib/jvm/java-25-openjdk-amd64 ./gradlew build --offline --no-daemon`: PASS.
- 116 tests, zero failures/errors/skips: core 54, infrastructure 33, API 15, worker 14.
  Core's seven new tests passed in the preceding targeted run and were up-to-date in
  the full build; infrastructure's six new PostgreSQL cases passed in the full build.
- Existing OpenAPI checks validate 46 actual HTTP responses across all seven operations.
- `JAVA_HOME=/usr/lib/jvm/java-25-openjdk-amd64 python3 scripts/smoke_apps.py`: packaged
  API and disabled worker startup checks PASS.
- Diff whitespace and changed-document local links checked.

New checks cover required fields, ambiguous/missing efficiency legs, numeric representation
budgets, bounds that differ only beyond double precision, idle sites, window alignment,
adjacency and next midnight, completed-day eligibility at the fixed UTC+10 boundary,
canonical equivalence, exact decimal preservation, and validation before database access.

Real disposable PostgreSQL tests cover unavailable/missing/source-null days, repeated imports,
changed revision identity, preservation of captured pre-correction prices and variation
of all site/cost/efficiency/window fields. Preparation leaves refresh jobs, snapshots and
backfills untouched. The historical OE fixture runs through the existing engine: fixed
margin 437.258414 AUD and certified hindsight 479.141462 AUD within 0.00001, matching M2.

The first targeted run found two invalid test fixture provenance hashes; these were
corrected to valid SHA-256 values. No application failure was hidden or skipped. The
sandbox initially prevented Gradle cache locking; approved test execution used existing
caches and disposable Docker containers. No live OE or persistent database was used.

## Limits and next work

No HTTP endpoint, simulation job schema, persisted scenario/result or new public workflow
exists yet. Input ceilings bound arithmetic and representation; they do not guarantee every
admitted scenario will pass the one-cent optimality proof. NEM-040 must retain solver
status and enforce external process bounds; NEM-041 owns HTTP parsing/status mapping and
contract generation. No frontend code changed and browser tests were not repeated.
Hosted CI remains unverified under NEM-038; local work proceeded at the user's direction.
