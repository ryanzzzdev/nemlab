# Recent NSW1 price validation

Recorded: 2026-09-13 23:00 AEST  
Task: [NEM-003](../../backlog.md#nem-003)

## Result

Authenticated retrieval succeeded (HTTP 200, API 4.5.14, success=true). The saved response contains one NSW1 price series with 288 unique finite numeric values, five-minute spacing, UTC+10 offsets, no nulls, no duplicates, and no missing or extra points on the returned midnight-to-23:55 grid. Units are `$/MWh`, interpreted as Australian dollars for NEM regional prices. This validates access to this recent sample, not Academic entitlement or older history.

## Important interval finding

The request ended at 2026-09-12 00:00 but the response ends at 2026-09-11 23:55. Observed selection is consistent with an exclusive upper boundary, despite the endpoint documentation describing it as inclusive. No rows were dropped or shifted during validation.

This does not establish whether each price applies to the following or preceding five minutes. A complete timestamp grid is not proof of interval-start labelling. The sibling OpenNEM checkout's `opennem/controllers/nem.py` process_nem_price preserves AEMO settlementdate as interval; `opennem/api/queries.py` uses an exclusive date_end. That is supporting local-source evidence, not proof of the deployed service's full ingestion lineage. This was the initial uncertainty; the cross-check below resolves it for this sample. The broader historical price gate remains pending NEM-004.

Initial follow-up (now completed): establish the deployed series' relationship to AEMO interval-ending prices through a primary-source cross-check or provider clarification. If end-labelled, retrieve the next midnight value and use `(start,end]` for the selected analytical day. Do not silently assume `[start,end)` is physically correct.

## Evidence and reproducibility

- [Request parameters and retrieval time](recent-price-request.json)
- [Response sample](recent-price-response.json)
- [Computed checks and response hash](recent-price-checks.json)

The request uses the documented market endpoint with the sample plan's parameters and an explicit `User-Agent: NEMLab-data-validation/0.1`, plus `Accept: application/json`. The default Python client received HTTP 403 with gateway error 1010; the identified client succeeded. Authentication headers and the credential were not saved. An initial restricted-network attempt failed before the request could complete.

The sample demonstrates zero prices but contains no negative prices; negative-price correctness still requires separate fixtures or another historical window. No forward-fill, imputation, deduplication or timezone shifting was applied.

Sources: [OE market endpoint](https://docs.openelectricity.org.au/api-reference/market/get-network-data/), [OE price guide](https://docs.openelectricity.org.au/guides/price/). Original documents distinguish query bounds from physical interval semantics only incompletely; this uncertainty is recorded rather than resolved by assumption.

## Resolution — boundary cross-check

Four independent AEMO DISPATCH PRICE records (intervention=0), at 23:50, 23:55, midnight and 00:05, match OE at the same timestamp within 0.005 AUD/MWh. A five-minute-shift interpretation does not match these changing prices. Together with AEMO's interval-ending convention and the source lineage described above, this supports interval-end interpretation for this modern NSW1 sample. This is an evidence-based inference for the tested series, not a provider guarantee for every metric or historical regime.

- [AEMO extracted records with exact report URLs](aemo-crosscheck.json)
- [Numerical comparison](boundary-comparison.json)
- [OE boundary request](boundary-price-request.json) and [response](boundary-price-response.json)
- [Normalised analytical-day sample](recent-price-normalised.json)

The boundary request for 23:50 through 00:10 returns 23:50, 23:55, 00:00 and 00:05, confirming the observed exclusive query end on a second window. The corrected analytical day selects source interval-end stamps in `(2026-09-11 00:00, 2026-09-12 00:00]`, explicitly deriving each interval start by subtracting five minutes. It contains 288 contiguous intervals with no gaps or conflicting overlap values. The original response is retained unchanged for provenance.

For future modern five-minute price requests, fetch an extra five minutes at the upper boundary and select interval ends explicitly. Preserve raw labels and never apply this rule indiscriminately to power, demand, or other metrics before validating their semantics. OE's cent precision differs from the higher-precision AEMO source; simulations based on OE reproduce OE precision.

NEM-003 passes for the sampled day. NEM-004 must still verify older access and regime semantics before closing the complete BatteryLab price gate. Earliest attempted AEMO report times were no longer listed in the current directory, so four available boundary reports were used instead; full-day independent price equivalence was not tested.

Primary convention reference: [AEMO five-minute settlement technical specification](https://www.aemo.com.au/-/media/files/electricity/nem/5ms/systems-workstream/2020/emms-technical-specification---five-minute-settlement---marked-up.pdf), which defines the first trading period as ending at 00:05 AEST. Public source prices were retrieved from the [AEMO DispatchIS directory](https://www.nemweb.com.au/Reports/CURRENT/DispatchIS_Reports/).

## Subsequent gate update

Historical validation is now complete in [NEM-004’s price gate](price-gate.md). Earlier pending references describe the state at completion of the recent-day exercise.
