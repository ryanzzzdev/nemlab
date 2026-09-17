# 004 — Java runtime and toolchain

Date: 2026-09-13  
Accepted: 2026-09-17  
Status: Accepted

## Context and decision

The original preference was Java 24. The user explicitly accepted Java 25 on 2026-09-17: “I like your recommendation of java 25. Use 25. And go ahead.” Use Java 25 LTS for compilation, tests and application runtime, without preview features.

Baseline selected for the first build:

| Component | Pin | Scope |
| --- | --- | --- |
| JDK | OpenJDK 25.0.4, build 7 | Java 25 language/toolchain; local Ubuntu build is `25.0.4+7-1-26.04-Ubuntu` |
| Gradle | 9.7.1 | Wrapper, with distribution checksum when created |
| Spring Boot | 4.1.1 | API and worker in M3; no Spring dependency in the battery engine |

The installed Ubuntu OpenJDK at `/usr/lib/jvm/java-25-openjdk-amd64` successfully reports the exact version above. Explicitly select it for the first build: the shell default currently points at Java 21. Eclipse Temurin 25.0.4+7 is the portable distribution baseline for future CI; provision and verify its artifact/checksum when CI is created. Patch upgrades are deliberate maintenance changes, not a permanent freeze at this patch.

## Compatibility evidence

Checked 2026-09-17 against primary sources:

- [Spring Boot requirements](https://docs.spring.io/spring-boot/system-requirements.html): Boot 4.1.1 supports Java 17–26 and Gradle 9.x.
- [Gradle compatibility](https://docs.gradle.org/current/userguide/compatibility.html): Java 25 compilation and running Gradle require 9.1.0 or newer.
- [Gradle releases](https://gradle.org/releases/): 9.7.1 is the current stable release shown.
- [Temurin support](https://adoptium.net/support/): Java 25 is LTS, with availability planned through at least September 2031; Java 24 reached end of support in September 2025. Distribution maintenance schedules differ.

NEM-009 subsequently verified a clean Java 25 core build with Gradle 9.7.1 and locked JUnit 6.1.3 dependencies, including an offline rerun. The checksum-pinned wrapper is checked in as a working-tree change. NEM-010 subsequently verified ojAlgo 57.3.0 on Java 25. NEM-011 subsequently verified Boot 4.1.1 application contexts and packaged API/worker startup; hosted CI remains unexecuted.

## Minimal engine build and follow-up

NEM-009 created a Gradle root and plain Java `core` module with focused tests, wrapper and locked test dependencies. No database, API, worker or frontend scaffolding is needed to prove the engine. NEM-010 selected and exercised ojAlgo 57.3.0 on Java 25; see [solver decision](007-hindsight-solver.md). NEM-011 introduces Boot applications and CI, rechecks maintained patches and records any updated pins before use.

## Alternatives and consequences

Java 24 matches the original request but has a shorter maintenance life. Java 21 is already the shell default but is not the accepted language baseline. Java 25 preserves the familiar Java implementation while providing an LTS maintenance path. No system-wide Java default was changed.

## Acceptance source

Java 25: explicit user instruction above. Specific build/version choices: agent selection under the instruction to proceed. Core build validation is complete in NEM-009; Boot application validation is complete in NEM-011; hosted CI execution remains pending a remote repository and push.

## References

[NEM-007](../backlog.md#nem-007), [BLK-002](../blockers.md#blk-002), [architecture](../architecture.md).
