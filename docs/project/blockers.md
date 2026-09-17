# Blockers and open questions

Updated: 2026-09-13

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
- Evidence / attempts: No sample region/dates or launch history range are agreed. Energy-curious visitors and employers are a working audience assumption. GridReplay thresholds/grouping are proposals.
- Blocking scope: Can be resolved incrementally; does not require pausing all work for a full product specification.
- Next action / owner: Select explicit bounded sample dates/region in NEM-002 using reasonable defaults; refine launch claims from validation. Finalise detector parameters and demo audience before the corresponding UI work.
- Resolution: Not yet resolved.


- M1 follow-up: NEM-018 owns battery-population overlap, physical-window timing and renewable-detector methodology; NEM-020 owns promised coverage validation. See [grid gate](evidence/oe-validation/grid-gate.md). Solar curtailment and unexplained signed-gas attribution are excluded until validated.

<a id="blk-006"></a>

## BLK-006 — Hosting, public limits and Admin scope

- Identified: 2026-09-13
- Status: Open
- Impact: M5 assessment and M6 release.
- Affected tasks: [NEM-019](backlog.md#nem-019), [NEM-020](backlog.md#nem-020).
- Evidence / attempts: No hosting provider/budget, identity mechanism, public compute quotas, retention policy or decision to ship Admin UI is recorded.
- Blocking scope: Not an immediate blocker. Blocks final launch readiness if unresolved.
- Next action / owner: Use engine/runtime measurements to propose deployment limits and costs, rehearse operator commands, and decide Admin UI scope with the user before launch.
- Resolution: Not yet resolved.
