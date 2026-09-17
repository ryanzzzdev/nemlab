# OE validation sample plan

Recorded: 2026-09-13 22:51 AEST  
Task: [NEM-002](../../backlog.md#nem-002)

## Selected samples

Network `NEM`, region `NSW1` (NSW/ACT). This is a bounded initial region, not a launch coverage commitment. Choose ordinary dates without selecting for a known profitable outcome.

| Sample | Market-day interval (fixed UTC+10) | Equivalent UTC interval |
| --- | --- | --- |
| Recent | 2026-09-11 00:00 to 2026-09-12 00:00 | 2026-09-10 14:00Z to 2026-09-11 14:00Z |
| Historical | 2023-09-11 00:00 to 2023-09-12 00:00 | 2023-09-10 14:00Z to 2023-09-11 14:00Z |

The recent date leaves a completed day between collection and the sample. The older date is more than two years before collection; its price/settlement interpretation still needs verification. These are midnight-to-midnight analytical days in fixed market time, not a claim about every operational definition of trading day.

## First request

GET `https://api.openelectricity.org.au/v4/market/network/NEM`

```json
{
  "metrics": "price",
  "interval": "5m",
  "network_region": "NSW1",
  "primary_grouping": "network_region",
  "date_start": "2026-09-11T00:00:00",
  "date_end": "2026-09-12T00:00:00"
}
```

Dates are supplied as network-local time as documented. Historical request substitutes the historical boundaries. Both query boundaries are documented as inclusive: preserve the full raw response before selecting the analytical day. Establish interval start/end labelling from evidence before filtering. Start-labelled data belongs in `[start,end)`; end-labelled data belongs in `(start,end]`. Expect 288 normalised five-minute price intervals, not necessarily 288 raw points. Do not discard a boundary merely to force a desired count.

Verify AUD/MWh units, actual offset, labels, duplicates, nulls, gaps and response status. Do not derive observation counts from an envelope field without inspecting its meaning.

Source: [market endpoint](https://docs.openelectricity.org.au/api-reference/market/get-network-data/), checked 2026-09-13.

## Subsequent requests

Use the same region and windows for NEM-005: market endpoint with `demand`, then separately `flow_imports` and `flow_exports`; generation endpoint `/v4/data/network/NEM` with `power`, `primary_grouping=network_region`, `secondary_grouping=fueltech`. Validate each combination instead of treating the broad shared metric list as proof of support. Repeat supported series at `1h` and expect 24 normalised hourly buckets per complete series. NEM-006 discovers actual facility/unit IDs before forming facility requests; identifiers are not guessed here. Renewable/curtailment probes remain optional.

Sources: [generation endpoint](https://docs.openelectricity.org.au/api-reference/data/get-network-data/), [network codes and timezone](https://docs.openelectricity.org.au/guides/networks/).

## Credential check and next action

No OE-related variable names were found in the active process environment, and no environment/configuration files exist in the NEMLab project. This is a scoped check, not proof that no key exists elsewhere. Sibling-project credentials were not searched or reused. No authenticated request has been sent and Academic entitlement has not been verified.

Configure `OPEN_ELECTRICITY_API_KEY` in a local `nemlab/.env` file or the environment available to this task. The local file is ignored by the added project `.gitignore`; do not paste credentials into chat. A future validation helper should load the value without shell tracing, never put it in command arguments or logs, and send it only as a Bearer header to the documented OE API. Merely configuring the key does not prove valid access: NEM-003 must check the actual response.

Source: [authentication overview](https://docs.openelectricity.org.au/api-reference/overview/).

## Evidence layout and findings

This directory contains the plan only. On execution, create sanitised request metadata, response samples and a findings report named by sample/metric. Record request parameters, retrieval timestamp, HTTP status, API version, source units, label semantics, raw/normalised counts, duplicates, nulls, missing timestamps, and pass/fail with reasons. Exclude authentication headers, keys and account-profile payloads. Keep large raw data outside Git until retention is decided.

| Check | Result |
| --- | --- |
| Safe local credential availability | Not found in the inspected scope |
| Recent price response | Not requested |
| Historical price response | Not requested |
| Grid/facility coverage | Not requested |
| BatteryLab price gate | Pending NEM-003 and NEM-004 |

## Execution update — 2026-09-13 23:00 AEST

Credentials are now available and the recent sample was retrieved successfully. The earlier access check describes the initial state. See [recent findings](recent-price-findings.md): query-grid checks pass, but physical interval labels and the full price gate remain pending.

## Boundary resolution

NEM-003 now passes: tested modern NSW1 prices are interval-ending, and observed API selection uses an exclusive end. Future sample requests should extend the query end by five minutes and select source interval ends in `(start,end]`. See [resolved findings](recent-price-findings.md); other metrics still need independent validation.

## Historical execution update

NEM-004 passed on 2026-09-13: 2023-09-11 returned a complete normalised day. The [sampled-price gate](price-gate.md) now permits both selected days, with stated scope and provenance limitations. Initial request/access statuses above are historical records.
