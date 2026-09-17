# Regional grid validation

Recorded: 2026-09-13 23:09 AEST  
Task: [NEM-005](../../../backlog.md#nem-005)

## Result and scope

Twelve authenticated requests succeeded (HTTP 200): NSW1 on 2026-09-11 and 2023-09-11, each at five-minute and hourly resolution, for market demand, market imports/exports, and generation power grouped by fuel technology. Request metadata and original responses are stored beside this report, identified by date, kind and interval. Every response reports MW.

| Input | Recent series | Historical series | Coverage result |
| --- | --- | --- | --- |
| demand | 1 | 1 | 288 finite points on each midnight-to-23:55 source-label grid |
| flow_imports / flow_exports | 2 | 2 | Same; no negative values in these samples |
| power by fueltech | 13 | 12 | Same for every returned technology |

Across 31 series/day combinations there are no missing grid points, duplicate timestamps or invalid values. This establishes response completeness for returned categories, not completeness of all assets or absence of upstream interpolation. An absent category must not automatically become zero.

## Hourly aggregation

Each request extends to the following 01:00 to retain boundary context. Compare the 24 full API hourly buckets with the arithmetic mean of twelve five-minute values whose source timestamps fall in `[hour,hour+1h)`. All 744 comparisons agree within 0.000001 MW. A separate shifted grouping `(hour,hour+1h]` generally disagrees, by up to approximately 196.47 MW in the tested series. Hourly labels therefore describe source-timestamp buckets, not necessarily identical physical-hour coverage across metrics.

Do not sum MW values as though they were MWh. If a physical-hour view of end-labelled prices/demand is required, aggregate the explicitly normalised five-minute data yourself rather than silently joining native hourly series with different time support.

See [computed checks](checks.json). Reproduce offline with `python3 check_grid.py` from any directory; this script reads only saved market-data files and makes no network requests.

## Meanings, signs and timing

- Demand: OE documents `demand` as AEMO TOTALDEMAND (scheduled demand), not all underlying consumption. Label it accordingly. The source relationship supports dispatch-interval context, but we did not independently cross-check demand values against AEMO here. [OE demand guide](https://docs.openelectricity.org.au/guides/demand/).
- Regional flows: both import and export series are nonnegative magnitudes in the tested responses, and can both be nonzero when NSW trades in different directions across different links. Preserve them separately. A derived net-import series may be expressed as imports minus exports, with a clear derived label. These observations do not verify individual interconnector direction or establish an exact physical balance; link-level source reconciliation remains outside this test. [OE interconnector context](https://docs.openelectricity.org.au/guides/interconnectors/).
- Generation: fueltech labels are source categories. Recent data includes signed `battery` (negative consumption, positive output) alongside nonnegative `battery_charging` and `battery_discharging`; historical data has the two directional categories but no generic battery category. Do not infer whether the generic and split categories are disjoint or overlapping from names alone. Preserve separate series and defer combined battery totals to unit-level metadata validation in NEM-006. Charging and pumps represent consumption even where their returned magnitudes are positive. [OE battery representation](https://docs.openelectricity.org.au/guides/batteries/).
- Historical gas_ocgt reaches -4.0851 MW. Preserve the signed observation rather than clamping it; unit-level investigation must determine whether it represents net consumption or another data issue.
- Power is an observation of a rate, not automatically an interval-average energy quantity. Timestamp equality with price does not prove an identical physical measurement window. Roof-top solar on a five-minute grid may be resampled from a coarser feed; do not describe all five-minute rows as independent five-minute measurements. [OE power guide](https://docs.openelectricity.org.au/guides/power/).

All series expose the same source-label grid, permitting a labelled observation-time replay. Full physical-window reconciliation between SCADA, demand, flows and interval-ending prices is not established by these API checks. Keep raw timestamps and metric-specific timing metadata, show contextual observations, and avoid energy-balance or causal claims until unit/source timing is validated.

## GridReplay classification

| View | Classification |
| --- | --- |
| Price and scheduled-demand context | Core candidate on sampled dates; keep demand definition explicit |
| Generation by individual technology | Core candidate as separate observed series with signed values |
| Regional import/export context | Optional supported series; preserve directional magnitudes, no named-link animation |
| Combined battery total / exact supply-demand balance | Deferred pending category/asset and measurement reconciliation |
| Rooftop solar | Optional contextual series; label source resolution limitations |
| Renewable percentage / curtailment | Not requested in NEM-005; evaluate in NEM-006 |

NEM-005 is complete as a bounded API validation and classification exercise. It does not close M1 or promise full GridReplay physical alignment. Carry the explicitly identified category, timing and optional-metric questions into NEM-006 before closing the grid gate.
