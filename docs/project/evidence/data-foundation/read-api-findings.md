# Stored-price read API verification

Date: 2026-09-18  
Scope: NEM-031, first implementation slice of NEM-014.

## What this proves

Visitors can discover which completed days have stored prices and retrieve those prices.
No import is triggered by a read. An unimported day, a missing observation, an explicit source
null and a numeric zero remain distinguishable. A correction updates the current response while
old stored snapshots retain their original data.

## Verification

Java 25 offline Gradle build passes 103 tests: the prior 97 plus six real HTTP/PostgreSQL read
API cases. Existing operator tests now run with both feature flags enabled, checking shared
wiring and unchanged authentication. The default API test verifies disabled reads return 404.

Read cases verify mixed complete/incomplete/unimported coverage, the maximum 31-day bound,
exact decimal strings and negative/zero values, 288 intervals, fixed UTC+10 boundaries across
Sydney's DST transition, current-revision corrections with preserved snapshots, no jobs or
retrieval attempts created by reads, disabled admin access in public-only mode, invalid inputs,
and safe storage errors. Coverage uses one SQL query; series capture a revision ID before reading
its immutable slots. Responses carry no-store caching policy.

An initial snapshot assertion compared BigDecimal scale rather than numeric value; corrected
the test to compare values. No engine or persistence change was needed for that assertion.
Packaged API and disabled-worker startup smoke checks also pass. Smoke mode explicitly disables
both database-backed API features. No live OE requests, persistent database migrations or deployment were performed.

## Remaining scope

Formal OpenAPI and reproducible generated frontend inputs are NEM-032; NEM-014 remains in
progress. Historical revision retrieval, simulation requests/results and GridReplay data APIs
remain later feature work. These tests establish endpoint behaviour, not broad historical
coverage or production load performance. Implementation remains uncommitted.
