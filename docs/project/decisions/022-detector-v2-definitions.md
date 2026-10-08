# 022 — Detector v2 frozen definitions and highlight selection

Date: 2026-10-08. Status: Accepted (implementation campaign under NEM-083–091;
calibration against real September data recorded in NEM-091). Task:
[NEM-087](../backlog.md#nem-087).

## Frozen detector-v2 definitions (detector version `v2`)

All v2 detectors run *after* the unchanged v1 detectors over the same pinned
revision snapshot. v2 event rows carry `detector_version="v2"`, their own
`detector_params`, and an immutable `detail` evidence payload.

### Unusual demand ramp (`unusual_demand_ramp`)

- Base event: the day's existing `demand_ramp` (largest positive three-hour
  scheduled-demand change). No qualifying ramp → no candidate.
- Baseline: the **90 NEM days preceding the ramp day**, evaluated with the
  same ramp rule per day. Requires **≥ 60 complete baseline days** overall and
  **≥ 20 same-class days** (weekday vs weekend).
- Classification: unusual when the rise is **strictly greater than the
  nearest-rank P90** of same-class daily ramp rises (complete nonpositive days
  contribute 0) **and ≥ 1000 MW**.
- Insufficient baseline is recorded as `insufficient_baseline` in the day's
  coverage — never reported as "ordinary".

### Negative-to-high price reversal (`price_reversal`)

- Base: a **complete** `negative_price_run` (≥ 3 intervals).
- Look-ahead: **72 intervals (6 h)** after the run's last interval; all must
  be present — one missing observation withholds the claim entirely.
- Qualifying peak: price **≥ 300 AUD/MWh** (which, given a strictly negative
  trough, already implies a > 300 rise; the separate ≥ 300 rise clause is
  documented redundancy kept for clarity).
- Peak choice: highest qualifying price, earliest interval on ties. Runs
  whose look-aheads share the same peak interval keep the candidate with the
  largest rise (deepest trough), earliest run start on ties; other runs are
  recorded as linked evidence (`memberRuns`/`memberIds`).
- `detail` carries trough, peak, rise, elapsed minutes, member run ranges.

### Negative-price episode (`negative_price_episode`)

- Groups consecutive **complete** negative runs when each gap is:
  present in full, all observations nonnegative and ≤ 50 AUD/MWh, and
  ≤ 3 intervals (15 min) long; cumulative joined gap ≤ 6 intervals (30 min);
  ≥ 2 members.
- Deterministic left-to-right scan; `detail` carries member ranges/count,
  negative minutes, gap minutes and total span minutes (kept separate).

## Highlights selection versions

- `highlights-v1` (v1 types only): per-reason exact-value lists —
  highest price (spike: peak desc), longest negative run (duration desc, min
  price asc), deepest negative price (min asc, duration desc), largest demand
  rise (rise desc). Ties: latest start, then highest immutable id.
- `highlights-v2`: adds lists for unusual demand rise, largest price
  reversal and widest negative episode; a selected compound/classified event
  **suppresses its linked simple constituents inside the selection only** —
  All events still shows every original.
- Round-robin across the frozen reason order; when a candidate violates a
  per-type (spike 2, ramp 2, run 4, v2 types 2 each) or per-day (2) cap,
  selection **scans down the same candidate list** for the highest remaining
  candidate that fits — the list's turn is not skipped.
- Maximum 8 cards; no filler when a publication is thin. Ranks stay truthful
  (a capped-out candidate keeps its real rank; reasons keep their own units).

## Frozen vs tunable

Frozen for `v2`/`highlights-v2`: all constants above, selection order, caps,
suppression semantics, detail field names. Changing any requires a new
detector/selection version. The `detected v2` suite is published only via the
explicit `detectorSuite="v2"` operator parameter — v1 publications never emit
v2 types.

## Known limitations carried from the discovery plan review

- September-only catalogues lack the 90-day baseline: `unusual_demand_ramp`
  will report `insufficient_baseline` until a bounded backfill exists — this
  is a data dependency, not a code one.
- The same-weekday sample floor (≥ 20) means nearest-rank P90 is roughly the
  second-largest same-class value; claim strength stays modest on purpose.
- The rolling 90-day window is seasonally naive; revisit if calibration shows
  systematic seasonal miss.
- The 300 AUD/MWh reversal peak may prove non-selective on real data; it is
  frozen as the calibrated starting point and measurable via `price_reversal`
  counts in `typeTotals`.
