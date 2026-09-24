# NEMLab roadmap

Updated: 2026-09-21

The accepted product sequence is BatteryLab, then GridReplay, then public launch. Admin is assessed before launch. See [launch scope decision](decisions/001-product-and-launch-scope.md). Detailed behaviour and technical choices remain proposed where explicitly labelled.

M1 sampling is complete with bounded [price](evidence/oe-validation/price-gate.md) and [grid](evidence/oe-validation/grid-gate.md) gates. Individual task status belongs in the backlog. M2 now passes for the ordered-window comparison; see [engine evidence](evidence/engine/findings.md). The API/worker foundation now passes [NEM-011](backlog.md#nem-011); [NEM-012](backlog.md#nem-012) now implements the price-storage/backfill slice. [NEM-013](backlog.md#nem-013) is split into focused tasks: the durable queue is verified in NEM-028; NEM-029 adds verified worker scheduling/execution; NEM-030 verifies protected operator controls and completes this price-refresh package. NEM-031 implements public stored-price reads; NEM-032 verifies formal contracts and generated client inputs, completing NEM-014. NEM-015 is split into NEM-033–NEM-036: the separate frontend repository/tooling is verified in NEM-033; NEM-034 verifies public navigation and shell; NEM-035 verifies typed public price integration; NEM-036 verifies synchronised charts and completes NEM-015. NEM-037 has reviewed the aggregate M3 exit evidence: local foundation checks pass, while NEM-038 must verify hosted CI before M3 closes. See the [exit review](evidence/foundation/m3-exit-review.md). Optional unrestricted hindsight remains deferred. No delivery dates are committed; estimate after the data and engine exercises reveal the work involved.

| Milestone | Outcome | Status | Depends on |
| --- | --- | --- | --- |
| M1 — OE validation | Evidence for supported inputs and coverage | Complete | None |
| M2 — Battery-engine proof | Correct, reproducible strategies and feasible solver | Complete | M1 price gate; synthetic design can proceed alongside M1 |
| M3 — Shared foundation | Ingestion, jobs, persistence, API and frontend shells | In progress | M1 and M2 |
| M4 — BatteryLab | Complete simulation experience | In progress | M3 local foundation; hosted CI gate still open |
| M5 — GridReplay and Admin assessment | Replay experience and an explicit Admin scope decision | Planned | M4 and validated grid inputs |
| M6 — Launch | Verified, operable release of both products | Planned | M5 |

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

Planning work packages: [NEM-016](backlog.md#nem-016), [NEM-017](backlog.md#nem-017). At the user’s direction, local M4 work proceeds while hosted CI remains outstanding for M3. NEM-039–NEM-041 complete the simulation backend package NEM-016. NEM-017 frontend delivery is split into NEM-042–NEM-045: product layout/appearance, scenario form/lifecycle, comparison/charts and saved-result acceptance. No completed visitor journey is implied. Completion is an internal milestone, not the public launch.

## M5 — GridReplay and Admin assessment

Scope: a focused catalogue, three proposed event types, one polished replay, and navigation into BatteryLab. Validate region coverage before expanding. Assess Admin based on actual operational workflows.

Exit criteria: event results are repeatable and coverage-aware; linked charts align; observations do not imply unsupported causal claims; a replay can open the corresponding BatteryLab day. Record whether Admin UI is included or deferred, with an operational alternative if deferred.

Planning work packages: [NEM-018](backlog.md#nem-018), [NEM-019](backlog.md#nem-019).

## M6 — Launch readiness and release

Scope: hosting decision, public request/resource limits, administrator authentication, observability, backups and restore rehearsal, deployment/rollback instructions, methodology and attribution, coverage validation, and accessible browser journeys across both products.

Exit criteria: launch coverage claims match verified data; end-to-end smoke checks pass in the deployment environment; refresh/retry and recovery procedures work; resource budgets and failure alerts are documented; the agreed release is ready for deployment under the user's publication authorisation.

Planning work package: [NEM-020](backlog.md#nem-020). Hosting provider, budget and release date are open, not assumed.

## Deferred scope

WEM, household tariffs, FCAS revenue, forecasting, annual optimisation, renewable economics, flexibility atlas, and generator observatory are outside this launch. Record future requests in the backlog instead of silently expanding these milestones.
