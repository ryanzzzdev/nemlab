# GridReplay

Updated: 2026-09-13  
Status: Proposed detailed specification; delivery before launch is accepted.

## Visitor outcome

Discover an interesting historical NEM period, inspect aligned evidence, and open its region/day in BatteryLab. Start with one validated region and a bounded catalogue period, expanding only after coverage checks.

## Proposed first scope

Three initial detector candidates:

| Event | Proposed definition to refine before implementation |
| --- | --- |
| Negative-price run | Consecutive complete intervals below zero; gaps end a run. |
| Price spike | A configurable documented price threshold; contiguous qualifying intervals grouped deterministically. |
| Renewable peak | A documented regional renewable metric and threshold/ranking over complete coverage; requires validated metric semantics. |

Numeric thresholds, minimum durations, grouping and ranking are not settled. If renewable coverage is insufficient, assess a validated demand-ramp event as a replacement and record the scope decision before building it. Do not fabricate renewable share from mismatched component series.

Catalogue cards show type, region, market time, duration/value, evidence coverage and methodology. Filter by region, date range and event type. Replay opens a bounded context window with synchronised price, demand, generation-by-technology and validated regional flow charts. A play/pause/scrub cursor moves across the same intervals. Facility changes may be shown only where facility data passed validation; they are supporting observations, not proof of causation.

## Correctness and provenance

Store event detector version, parameters, source revision and evaluated coverage. Repeated detection on identical inputs produces the same logical events without duplicates. Recompute revised periods deliberately while preserving version context for saved investigations.

Document how events cross day boundaries and avoid counting the same event twice in overlapping ingestion windows. Missing intervals interrupt qualifying runs and invalidate unsupported rankings. A label such as longest this month requires complete coverage of that comparison scope or an explicit available-data qualification.

Display regional imports/exports using verified signs and definitions. Named interconnector animations, trip attribution, bidding causes and constraint explanations are outside initial scope without additional evidence.

## Acceptance criteria

- Hand-labelled fixtures verify each detector's boundaries, ties, thresholds, missing intervals and overlap deduplication.
- A replay can be reproduced from its detector/data version and all chart timestamps agree.
- Empty catalogue, missing optional metrics and unavailable periods have clear UI states.
- A catalogue-to-replay-to-BatteryLab journey passes browser checks; cross-midnight events identify the selected simulation day explicitly.
- Public event statements describe observations and their evidence without asserting unverified causes.

Execution is refined in [NEM-018](../backlog.md#nem-018) after BatteryLab. Data prerequisites: [data foundation](data-foundation.md), [BLK-003](../blockers.md#blk-003), [BLK-005](../blockers.md#blk-005).

## Data-validation constraints from M1

The [grid gate](../evidence/oe-validation/grid-gate.md) supports an observation-time replay for the sample days. Shared cursor positions must not imply identical measurement windows. Regional battery totals, curtailment-based events and renewable-peak detection require additional methodology checks before implementation; individual provider series can remain contextual with explicit labels. Keep the three-event target, but settle the third detector using the proposed fallback or validated renewable methodology in NEM-018.

## Exploration demo

A static mock-data page at [docs/demos/gridreplay/index.html](../../demos/gridreplay/index.html) sketches the catalogue, filters, synchronised replay cursor and catalogue→replay→BatteryLab navigation for discussion. It runs a seeded synthetic NSW1 generator with no backend; the detector parameters, thresholds and provisional renewable/ramp definitions shown are illustrative, not accepted definitions, and the page is not a design commitment for NEM-018.

## Public shell implementation

NEM-034 adds a `/gridreplay` overview in the separate frontend, with explicit unfinished-feature
copy and a methodology link. It contains no data, controls or calculated results. The
full product journey and acceptance criteria above remain future work.
