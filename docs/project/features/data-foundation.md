# Data foundation

Updated: 2026-09-13  
Status: Proposed implementation specification. [Two NSW1 price samples passed validation](../evidence/oe-validation/price-gate.md); [regional grid API checks passed with limitations](../evidence/oe-validation/grid/findings.md); unit-level timing, facility joins and broader coverage remain unverified.

## Outcome and scope

Provide validated historical NEM prices for BatteryLab and aligned price/demand/generation/flow data for GridReplay. Start with one sample region and bounded windows; all five NEM regions remain potential coverage, not a promise of complete history.

Reference background: [project ideas and validation exercise](../../summaries/nemlab-project-ideas.md). This specification owns the current proposed implementation behaviour; the summary remains a historical record.

## Initial validation protocol

1. Select a recent completed market day and an older day more than two years ago, recording exact dates and initial region. Avoid unverified settlement regimes for the first simulation samples.
2. Locate authorised Academic access without exposing keys. Record endpoint/request parameters, retrieval time, sanitised samples and response status. Observe actual query/rate limits and retry responses.
3. Validate five-minute price units, timezone, start/end labelling and inclusive boundaries. A correctly normalised complete 24-hour market day should contain 288 intervals. Report raw and normalised counts, duplicates, gaps and nulls separately.
4. Retrieve demand, technology-grouped generation and regional imports/exports for matching windows. Verify each metric/endpoint combination, signs and grouping. Compare hourly aggregation with five-minute inputs without assuming every series is additive or that demand equals generation.
5. Discover facility/unit codes and join representative output samples to metadata. Inspect coverage across technologies and distinguish absent output from zero.
6. Probe renewable and curtailment metrics separately if useful. Named interconnector series require their own evidence; regional flow totals are insufficient.

Create the findings report and sanitised evidence during execution, under a clearly documented location such as `docs/project/evidence/oe-validation/`. Do not create pretend sample data now. Large/raw datasets need a storage and retention decision, not automatic Git inclusion.

## Ingestion behaviour

Scheduled polling operates on completed intervals using source-aware delay and a configurable overlap window for revisions. Backfill requests specify metric, region/entity, resolution and bounded start/end times. Chunk requests to verified provider limits. Resume from persisted checkpoints; retry transient errors with bounded backoff. Reprocessing identical inputs creates no duplicate logical observations.

Preserve retrieval provenance and enough immutable inputs to reproduce published simulations. Expose freshness and coverage independently: recently fetched data may still be incomplete. A refresh must not rewrite old result snapshots.

## Missing data and presentation

Proposed policy: reject BatteryLab simulation on any required missing/invalid price interval. GridReplay displays gaps and limits comparisons/rankings to their documented complete coverage. Do not join events across missing intervals or silently fill gaps. Unsupported metrics are absent with an explanation, not zero.

Each series response identifies unit, resolution, interval labelling, market timezone, source/revision and coverage. Historical capacity metadata must not be presented as known when only current metadata is available.

## Acceptance criteria

- Sample evidence is sanitised and reproducible, with an explicit BatteryLab price gate and GridReplay input gate.
- Reimporting a window is idempotent; corrected inputs are traceable.
- Restarting interrupted backfills resumes safely; failed requests expose an actionable reason.
- Coverage checks find synthetic gaps, duplicates, nulls and timezone-boundary errors.
- Publicly advertised regions/date ranges have verified coverage beyond the initial sample.

Out of scope: WEM, weather dependency, complete facility-history reconstruction, and storing every OE metric before a feature needs it.

Execution: [NEM-002](../backlog.md#nem-002)–[NEM-006](../backlog.md#nem-006), [NEM-012](../backlog.md#nem-012). Open questions: [BLK-001](../blockers.md#blk-001), [BLK-003](../blockers.md#blk-003).

## M1 evidence update

The [sampled grid gate](../evidence/oe-validation/grid-gate.md) closes M1 for two NSW1 days with explicit observational scope. Preserve sparse directional battery data and choose one validated representation per facility/time window; do not sum parent and split records. Exact cross-metric physical alignment, population-wide battery totals, curtailment detection and broader launch coverage remain excluded pending follow-up.
