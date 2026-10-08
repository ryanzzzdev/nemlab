# GridReplay data loading runbook

Created: 2026-10-08
Updated: 2026-10-08 — reconciled for the delivered Admin UI (NEM-105): browser
load/publish workflow, browser-vs-automation identity, explicit v2 publication.
Scope: how an operator populates GridReplay — which endpoints load observations,
in what order, and how to monitor and recover. The owner does this in the
browser Admin console; the curl path below remains the tested automation path
and the contract the UI orchestrates.

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

## Browser path — the Admin console

The delivered way to run this pipeline is the Admin UI at `/admin`, a separate
bundle on the same origin. Sign-in is an emailed single-use link — request one
at `/admin/sign-in` for an account the owner has approved (or the bootstrap
owner). The console mirrors this runbook:

- **Coverage** answers what is stored before loading (same read as the curl
  example below).
- **Load data** reviews a ≤366-day scope, then creates a resumable load
  operation that dispatches ≤31-day chunks — grid phase first, then prices —
  with explicit per-chunk dispatch, pause and resume. It never publishes.
- **Jobs** shows every bounded submission, checkpoints, attempts and audit
  events; owner can cancel active imports and "Submit again" for the remaining
  window after failure.
- **Publications** previews coverage for a ≤31-day scope, requires an owner
  acknowledgement for incomplete days, then publishes explicitly — **v2 is the
  default suite** (v1 is an advanced option). Each publish carries a caller
  attempt key so a lost response reconciles against the recorded run instead
  of silently republishing.
- **Access** is where the owner approves verified requests, extends or revokes
  viewer grants. Baseline demand history for ramp detection is an explicit
  separate import, never silently fetched.

Humans use the browser session; automation uses the bearer token below. The
two are separate credentials — a browser request that also presents a bearer
is rejected, and the UI never stores a credential.

## Prerequisites

- API running with `NEMLAB_ADMIN_ENABLED=true`, `NEMLAB_ADMIN_OPERATOR`,
  `NEMLAB_ADMIN_TOKEN` (43–128 char base64url) and `NEMLAB_ADMIN_BASE_URL`
  (the Admin UI origin+path used in sign-in links). Admin routes are not
  mounted without them.
- Browser path additionally needs a bootstrapped owner
  (`python -m nemlab_infrastructure.admin bootstrap-owner`, see
  [infrastructure README](../../infrastructure/README.md#admin-identity)) and
  the worker mail drain so sign-in links actually send
  (`NEMLAB_MAIL_ENABLED`, `NEMLAB_MAIL_DIR`).
- Worker running with `NEMLAB_GRID_IMPORT_ENABLED=true` and
  `OPEN_ELECTRICITY_API_KEY` set, plus `NEMLAB_WORKER_ENABLED=true` for price
  refreshes.
- Schema migrated to head. Detector v2 publication additionally requires the
  detector-v2 migration (V7 or current head); the identity/load-operation
  tables need V8–V10 (all included in `migrate`).
- Every mutating automation request needs
  `Authorization: Bearer $NEMLAB_ADMIN_TOKEN` and a unique `Idempotency-Key`
  header (publication is the exception — see below). Browser sessions supply
  their own cookie + CSRF instead.
- Regions: NSW1, QLD1, SA1, TAS1, VIC1 — all supported end to end.

## Phase 1 — import grid observations

Inspect what is already stored before submitting — the coverage read answers
per day and per series without creating a publication:

```sh
curl "http://localhost:8080/api/admin/v1/grid-coverage/QLD1?start=2023-09-01&endExclusive=2023-10-01" \
  -H "Authorization: Bearer $NEMLAB_ADMIN_TOKEN"
```

Each day reports `availability` over the required market series
(`NOT_IMPORTED`/`PARTIAL`/`COMPLETE`), a `series` list with the three market
metrics always present plus any stored power fueltech series, and per-series
revision/observation counts. Bounds match the other operator reads: 1–31
completed market days since 2021-10-01.

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
# one windowed submission fans out to a job per market day
curl -X POST http://localhost:8080/api/admin/v1/price-refreshes \
  -H "Authorization: Bearer $NEMLAB_ADMIN_TOKEN" \
  -H "Idempotency-Key: px-QLD1-2023-09" \
  -H "Content-Type: application/json" \
  -d '{"region":"QLD1","startDay":"2023-09-01","endExclusive":"2023-10-01"}'
```

A window submission returns `202` with `{"jobs": [...]}` — one job per market
day, in day order. The single-day form `{"region":"…","day":"…"}` still works
and returns the job with a `Location` header as before.

Semantics:

- Window bounds: 1–31 completed market days (same rule as grid imports). A
  failure mid-window rolls the whole submission back — never a partial set.
- Each day is an independent `refresh_job` — it queues, retries, cancels and
  audits exactly like a single-day submission.
- Idempotency: the bare key pins the window — resubmitting the identical
  window returns the same job set; the same key with a different window or
  region returns `409 IDEMPOTENCY_CONFLICT`. Internally each day derives key
  `{key}:{day}`, so window jobs also dedup onto a day already queued by a
  single-day request.
- Up to 1000 refresh jobs may be pending; beyond the cap the API returns
  `QUEUE_FULL` — retry after the queue drains.
- Same idempotency rules as grid imports.
- Prices are also refreshed on the scheduled cadence for recent days; this
  path is for backfilling historical windows.

## Phase 3 — publish the catalogue

One atomic publication per region+window runs the chosen detector suite over
all stored observations, mints immutable event versions with materialised
replay snapshots, and swaps the region's catalogue pointer — in a single
REPEATABLE READ transaction. The Admin UI submits `"detectorSuite":"v2"`
explicitly (v1 remains for compatibility); a bare API call defaults to v1.

```sh
curl -X POST http://localhost:8080/api/admin/v1/grid-publications \
  -H "Authorization: Bearer $NEMLAB_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"region":"QLD1","startDay":"2023-09-01","endExclusive":"2023-10-01","detectorSuite":"v2","attemptKey":"run-2023-09-a"}'
```

(No `Idempotency-Key` — every successful call creates a new publication row;
a republish is an explicit, meaningful operation. `attemptKey` is optional
caller correlation recorded on the detection run: it reconciles a lost
response via `GET /api/admin/v1/grid-publications/attempts`, it never
deduplicates.)

Response carries `id`, `region`, `startDay`, `endExclusive`,
`detectorVersion`, `eventCount`, `coverage`, `createdAt`. Inspection:

- `GET /api/admin/v1/grid-publications?limit=50` — publication history
- `GET /api/admin/v1/grid-publications/{id}` — detail including coverage
- `GET /api/admin/v1/grid-publications/attempts` — detection-run history with
  actor and `attemptKey`, for reconciling a lost publish response

A span longer than 31 days is deliberately *not* auto-published: publish each
≤31-day window explicitly — the most recent publication wins the region's
latest pointer; it does not append monthly catalogues.

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
| 401 on any admin call | missing/wrong token, or an expired/consumed session | automation: check `NEMLAB_ADMIN_*` env; browser: request a fresh sign-in link |
| 403 on a browser decision | capability or recent-auth failure | viewers are read-only; owner decisions need a sign-in from the last 15 minutes |
| 409 `ACCESS_CONFLICT` on a decision | request/grant already decided or stale version | refresh the view — the other decision already committed |
| 404 on `/api/admin/…` | admin routes not mounted | `NEMLAB_ADMIN_ENABLED=true`, restart API |
| 400 naming a field/header | request validation | fix request; message names the missing part |
| 409 `IDEMPOTENCY_CONFLICT` | key reused with different payload | use a new key |
| `QUEUE_FULL` | too many pending jobs | wait for drainage, resubmit |
| `FAILED` + `INVALID_SOURCE_DATA_OR_CONFIGURATION` | source data invalid/unavailable for that window | inspect job events; resubmit a corrected/smaller window with a new key |
| job stuck RUNNING after worker restart | lease expiry will requeue (~5 min) | none — resumes from `nextDay` |
| catalogue published but price chart empty | prices imported after publication | republish the window (fixed since the context-pin dedupe change) |

## Admin UI (delivered)

The Admin app orchestrates the same three phases — no new backend surface was
needed beyond the bounded console reads and load-operation metadata:

- **Load-window flow**: region + ≤366-day range → one resumable load
  operation; explicit dispatch submits ≤31-day grid chunks then ≤31-day price
  windows with queue backpressure. Pause stops new submissions without
  cancelling queued children; resume reconciles via deterministic child keys.
- **Status views**: job list/detail with `nextDay` progress and `attempts`;
  the `events` endpoint is the audit view (submission → claims → day commits →
  terminal).
- **Actions**: cancel a running import; submit the remaining window as a new
  bounded submission after failure; publish/republish a ≤31-day window.
- **Feedback**: `optionalFailures`, `diagnostic` and queue-full
  (`backpressured`) are states, not silent retries; publish attempts carry a
  caller correlation key for lost-response reconciliation.
- **Constraints (decision 021, kept)**: the app is a *separate* bundle
  (`apps/admin` served at `/admin`), never part of the public build; no
  operator token or secret in either bundle or a Vite env. Browser
  authentication is email-link sessions with CSRF + same-origin checks; the
  bearer token below is automation-only.

See also: [decision 021 — Admin UI deferred](decisions/021-admin-ui-deferred.md) (superseded by M6 delivery),
[NEM-063 rehearsal evidence](evidence/m5-ops-rehearsal.md),
[gridreplay feature spec](features/gridreplay.md).
