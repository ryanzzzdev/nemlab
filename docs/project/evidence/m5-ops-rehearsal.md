# M5 operator rehearsal — GridReplay

Date: 2026-10-02. Live compose stack (PostgreSQL, `nemlab-api` :8080,
`nemlab-worker` all features on), `NEMLAB_ADMIN_TOKEN` set from `.env`.
Database contains the real NSW1 2023-09 import + publication plus the
rehearsal jobs below.

## Commands exercised (all `curl` against `/api/admin/v1/*`)

| Operation | Result |
| --- | --- |
| `GET` grid-imports / grid-publications / price-refreshes without `Authorization` | 401 |
| Same three with a wrong bearer token | 401 |
| `POST /grid-imports` NSW1 2023-09-01..10-01, `Idempotency-Key: rehearsal-dedupe-1` | 202, job `56fe8ce9` QUEUED → SUCCEEDED |
| Same key + same body again | Same job id returned — no duplicate work |
| Same key, different window | `IDEMPOTENCY_CONFLICT` |
| New key, identical still-active window | Returned the existing job `56fe8ce9` (active-window dedupe) |
| New key, overlapping sub-window 09-10..09-20 | New job `7bf80ae8` QUEUED |
| `POST /grid-imports/{7bf80ae8}/cancel` while queued | CANCELLED, `CANCELLED_BY_OPERATOR`; audit `SUBMITTED → CANCELLED` |
| `POST /grid-imports` 1998-12-01..05 (pre-NEM) | Job `4c870eb3` → FAILED `INVALID_SOURCE_DATA_OR_CONFIGURATION` attempt 1, no retry (non-retryable code) |
| SIGKILL worker mid-import (job `dcc95743`, 4/5 days committed, `nextDay` 2023-10-05) | Lease expired at ~300s → `RETRY_SCHEDULED LEASE_EXPIRED`; restarted worker re-claimed, resumed at checkpoint day, SUCCEEDED attempt 2 |
| Resubmit the failed 1998 window under a new key | New job `0a4e4825` → FAILED again, deterministically |
| `POST /grid-publications` NSW1 Sept-2023 (repeat) | New publication `6f01dffc`, 99 events; event ids unchanged |
| `GET /api/v1/events/{47af4f63}` after republication | Still readable, v1 |
| `GET …/replay` after republication | Original snapshot intact — `price[210] = 16599.89`, `demand[210] = 8787.05` |

## Semantics confirmed

- Job-level dedupe: `Idempotency-Key` replays return the same job;
  key reuse on a different window is rejected; identical active windows
  dedupe to the running job.
- Revision-level dedupe: the re-import wrote no new grid/price revision
  rows for identical content (content-addressed revisions).
- Retry classes: retryable failures schedule `RETRY_SCHEDULED` with
  `30s × attempts` backoff up to 3 attempts; permanent diagnostics fail
  immediately; lease expiry requeues and resumes from `next_day`.
- **No in-place retry endpoint exists.** Manual recovery is a new
  `POST` under a fresh `Idempotency-Key`; the audit shows both jobs.
- Cancellation clears the claim fence, so an in-flight child cannot
  commit after cancellation.
- Publication is atomic: a repeat publish mints a new publication id
  while identical detections dedupe and old event/replay links keep
  their pinned evidence.

## Fixes and gaps

- Fixed during rehearsal: a missing `Idempotency-Key` header returned a
  generic `INVALID_REQUEST`; admin-path validation errors now name the
  missing field (`Missing header 'idempotency-key'`). Public-path
  messages unchanged. (`api/errors.py`)
- Gap: no grid-observation coverage endpoint — operators cannot inspect
  which grid days/series are stored without creating a publication
  (publication bodies and job status are the only views). Split to
  NEM-082.
- Pain point: crash recovery waits one 300s lease before requeue — by
  design; acceptable for bounded imports.
