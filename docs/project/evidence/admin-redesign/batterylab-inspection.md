# BatteryLab inspection acceptance review — 2026-10-10

NEM-123 evidence against the [BatteryLab Admin specification](../../features/admin-batterylab.md). Review run on the real stack: API :8080, PostgreSQL with V11 applied, worker idle, admin dev server :5274, seeded owner session. Screenshots in `batterylab-inspection/`; the workspace shell, panes, drawers and access surfaces were already reviewed in [m6-review](m6-review.md) and are not repeated.

## Suites

| Suite | Result |
|---|---|
| Backend pytest (api + infrastructure + worker) | 585 passed |
| ruff / mypy / lint-imports | clean |
| OpenAPI verification | 204 responses validated, 50 operations |
| Public browser suite | 126 passed |
| Admin browser suite | 31 passed |
| Admin + public builds | clean |

## Real-data journeys

- **Catalogue → inspector** (`s1-1440-list`, `s4-1440-inspector`): `GET /api/admin/v1/simulations` under an owner session returns 11 rows for the scoped NSW1 window with server-side status counts (0 queued / 0 running / 11 succeeded / 0 failed). Selecting `7da8a73b` renders the detail projection: exact decimal capacity/power strings (`2`, `1`), verbatim stored scenario, OPTIMAL solver with objective/upper bound/absolute gap, per-strategy accounting for fixed/threshold/hindsight, and provenance showing the pinned revision matching the current revision.
- **Legacy lifecycle honesty**: every stored row predates V11, so `lifecycle.recorded` is `false` and the UI prints "Execution history was not recorded for this job" rather than inventing events (`s9-keyboard`, bottom pane). No attempt duration is shown without a matched CLAIMED→terminal pair.
- **Shared price readiness** (`coverage-prices`): the Prices column and inspector readiness section resolve from the public `/api/v1/prices/{region}/coverage` endpoint — every scoped day reports Complete with the current revision; "Simulations for this day" lists the same-day records.
- **Real-data defects found and fixed**: Java-era requests carry `efficiency: {charge, discharge, roundTrip: null}` — the scenario renderer printed "round-trip null"; now renders the leg values (visible in `s4`/`s5`). The admin dev proxy whitelisted only `/api/admin|auth|access`, so the shared price read 404'd on the real stack (browser mocks had hidden this); `/api/v1/prices` is now proxied, matching production same-origin serving (`nemlab-ui` commit `2b10a04`).

## Viewport / theme / density matrix

All on the new Simulations view unless noted; every pass reported zero horizontal overflow and no console/page errors.

| Check | Result |
|---|---|
| 1440×900 catalogue and inspector | `s1`, `s4` |
| 1280×720 | rail collapses to icon strip, filters wrap cleanly — `s2` |
| 1920×1080 | `s3` |
| Dark theme | inspector readable, chips and accounting table tinted — `s5` |
| Compact density | `s6` |
| Comfortable density | `s7` |
| 720×450 at 2x scale (≈200% zoom) | zero overflow — `s8` |
| Keyboard | focus grid → ArrowDown → Enter selects the second row, inspector + activity swap — `s9` |

## Security and contract coverage (suite-verified)

- Identity matrix on both simulation endpoints: anonymous 401, applicant/viewer/owner cookie sessions, bearer automation, expired and revoked grants denied, dual cookie+bearer credentials rejected (`test_admin_simulations.py`).
- Catalogue bounds: scope rejection beyond 31 days / future days, status/strategy filters composed with counts, keyset determinism under identical `created_at` timestamps, malformed and foreign-scope cursors rejected (`test_simulation_catalogue.py`).
- Exactness: scenario decimals emitted as strings; accounting numeric per contract; no result payload decode in the catalogue page query.
- Frontend: URL-restored filters/selection, out-of-scope direct ID, not-recorded lifecycle, owner-only refresh, viewer read-only (`tests-admin/`).

## Honest limitations

- All local rows predate V11, so the *recorded* lifecycle path is verified by worker/integration tests rather than a live post-migration submission; the live evidence covers the `recorded: false` branch.
- Corrected-price immutability rests on the V3 immutable triggers (suite-tested) and the pinned-vs-current comparison verified live as `matches`; no fresh corrective refresh was submitted during this review.
- Viewer desktop journey is covered by browser tests, not a second live session.

## Verdict

NEM-117–122 implementation verified end-to-end on real data; the additional M6 exit criteria (bounded authorized catalogue, exact result/provenance inspection, truthful lifecycle, shared price readiness, public-result handoff) pass. M7 deployment/launch gates remain open and unverified.
