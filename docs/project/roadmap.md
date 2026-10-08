# NEMLab roadmap

Updated: 2026-10-08

The accepted product sequence is BatteryLab (M4), GridReplay (M5), Admin (M6), then launch (M7). The user separated Admin from GridReplay on 2026-10-08; Admin scope is now accepted in [decision 024](decisions/024-admin-experience-and-access.md). See [launch scope decision](decisions/001-product-and-launch-scope.md). Detailed behaviour and technical choices remain proposed where explicitly labelled.

M1 sampling is complete with bounded [price](evidence/oe-validation/price-gate.md) and [grid](evidence/oe-validation/grid-gate.md) gates. Individual task status belongs in the backlog. M2 now passes for the ordered-window comparison; see [engine evidence](evidence/engine/findings.md). The API/worker foundation now passes [NEM-011](backlog.md#nem-011); [NEM-012](backlog.md#nem-012) now implements the price-storage/backfill slice. [NEM-013](backlog.md#nem-013) is split into focused tasks: the durable queue is verified in NEM-028; NEM-029 adds verified worker scheduling/execution; NEM-030 verifies protected operator controls and completes this price-refresh package. NEM-031 implements public stored-price reads; NEM-032 verifies formal contracts and generated client inputs, completing NEM-014. NEM-015 is split into NEM-033–NEM-036: the separate frontend repository/tooling is verified in NEM-033; NEM-034 verifies public navigation and shell; NEM-035 verifies typed public price integration; NEM-036 verifies synchronised charts and completes NEM-015. NEM-037 has reviewed the aggregate M3 exit evidence: local foundation checks pass, while NEM-038 must verify hosted CI before M3 closes. See the [exit review](evidence/foundation/m3-exit-review.md). Optional unrestricted hindsight remains deferred. No delivery dates are committed; estimate after the data and engine exercises reveal the work involved.

| Milestone | Outcome | Status | Depends on |
| --- | --- | --- | --- |
| M1 — OE validation | Evidence for supported inputs and coverage | Complete | None |
| M2 — Battery-engine proof | Correct, reproducible strategies and feasible solver | Complete | M1 price gate; synthetic design can proceed alongside M1 |
| M3 — Shared foundation | Ingestion, jobs, persistence, API and frontend shells | In progress | M1 and M2 |
| M4 — BatteryLab | Complete simulation experience | Complete | M3 local foundation; hosted CI remains a separate open gate |
| Python backend rebuild | Verified Python parity with retained Java reference | Complete | Delivered Java baseline; before M5 |
| M5 — GridReplay | Working catalogue, replay, sharing and discovery | Complete (local feature milestone) | M4 and validated grid inputs |
| M6 — Admin | Agreed operator experience and supporting controls | Complete (local feature milestone) | M5 and existing operator APIs |
| M7 — Launch | Verified, operable public release | Planned | M6 outcome and launch gates |

## Python backend rebuild — complete

Status: Complete (2026-10-02). The user selected a complete Python rebuild on 2026-10-01 before continuing M5. The Python API/worker now run with no Java dependency; the parity matrix is closed and populated-clone adoption, both-direction reads, post-switch writes and non-destructive rollback are rehearsed — see the [parity gate](evidence/python-rebuild/parity.md) and [cutover rehearsal](evidence/python-rebuild/cutover-rehearsal.md). Preserved: repository/history, runnable Java reference, canonical docs, API/worker split and delivered functionality. See the [execution plan](python-backend-rebuild.md) and [NEM-065–NEM-080](backlog.md#python-rebuild-tasks).

Exit criteria: independent Python API/worker run with no Java dependency; existing HTTP/frontend behavior, domain correctness, durable recovery and immutable historical data/results pass the parity matrix; clean setup, populated-schema adoption and rollback are rehearsed; active runbooks/checks use Python. Hosted CI remains NEM-038 and deployment remains NEM-020. Completed M1/M2/M4 records remain historical Java-era evidence, not automatic Python verification.

Sequence: NEM-065 baseline → reference/scaffold → domain/solver/schema → ingestion/queues/APIs → simulation → tooling/frontend/cutover. Resume NEM-054 after NEM-080.

## M1 — OE validation

Scope: choose a sample region and exact dates; inspect safe credential configuration; validate recent and historical prices, matching grid series, and representative facility metadata/output. Sample optional inputs separately. Record sanitised evidence and findings rather than assuming documentation guarantees coverage.

Exit criteria:

- Recent and older price samples have documented units, timestamp labels, interval boundaries, duplicates, gaps, and actual tested dates.
- A price gate explicitly states whether BatteryLab can proceed and which dates/regimes it can use.
- Grid and facility findings identify supported replay inputs and excluded/uncertain ones.
- Intended launch coverage is distinguished from sampled coverage; outstanding expansion checks have owners/actions.

Tasks: [NEM-002](backlog.md#nem-002) through [NEM-006](backlog.md#nem-006). Missing optional metrics may narrow replay scope rather than hold up price-based engine work.

## M2 — Battery-engine proof

Scope: resolve Java/toolchain and model conventions, build an isolated Java domain implementation, evaluate a solver, and validate both strategies with synthetic and sampled prices. A minimal build here supports the proof; full API/worker infrastructure remains M3.

Exit criteria:

- Fixed-schedule policy is deterministic and does not inspect future prices.
- Both strategies enforce physical limits, charge/discharge exclusivity, and matching initial/final energy.
- Accounting and physical invariants pass independent checks, including negative-price cases.
- Small exact cases establish optimiser correctness; 288-interval runs establish measured runtime and resource limits.
- Solver status distinguishes proven optimal results, feasible incomplete results, and failures.

Tasks: [NEM-007](backlog.md#nem-007) through [NEM-010](backlog.md#nem-010).

## M3 — Shared foundation

Scope: establish two repositories, backend modules, frontend workspace, PostgreSQL migrations, OE ingestion, durable jobs, API contract and generated frontend client. Implemented runtime/build choices are recorded in [architecture](architecture.md); remaining UI libraries await their focused checks.

Exit criteria: a clean local setup can ingest a validated day, report coverage, submit work through the API, recover an interrupted job, and display API data in the frontend. CI runs relevant checks. Repeated ingestion does not duplicate observations. Stored simulation inputs remain reproducible after source refreshes.

Planning work packages: [NEM-011](backlog.md#nem-011) through [NEM-015](backlog.md#nem-015). All implementation packages are complete; [NEM-038](backlog.md#nem-038) owns the remaining hosted CI gate.

## M4 — BatteryLab

Scope: one market day, one aggregate site, fixed schedule versus hindsight, synchronised charts, financial breakdown, saved/shareable results, and methodology. See [feature specification](features/batterylab.md).

Exit criteria: a visitor can configure a valid scenario, follow job progress, inspect both results, and reopen the same immutable result from a link. Invalid inputs, missing data, failures and timeouts have clear states. Browser workflows and numerical regression checks pass.

Planning work packages: [NEM-016](backlog.md#nem-016), [NEM-017](backlog.md#nem-017). NEM-039–NEM-041 completed the simulation backend package NEM-016; NEM-042–NEM-045 delivered the NEM-017 visitor experience. The original exit criteria passed locally, verified by mocked browser suites and a live API/worker/PostgreSQL journey ending in an immutable result reopen. On 2026-09-24 the user added [NEM-046](backlog.md#nem-046) — visitor-triggered price refresh for missing days — as required BatteryLab scope; it landed on 2026-09-25 with bounded deduplicated visitor fetches, explicit pending/failed/limited states and a live real-stack verification of the terminal failure path, restoring the milestone to complete. Completion remains an internal milestone, not the public launch: hosted CI stays open under NEM-038 and launch gates under NEM-020.

## M5 — GridReplay

Status: **Complete as a local feature milestone**, reconciled 2026-10-08. The original real-data journey was recorded as delivered on 2026-10-02; discovery releases A+B followed on 2026-10-08. See the [state review](evidence/m5-state-review-2026-10-08.md) for evidence and the limits of this conclusion.

Delivered: versioned observations and events, a real catalogue/replay, filters and saved links, synchronized charts, BatteryLab handoff, Highlights/All events, scoped reasons/sorts, preview sparklines, price reversals and grouped negative episodes. The unusual-ramp detector is implemented but correctly reports insufficient baseline for the current September dataset.

Exit criteria for this local feature scope: repeatable coverage-aware events, reproducible replay data, a functioning catalogue→replay→BatteryLab journey, and verified discovery behavior. The initial Admin assessment was completed historically under NEM-019/NEM-063; Admin product work is now M6 and does not keep M5 open. Scope/sequence acceptance: [decision 023](decisions/023-milestone-separation.md).

NEM-018, NEM-059 and NEM-064 records are reconciled with delivered evidence. NEM-083–NEM-091 record discovery delivery. Known reduced-motion, chart-failure and maximum-window verification follow-ups are explicitly tracked in NEM-094 for M7; local feature completion is not a statement that all earlier aspirational acceptance wording or launch hardening has been verified. Additional prior demand history and cross-region v2 publication are data-operations follow-ups, not missing detector implementation. Renewable peaks remain outside this scope.

## M6 — Admin

Status: Complete locally (2026-10-08). The [Admin specification](features/admin.md) is delivered through NEM-095–107 and NEM-082; NEM-092 bounded price windows were already delivered. All M6 tasks are Done with recorded evidence — boundary/resilience verification in [NEM-106](backlog.md#nem-106), UI/exit review in [NEM-107](backlog.md#nem-107). Production deployment, hosted CI, real email delivery and launch gates carry to M7 explicitly unverified.

Scope: coverage-led separate Admin UI, embedded workflow guide, securely bootstrapped owner, verified/approved expiring read-only visitors, public Admin entry, safe operational reads, bounded imports/recovery and explicit v2 publication. Existing API/worker/jobs remain the execution path. Decision 024 supersedes the earlier UI deferral; two human roles and email-link sign-in are selected defaults. NEM-082 (grid coverage read) is delivered; NEM-095 identity storage is in progress.

Sequence: NEM-095 identity → NEM-096 sessions/mail → NEM-097 permissions → NEM-098 requests/grants and NEM-099 reads (with NEM-082) → NEM-100 console → NEM-101 entry/auth, NEM-102–103 load workflow and NEM-104 access UI → NEM-105 public entry/runbook → NEM-106 verification → NEM-107 visual/exit review. Independent API slices may proceed concurrently once their dependencies are satisfied.

Exit criteria: owner bootstrap and full operator journey verified; visitor request/verification/approval/sign-in/revocation works; all backend capabilities and viewer redaction tested; bounded load/recovery and explicit publication preserve links; guide explains v2 and Highlights accurately; local integrated and responsive/accessibility checks pass with recorded evidence. Scope planning alone does not complete M6. Provider credentials/owner identity are setup inputs, not default secrets; production deployment and hosted verification remain M7.

## M7 — Launch readiness and release

Scope: hosting decision, public request/resource limits, administrator authentication, observability, backups and restore rehearsal, deployment/rollback instructions, methodology and attribution, coverage validation, and accessible browser journeys across both products.

Exit criteria: launch coverage claims match verified data; end-to-end smoke checks pass in the deployment environment; refresh/retry and recovery procedures work; resource budgets and failure alerts are documented; the agreed release is ready for deployment under the user's publication authorisation.

Planning work package: [NEM-020](backlog.md#nem-020), including [NEM-094](backlog.md#nem-094) for carried GridReplay hardening evidence. M3 hosted CI remains an explicit NEM-038 gate before public launch. Hosting provider, budget and release date are open, not assumed.

## Deferred scope

WEM, household tariffs, FCAS revenue, forecasting, annual optimisation, renewable economics, flexibility atlas, and generator observatory are outside this launch. Record future requests in the backlog instead of silently expanding these milestones.


## GridReplay discovery refinement — accepted 2026-10-08

Follow-up to the working GridReplay feature; not a replacement for original M5 acceptance or a declaration of hosted launch readiness. [NEM-083–NEM-091](backlog.md#gridreplay-discovery-tasks) deliver the [accepted discovery plan](features/gridreplay-discovery.md): Release A corrects duration and adds Highlights/All events, whole-publication sorting/filtering, clear card reasons and bounded previews; Release B calibrates and implements unusual ramps, price reversals and related negative episodes. Preserve the demo's flat grid and all existing saved events. **Delivered 2026-10-08** (backend `5e01125`, nemlab-ui `67c1cd6`/`40ff212`/`9ecabd1`, decision [022](decisions/022-detector-v2-definitions.md)); both releases verified, NSW1 v2 publication `232be228` live. Reference-history gaps mean unusual ramps currently report `insufficient_baseline` — importing ~90 days of prior demand history is a separate bounded operator task. Admin, hosting and existing coverage follow-ups retain their own task status.
