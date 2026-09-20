# Typed stored-price integration — NEM-035

Implemented: 2026-09-18. Interrupted-session audit and closeout: 2026-09-20.
Changes committed: backend records `19834eb`, frontend `e963747`.

## Delivered

BatteryLab's public page now accepts a region and one completed market day, checks
coverage and displays all 288 intervals for imported days. It distinguishes complete,
incomplete and absent days; preserves decimal strings, negative/zero prices and gap
states; and shows fixed NEM UTC+10 times, source, unit, revision and retrieval timestamp.
It does not import data or run a simulation.

The backend contract snapshot is tied to commit
`7bdbd1ce74700454db123974a209f64250e3c7d1`, version 1.0.0, with per-file hashes. The
[client decision](../../decisions/013-typed-price-client.md) and
[frontend guide](../../../../../nemlab-ui/README.md) describe its update workflow,
cache behaviour, public request boundary and development/production routing.

## Verification

The interrupted session left passing logs for 34 browser checks and two real-backend
checks. Both suites passed again on 2026-09-20: 34 fixture/navigation cases and two real-backend cases. The local Chromium binary was missing at audit startup; reinstalling the pinned browser resolved that environment issue.

- `npm run check`: contract hashes and sibling comparison, Prettier, strict TypeScript,
  production build, and desktop/mobile browser fixtures.
- Browser coverage includes complete/incomplete/not-imported data, exact decimal strings,
  negative prices, null gaps, loading, invalid dates, HTTP/network/HTML/malformed-JSON
  failures and retry, corrected revision metadata, explicit cache refresh, keyboard
  navigation and responsive layouts. Requests omit planted cookies and Authorization.
- `JAVA_HOME=/usr/lib/jvm/java-25-openjdk-amd64 npm run test:live`: production browser
  through Vite proxy to the packaged Java API and a disposable PostgreSQL 18.6 database,
  with synthetic complete/incomplete days and an absent day. Both desktop/mobile cases
  passed in the original session and the closeout rerun. No response interception, OE calls or existing database.
- Deliberate snapshot edits and upstream contract drift were rejected by probes in the
  original session; originals were restored. No generated files were hand-edited.

## Limits

Frontend CI runs fixture checks; the cross-repository Java/PostgreSQL suite is an explicit
local/coordinated check, not a hosted CI claim. The test script applies SQL migrations to
its empty test database; backend tests own Flyway migration verification. Ordinary public
startup still needs a separately configured backend for price requests.

No chart, simulation submission, GridReplay workflow, deployment or full accessibility
certification is delivered. NEM-036 is the remaining frontend-foundation chart proof;
NEM-015 and M3 stay in progress until its criteria are met.

## Closeout

The implementation required no further application-code changes. Completed the missing
architecture/decision/feature records, task evidence and journal after fresh verification.
The real-backend mobile screenshot was reviewed: form and metadata fit the viewport;
the labelled interval table scrolls to retain exact values. Both test-owned processes
and the disposable database are cleaned up by the integration runner.
