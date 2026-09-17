# Sampled grid-data gate

Recorded: 2026-09-13 23:12 AEST  
Task: [NEM-006](../../backlog.md#nem-006)

## Conclusion: bounded pass for development, with explicit exclusions

The NSW1 samples on 2023-09-11 and 2026-09-11 support development of an observation-time GridReplay: price, scheduled demand, selected technology and facility output, and regional import/export context. This closes the initial M1 sampling exercise. It does not certify all regions/history, a balanced energy model, or exact physical synchronisation between every metric.

[Price validation](price-gate.md) and [regional validation](grid/findings.md) remain applicable. Nine further requests succeeded: one metadata request, two facility-power requests and six optional-metric requests. Source definitions were checked against the [facility catalogue](https://docs.openelectricity.org.au/api-reference/facilities/get-facilities/) and [unit series endpoint](https://docs.openelectricity.org.au/api-reference/data/get-facility-data/).

## Facility selection and joins

The NSW1 catalogue returned 175 facilities. From actual discovered codes, sampled BAYSW (coal), BANGOWF (wind), AVLSF (solar), COLONGRA (gas), WALGRV and WTAHB (batteries). Queries cover midnight through the following 00:05, retaining a boundary observation. Unit checks below concern the `[00:00,24:00)` source-label grid, not a claim that power is an interval-average quantity.

All 17 recent and 13 historical returned unit series join by unit_code to a facility, technology and dispatch type in the current metadata. Current capacity/status/commencement records are not proven historical snapshots. WTAHB and the generic WALGRV bidirectional unit were absent from the historical response; absence remains unavailable data, not zero and not independent proof of commissioning dates.

The 11 non-battery unit series in each day have 288 numeric points with no missing timestamps or duplicates. Some units are all zero, notably sampled gas units; these are explicit returned zeros. They must remain distinct from omitted rows, nulls and entirely missing series. The underlying provider may apply preprocessing; this exercise does not verify upstream meter completeness.

## Battery overlap resolved for sampled units

Recent signed WALGRV1 and WTAHB1 each have complete 288-point source grids. Their split charging/discharging representations contain both omitted rows and null values. Across the entire 289-point requested window, all 578 populated directional observations match the corresponding positive or negative part of the signed unit exactly. Do not add both representations together.

For these sampled modern units, use the complete signed record as the canonical observed quantity and derive charging/discharging for display. Preserve the split source series as provenance, without converting their nulls into invented measurements. In the historical sample, WALGRVG1 and WALGRVL1 each have complete 288-point grids and no generic parent response; use that legacy pair for that period, preserving magnitude/direction explicitly.

This is not proof that every battery follows the same mapping. Require per-facility/time-window representation selection and an overlap check before summing a region. Defer a regional combined-battery total until that coverage is established. See [directional comparisons](facilities/battery-direction-checks.json) and [per-unit checks](facilities/checks.json).

## Optional metrics

| Metric | Recent range | Historical range | Decision for initial implementation |
| --- | --- | --- | --- |
| renewable_proportion | 12.39–78.83% | 5–68.37% | Contextual provider metric available; defer renewable-peak detector until denominator/storage/rooftop methodology is validated |
| curtailment_solar_utility | -2.0251–1313.2562 MW | -0.6637–383.1197 MW | Exclude initial event detection; preserve signed values, investigate negative values before use |
| curtailment_wind | 0–38.395 MW | 0–23.698 MW | Available contextual candidate; curtailment interpretation/timing not independently validated |

Each optional metric has 288 finite values on each tested source-label grid. Complete responses do not establish metric correctness. Do not silently clamp solar curtailment or turn the percentage into a custom renewable formula. Named-interconnector series were not tested and link animation remains excluded.

## Timing, rooftop and signed gas follow-up

Retain source timestamps for power and grid context; price carries the independently established interval-end convention. Do not shift every metric by five minutes or use cursor coincidence to claim causal alignment. Exact physical-window joins, energy integrations and reconstruction of supply-demand balance are excluded from the initial observation-time view until separately validated.

Rooftop solar stays optional and visibly described as a provider estimate/resampled series, not independent five-minute metering. Historical negative regional gas output was not explained by the sampled COLONGRA units (all zero); preserve the anomaly and defer its causal explanation. Other gas units would need sampling to trace it. These limitations are exclusions from claims, not fabricated data repairs.

## Evidence and remaining coverage work

Saved [metadata](facilities/nsw-metadata-response.json), date-labelled facility/optional responses and request metadata are in [facilities](facilities/). Reproduce per-series checks with [check_facilities.py](facilities/check_facilities.py); it reads local evidence only. Battery direction comparisons are separately recorded. No keys or authentication headers are saved.

- NEM-018 owner: implementing agent. Validate per-metric physical timing before claiming exact interval alignment; validate battery representation across any summed population. Resolve event definitions, including replacing or validating the renewable-peak candidate, before detector implementation.
- NEM-018 owner: implementing agent. Preserve negative gas observations without attribution; investigate additional gas-unit samples if explanations or corrected totals are required.
- NEM-020 owner: implementing agent with user scope decisions. Define promised regions/date ranges, sample that coverage, check attribution/retention, and confirm provider methodology for any optional metric promoted into public claims.
- NEM-007/NEM-008 owner: implementing agent and user for material choices. Resolve Java baseline and battery model contract next. M2 has not started merely because M1 sampling is complete.

BLK-003 closes for the bounded observational scope. Broader scope/methodology follow-ups remain recorded under BLK-005 and the linked implementation packages. This gate does not authorise publication or change launch scope beyond the stated validation limits.
