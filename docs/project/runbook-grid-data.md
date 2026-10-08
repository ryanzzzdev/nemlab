# GridReplay data loading runbook

Created: 2026-10-08
Scope: how an operator populates GridReplay — which endpoints load observations,
in what order, and how to monitor and recover. This is the tested manual path
(decision 021 defers the Admin UI); it is also the contract a future Admin UI
would orchestrate.

Pipeline: **grid import → price refresh → publish catalogue**. Phases are
separate because the stores are separate: grid observations land in
`grid_revision`, prices in `price_revision`, and a publication pins whichever
revisions exist at publish time into each event's replay snapshot.

Ordering matters. A publication over a window with no imported prices still
succeeds — run/spike detectors have nothing to detect and ramp snapshots pin
`price: null`. Republishing after prices arrive mints corrected event versions
(snapshots whose pinned context changed get a `version+1` under the same event
identity), so the safe recovery is always *import the missing data, then
republish* — never database edits.

## Prerequisites

- API running with `NEMLAB_ADMIN_ENABLED=true`, `NEMLAB_ADMIN_OPERATOR` and a
  `NEMLAB_ADMIN_TOKEN` (43–128 char base64url). Admin routes are not mounted
  without them.
- Worker running with `NEMLAB_GRID_IMPORT_ENABLED=true` and
  `OPEN_ELECTRICITY_API_KEY` set, plus `NEMLAB_WORKER_ENABLED=true` for price
  refreshes.
- Schema migrated to head (V4–V6 grid tables).
- Every mutating request needs `Authorization: Bearer $NEMLAB_ADMIN_TOKEN` and a
  unique `Idempotency-Key` header (publication is the exception — see below).
- Regions: NSW1, QLD1, SA1, TAS1, VIC1 — all supported end to end.

## Phase 1 — import grid observations

One job imports a bounded window of **1–31 completed market days** for one
region, day by day, with a durable checkpoint (`nextDay`). Market data (demand,
interconnector flows) is required; power-by-fueltech fetch failures are
recorded as `optionalFailures` without failing the day.

```sh
curl -X POST http://localhost:8080/api/admin/v1/grid-imports \
  -H "Authorization: Bearer $NEMLAB_ADMIN_TOKEN" \
  -H "Idempotency-Key: grid-QLD1-2023-09" \
  -H "Content-Type: application/json" \
  -d '{"region":"QLD1","startDay":"2023-09-01","endExclusive":"2023-10-01"}'
```

Response (202, `Location` header to the job):

```json
{"id":"…","region":"QLD1","startDay":"2023-09-01","endExclusive":"2023-10-01",
 "nextDay":"2023-09-01","status":"QUEUED","attempts":0,"optionalFailures":[],
 "availableAt":"…","diagnostic":null}
```

Monitor with:

- `GET /api/admin/v1/grid-imports?limit=50` — recent jobs
- `GET /api/admin/v1/grid-imports/{id}` — status + `nextDay` progress
- `GET /api/admin/v1/grid-imports/{id}/events` — audit trail (submission,
  claims, per-day commits, lease expiry, retries, terminal state)
- `POST /api/admin/v1/grid-imports/{id}/cancel` — revoke a running claim
  (audited)

Semantics:

- `endExclusive` must be ≤ today's NEM market date; only completed days are
  importable. A window longer than 31 days needs multiple jobs.
- Same `Idempotency-Key` + same window returns the existing job; same key with
  a different window returns `409 IDEMPOTENCY_CONFLICT`. Resubmitting an
  *active* duplicate window returns the existing logical job.
- Up to 20 jobs may be pending; beyond that the API returns `QUEUE_FULL` —
  retry after the queue drains.
- A failed or crashed job keeps `nextDay`; recovery is a **new job covering the
  remaining window with a new key**. Day saves deduplicate by content hash, so
  overlap is harmless. Lease expiry automatically reschedules a killed
  worker's job; the resumed run continues from `nextDay`, not day one.
- Permanent failures surface `INVALID_SOURCE_DATA_OR_CONFIGURATION` as the
  diagnostic after retries are exhausted (`attempts` reaches 3).
- Rate observed locally: roughly 2.5 s/day — a 30-day window ≈ 75 s.

## Phase 2 — refresh prices

Price detection (negative runs, spikes) and the replay's price series read from
`price_revision`, populated by the per-day refresh path — grid imports do not
fetch prices.

```sh
# one job per market day
for d in $(seq 0 29); do
  day=$(date -d "2023-09-01 +$d day" +%F)
  curl -X POST http://localhost:8080/api/admin/v1/price-refreshes \
    -H "Authorization: Bearer $NEMLAB_ADMIN_TOKEN" \
    -H "Idempotency-Key: px-QLD1-$day" \
    -H "Content-Type: application/json" \
    -d "{\"region\":\"QLD1\",\"day\":\"$day\"}"
done
```

Semantics:

- One market day per job; the job view carries `status`, `attempts`,
  `diagnostic`. List/status/events/cancel mirror the grid-import endpoints
  under `/api/admin/v1/price-refreshes`.
- Up to 1000 refresh jobs may be pending — a 30-day × 5-region sweep (150 jobs)
  fits comfortably; beyond the cap the API returns `QUEUE_FULL` — retry after
  the queue drains. (Windowed submission to collapse the fan-out is planned as
  NEM-092.)
- Same idempotency rules as grid imports.
- Prices are also refreshed on the scheduled cadence for recent days; this
  path is for backfilling historical windows.

## Phase 3 — publish the catalogue

One atomic publication per region+window runs the frozen v1 detectors over all
stored observations, mints immutable event versions with materialised replay
snapshots, and swaps the region's catalogue pointer — in a single
REPEATABLE READ transaction.

```sh
curl -X POST http://localhost:8080/api/admin/v1/grid-publications \
  -H "Authorization: Bearer $NEMLAB_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"region":"QLD1","startDay":"2023-09-01","endExclusive":"2023-10-01"}'
```

(No `Idempotency-Key` — every successful call creates a new publication row;
a republish is an explicit, meaningful operation.)

Response carries `id`, `region`, `startDay`, `endExclusive`,
`detectorVersion`, `eventCount`, `coverage`, `createdAt`. Inspection:

- `GET /api/admin/v1/grid-publications?limit=50` — publication history
- `GET /api/admin/v1/grid-publications/{id}` — detail including coverage

Semantics:

- Event dedupe: unchanged detector inputs *and* unchanged pinned context
  (every `days` revision in the snapshot) reuse the existing event version;
  drift mints `version+1` with a `supersedes` link. Old event IDs and their
  pinned snapshots remain readable forever — a shared replay link never
  breaks.
- Publication does not delete anything. Superseded versions are only visible
  through direct `GET /api/v1/events/{id}` reads.
- A day with incomplete demand coverage contributes no ramp event
  (`insufficient_coverage`), which is honest — not an error.

## Verify

```sh
curl -s "http://localhost:8080/api/v1/events?region=QLD1" | jq '.publication'
curl -s "http://localhost:8080/api/v1/events?region=QLD1&limit=5" | jq '.events[].id'
curl -s "http://localhost:8080/api/v1/events/{event-id}/replay" | jq '.manifest'
```

Each region's public catalogue pins to its own latest publication; regions are
independent (publishing QLD1 never touches NSW1's catalogue or saved links).

## Failure quick reference

| Symptom | Meaning | Action |
| --- | --- | --- |
| 401 on any admin call | missing/wrong token | check `NEMLAB_ADMIN_*` env |
| 404 on `/api/admin/…` | admin routes not mounted | `NEMLAB_ADMIN_ENABLED=true`, restart API |
| 400 naming a field/header | request validation | fix request; message names the missing part |
| 409 `IDEMPOTENCY_CONFLICT` | key reused with different payload | use a new key |
| `QUEUE_FULL` | too many pending jobs | wait for drainage, resubmit |
| `FAILED` + `INVALID_SOURCE_DATA_OR_CONFIGURATION` | source data invalid/unavailable for that window | inspect job events; resubmit a corrected/smaller window with a new key |
| job stuck RUNNING after worker restart | lease expiry will requeue (~5 min) | none — resumes from `nextDay` |
| catalogue published but price chart empty | prices imported after publication | republish the window (fixed since the context-pin dedupe change) |

## Admin UI contract (when built)

A future Admin app should orchestrate the same three phases — nothing here
requires a new backend surface:

- **Load-window flow**: region + date range → client-side chunking into ≤31-day
  grid-import submissions; then one refresh job per market day (respect the
  100-pending cap with a submit-on-drain loop); then a publish action once jobs
  succeed.
- **Status views**: job list/detail with `nextDay` progress and `attempts`;
  the `events` endpoint is the audit view (submission → claims → day commits →
  terminal).
- **Actions**: cancel a running import; resubmit remaining window after
  failure; publish/republish a window.
- **Feedback**: surface `optionalFailures`, `diagnostic`, and queue-full as
  states, not silent retries.
- **Constraints from decision 021**: the app is a *separate* bundle
  (`apps/admin`), never part of the public build; no operator token in the
  public app or a Vite env; authentication/session/CSRF requirements must be
  designed before browser implementation.

See also: [decision 021 — Admin UI deferred](decisions/021-admin-ui-deferred.md),
[NEM-063 rehearsal evidence](evidence/m5-ops-rehearsal.md),
[gridreplay feature spec](features/gridreplay.md).
