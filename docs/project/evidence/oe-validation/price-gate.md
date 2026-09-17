# BatteryLab sampled-price gate

Recorded: 2026-09-13 23:06 AEST  
Tasks: [NEM-003](../../backlog.md#nem-003), [NEM-004](../../backlog.md#nem-004)

## Decision: pass for the two sampled NSW1 days

The engine proof can use NSW1 prices for 2023-09-11 and 2026-09-11. This is a bounded data-validation conclusion, not a claim of complete historical coverage, all-region support, independently audited settlement values or investment-grade accuracy.

| Check | Recent day | Historical day |
| --- | --- | --- |
| Analytical day | 2026-09-11 | 2023-09-11 |
| Network / region | NEM / NSW1 | NEM / NSW1 |
| HTTP / API version | 200 / 4.5.14 | 200 / 4.5.14 |
| Normalised five-minute intervals | 288 | 288 |
| Missing / duplicate / invalid observations | 0 / 0 / 0 | 0 / 0 / 0 |
| Source timezone / unit | UTC+10 / $/MWh | UTC+10 / $/MWh |
| Lowest / highest AUD/MWh | 0 / 122.86 | -24.89 / 299.99 |
| Negative / zero intervals | 0 / 3 | 6 / 2 |

## Historical response and day boundaries

The request from 2023-09-11 00:00 to 2023-09-12 00:05 returned 289 observations: midnight through the following midnight. Selecting interval-end timestamps in `(start,end]` excludes the initial midnight, which represents the preceding day's final interval, leaving 288 consecutive intervals from 00:05 through the following 00:00. No other observation was removed, filled, averaged or shifted. Each normalised record carries both explicit start and end instants.

Response envelope and series structure match the recent request: price metric, five-minute interval, $/MWh, NSW1 region and UTC+10 timestamps. Successful retrieval proves this credential can access the sampled date more than two years ago; it does not independently establish an account-plan name or unlimited historical entitlement.

## Settlement interpretation and limitations

AEMO reports that five-minute settlement commenced on 1 October 2021, aligning dispatch and financial settlement. Both chosen dates are after that transition. Treat these as five-minute regional wholesale prices for the simplified price-taking model; do not interpret them as household tariffs or a participant's realised revenue. [AEMO commencement reference](https://www.aemo.com.au/initiatives/major-programs/past-major-programs/five-minute-settlement/5ms-program-management/5ms-commencement).

Interval-ending interpretation is supported by the recent sample's four independent AEMO comparisons, source-code inspection and the common post-transition regime. It is applied to the historical response as an explicit inference; historical AEMO records were not independently downloaded and compared. No claim is made about pre-October-2021 series, intervention/revision treatment, source-side gap filling, or additional metrics. OE's rounded prices remain the model inputs; a structurally complete response cannot prove the provider never filled a missing upstream value.

For the engine proof this evidence is sufficient to proceed with the two immutable samples and the declared assumptions. Expand validation before advertising any broader region/date range, and independently cross-check older raw AEMO prices if exact source equivalence becomes a product requirement.

## Evidence

- [Historical request](historical-price-request.json)
- [Historical response](historical-price-response.json)
- [Historical checks](historical-price-checks.json)
- [Historical normalised day](historical-price-normalised.json)
- [Recent findings and boundary cross-check](recent-price-findings.md)
- [Recent normalised day](recent-price-normalised.json)

Samples contain market data only. Credentials and authentication headers are excluded. The negative historical intervals provide useful real-data cases, but synthetic cases are still required to prove numerical/physical correctness.

## Remaining work

NEM-005 and NEM-006 must validate aligned grid/facility data; M1 is not complete. The Java baseline and battery model contract remain separate decisions. Define and verify launch coverage before releasing historical-range selectors.
