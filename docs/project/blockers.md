# Blockers and open questions

Updated: 2026-10-01

These records distinguish future decision gates from work that is blocked now. No failed implementation attempt is implied. Each record is Open until evidence and its resolution date are recorded. Task execution status belongs in the [backlog](backlog.md).

<a id="blk-001"></a>

## BLK-001 — OE access and price semantics

- Identified: 2026-09-13
- Status: Resolved
- Impact: M1 price gate; downstream ingestion and real-data simulations.
- Affected tasks: [NEM-002](backlog.md#nem-002), [NEM-003](backlog.md#nem-003), [NEM-004](backlog.md#nem-004).
- Evidence / attempts: No authenticated response has been tested in this project. Academic access is user-reported; credential availability, endpoint semantics and actual price coverage are unverified.
- Blocking scope: Blocks acceptance of real-data results, not synthetic design or sample planning.
- Next action / owner: The implementing agent selects samples and checks safe credential availability, then collects evidence. If access is unavailable, ask the user for secure configuration rather than including a key in the tracker.
- Update 2026-09-13: NEM-002 selected NSW1 and exact sample windows. Active environment variable names and NEMLab config-file inventory revealed no OE credentials. NEM-003 is blocked until a key is configured locally. No authenticated call was attempted. See [sample plan](evidence/oe-validation/sample-plan.md).
- Update 2026-09-13 23:00 AEST: Credential now configured; authenticated recent-price request succeeded. The 288-point grid passes checks, but query date_end behaved exclusively and physical interval labels still need confirmation. Access hurdle cleared; semantic gate remains open. See [findings](evidence/oe-validation/recent-price-findings.md).
- Update: Recent-day interval semantics resolved through four AEMO boundary comparisons and a corrected 288-interval sample. NEM-003 is Done. BLK-001 remains Open only for historical access/regime validation in NEM-004.
- Resolution: 2026-09-13 23:06 AEST — Historical access and sample/regime checks passed. [Price gate](evidence/oe-validation/price-gate.md) permits the two sampled NSW1 days; broader coverage remains BLK-005.

<a id="blk-002"></a>

## BLK-002 — Java version and build baseline

- Identified: 2026-09-13
- Status: Resolved
- Impact: M2 engine build and M3 scaffolding.
- Affected tasks: [NEM-007](backlog.md#nem-007), [NEM-009](backlog.md#nem-009), [NEM-011](backlog.md#nem-011).
- Evidence: User explicitly accepted Java 25 on 2026-09-17. Installed Java 25 reports 25.0.4+7; official Boot/Gradle documentation supports the selected baseline.
- Resolution: 2026-09-17 — [Decision 004](decisions/004-java-runtime.md) records pins and minimal build scope. NEM-009 subsequently verified the Java 25 core build/tests; NEM-010 subsequently verified ojAlgo compatibility.

<a id="blk-003"></a>

## BLK-003 — Grid and facility coverage

- Identified: 2026-09-13
- Status: Resolved
- Impact: M1 grid gate and M5 replay coverage.
- Affected tasks: [NEM-005](backlog.md#nem-005), [NEM-006](backlog.md#nem-006), [NEM-018](backlog.md#nem-018).
- Evidence / attempts: Documentation supports the concept, but metric/endpoint combinations, flow signs, historical coverage and metadata joins have not been sampled.
- Blocking scope: Blocks promising unsupported replay views; price-only engine work may continue.
- Next action / owner: The implementing agent samples matching windows and records supported series; narrow optional views when evidence is insufficient.
- Resolution: 2026-09-13 23:12 AEST — Sampled joins and battery representations checked; [grid gate](evidence/oe-validation/grid-gate.md) passes for observational scope with explicit timing/optional-metric exclusions. Broader coverage and methodology are tracked under BLK-005.


- Update 2026-09-13: Regional API coverage and hourly checks passed in NEM-005. NEM-006 must validate unit joins, optional metrics and the recorded battery-category/timing limitations. See [grid findings](evidence/oe-validation/grid/findings.md).

<a id="blk-004"></a>

## BLK-004 — Battery policy defaults and solver feasibility

- Identified: 2026-09-13
- Status: Resolved
- Impact: M2 and M4.
- Affected tasks: [NEM-008](backlog.md#nem-008), [NEM-009](backlog.md#nem-009), [NEM-010](backlog.md#nem-010), [NEM-016](backlog.md#nem-016).
- Resolution: 2026-09-17 — The [contract](features/battery-model-contract.md), tested core and [solver findings](evidence/engine/findings.md) establish a feasible, certified ordered-window comparison. M2 is complete for this scope.
- Follow-up: NEM-013 enforces worker concurrency and hard execution limits; NEM-020 validates public input/resource limits and final illustrative presets. Unrestricted whole-day optimisation remains optional/deferred and requires separate modelling and proof.

<a id="blk-005"></a>

## BLK-005 — Initial coverage, audience and event definitions

- Identified: 2026-09-13
- Status: Open
- Impact: M1 sample selection, M4 curated demo and M5 detection.
- Affected tasks: [NEM-002](backlog.md#nem-002), [NEM-016](backlog.md#nem-016), [NEM-018](backlog.md#nem-018), [NEM-020](backlog.md#nem-020).
- Evidence / attempts: M1 validated bounded NSW1 samples on 2023-09-11 and 2026-09-11; this does not establish complete catalogue/launch coverage. Energy-curious visitors and employers are a working audience assumption. GridReplay thresholds/grouping remain proposals until NEM-054 freezes them.
- Blocking scope: Can be resolved incrementally; does not require pausing all work for a full product specification.
- Next action / owner: NEM-054 (Done 2026-10-02) froze the NSW1 September-2023 window and the three v1 detector definitions — see [decision 020](decisions/020-gridreplay-scope-and-detectors.md) and the [coverage probe](evidence/m5-coverage/findings.md). Remaining open scope: promised launch coverage (NEM-020) and renewable/battery methodology exclusions. Renewable peaks and regional battery aggregation remain excluded until their methodology is evidenced.
- Resolution: Partially resolved 2026-10-02 — GridReplay v1 event definitions and initial coverage are frozen; launch-coverage breadth stays open under NEM-020.


- M1 follow-up: NEM-018 owns battery-population overlap, physical-window timing and renewable-detector methodology; NEM-020 owns promised coverage validation. See [grid gate](evidence/oe-validation/grid-gate.md). Solar curtailment and unexplained signed-gas attribution are excluded until validated.

<a id="blk-006"></a>

## BLK-006 — Production hosting and Admin setup inputs

- Identified: 2026-09-13; updated 2026-10-08.
- Status: Open.
- Impact: M6 external setup and M7 release; local implementation can proceed.
- Affected tasks: NEM-096, NEM-105, NEM-020.
- Evidence: Admin UI, roles, email sessions and retention defaults are now selected in decision 024. Hosting/budget, production origin/TLS, sender domain/email transport credentials and actual owner name/email remain unspecified.
- Next action: implement against captured local mail and explicit configuration; obtain owner identity at bootstrap and configure the selected email transport/sender before real invitations. NEM-020 verifies production mail delivery, quotas, backups/retention and deployed identity boundary. Do not guess credentials, create a default account or purchase services.
- Resolution: Admin scope portion resolved by NEM-093; deployment/setup inputs remain open.


<a id="blk-007"></a>

## BLK-007 — Hosted CI evidence for M3

- Identified: 2026-09-20
- Status: Open
- Impact: M3 exit criterion “CI runs relevant checks”.
- Affected tasks: [NEM-038](backlog.md#nem-038). Local M4 implementation proceeds at the user’s direction; hosted CI still gates formal M3 completion.
- Evidence: Both workflows exist and their checks have recorded local passes. Neither Git repository has a configured remote; no hosted run is recorded. See [exit review](evidence/foundation/m3-exit-review.md).
- Blocking scope: Formal M3 completion; no missing local implementation was identified by this review.
- Next action / owner: User supplies/authorises repository destinations and publication when ready; implementing agent then verifies hosted workflow runs and records commit/run links. No account creation or push is authorised by NEM-037.
- Resolution: Pending.


<a id="blk-008"></a>

## BLK-008 — Python parity and existing-data transition gates

- Identified: 2026-10-01.
- Status: Resolved.
- Impact: Python rebuild acceptance; not a blocker to starting NEM-065.
- Affected tasks: [NEM-069](backlog.md#nem-069), [NEM-070](backlog.md#nem-070), [NEM-076](backlog.md#nem-076), [NEM-080](backlog.md#nem-080).
- Evidence: Java uses ojAlgo-specific certificates/versions, Flyway V1–V3, immutable JSON results and JVM child limits. Python equivalents and populated-schema adoption have not yet been exercised. No failed attempt is implied.
- Next action / owner: Implementing agent captures baseline fixtures, proves HiGHS certificates/budgets, verifies Alembic adoption on a populated clone and measures enforced Python/native resource bounds. Follow the [rebuild plan](python-backend-rebuild.md); record specific failures separately if discovered.
- Blocking scope: Prevents claiming complete parity or cutting over until evidence passes; no user decision is currently needed for planning/scaffolding.
- Resolution: 2026-10-02 — NEM-069, NEM-070 and NEM-076 established the solver, schema-adoption and process-budget evidence. NEM-080 then closed the [parity matrix](evidence/python-rebuild/parity.md) and rehearsed populated-clone adoption, both-direction reads, post-switch writes and non-destructive rollback; see the [cutover rehearsal](evidence/python-rebuild/cutover-rehearsal.md). Hosted CI remains separately tracked in BLK-007.
