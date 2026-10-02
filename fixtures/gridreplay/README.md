# GridReplay detector fixtures (NEM-054)

Hand-labelled, **synthetic** detector inputs — they encode boundary behaviour,
never real market data, and must not be presented as real events.

## Encoding

Each fixture is one JSON document:

- `marketDays`: ordered NEM days the input covers (1 or 2 for cross-midnight).
- `series.<metric>.semantics`: `interval_end` (price: label = interval end,
  index 0 covers 00:00–00:05) or `source_label` (demand: label = observation
  timestamp at grid start).
- `series.<metric>.runs`: run-length encoding — `[count, value]` pairs
  expanding to `count` consecutive intervals. `value` is a finite number,
  `null` (source returned a null), or `"ABSENT"` (no row at all — a true
  source gap). Runs must total `288 * len(marketDays)`.
- `expected.events`: ordered detector output for detector version `v1`
  (rules in `docs/project/decisions/020-gridreplay-scope-and-detectors.md`):
  `type`, `startIndex` (global index into the expanded sequence), `intervals`,
  `value` (min price / peak price / ramp MW), `ownerDay`, `edgeIncomplete`.
  `expected.noEventReason` records `insufficient_coverage` / `none` for days
  where a claim is withheld.

Indices are global across the concatenated day sequence so cross-midnight
cases stay unambiguous.
