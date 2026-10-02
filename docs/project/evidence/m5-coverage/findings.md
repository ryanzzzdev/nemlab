# GridReplay initial catalogue coverage — NSW1, September 2023

Recorded: 2026-10-02. Task: [NEM-054](../../backlog.md#nem-054).
Probe: [probe_sep2023.py](probe_sep2023.py) → [sep2023-nsw1-coverage.json](sep2023-nsw1-coverage.json).
Six bounded requests, no credentials stored; raw responses are not retained —
rerun the script to regenerate.

## Coverage matrix (5-minute series, NEM market days 2023-09-01..30)

| Series | Source endpoint | Days complete (288/288) | Days partial | Days absent | Notes |
| --- | --- | --- | --- | --- | --- |
| price ($/MWh, interval-end labels) | market/network/NEM | **30/30** | 0 | 0 | end-labelled grid; boundary rows excluded correctly |
| demand (MW, source-label grid) | market/network/NEM | **30/30** | 0 | 0 | AEMO TOTALDEMAND — scheduled demand, not underlying consumption |
| flow_imports (MW) | market/network/NEM | **30/30** | 0 | 0 | nonnegative magnitudes |
| flow_exports (MW) | market/network/NEM | **30/30** | 0 | 0 | nonnegative magnitudes |
| power:coal_black | data/network/NEM, secondary_grouping=fueltech | **30/30** | 0 | 0 | |
| power:wind | same | **30/30** | 0 | 0 | |
| power:solar_utility | same | **30/30** | 0 | 0 | |
| power:solar_rooftop | same | **30/30** | 0 | 0 | resampled estimate — label as such |
| power:hydro | same | **30/30** | 0 | 0 | |
| power:gas_ccgt / gas_ocgt / distillate | same | **30/30** | 0 | 0 | signed values possible; preserve |
| power:bioenergy_biomass | same | **30/30** | 0 | 0 | |
| power:pumps | same | **30/30** | 0 | 0 | consumption |
| power:battery_charging / battery_discharging | same | **30/30** | 0 | 0 | legacy split representation in this period (no signed `battery` series); preserve magnitude/direction, do not double-count |

Edge rows in the JSON (price 2023-08-31 with 1 row; all series 2023-10-01 with
≤12 rows) are the probe window's boundary observations, not September gaps.

## Event density observed (September 2023, NSW1)

- **All 30 days** contain at least one negative-price interval
  (month min −53.89 AUD/MWh) — the negative-price-run detector will produce
  plentiful real events; ranking/“interestingness” must not be needed to fill
  a catalogue.
- **2023-09-04** reaches 16,599.89 AUD/MWh — at least one genuine spike event.
- Scheduled demand spans 3,967–9,875 MW — real positive ramps exist.

## Recommendation accepted

First catalogue: **NSW1, 2023-09-01 through 2023-09-30** — every required
series is complete on every day, all three detector types have real events,
and the month includes the M1-validated 2023-09-11 anchor day. Coverage was
verified on returned data; upstream provider gap-filling cannot be excluded —
coverage claims must cite "stored/observed coverage", never "complete market
history".

## Bounded source checks still needed before enabling imports

- Backfill-window behaviour: confirm OE returns identical values when the same
  day is fetched inside a multi-week window vs a single-day request (revision
  identity depends on it).
- `power` series null/omitted-timestamp behaviour on deliberately partial days
  (choose a known AEMO outage window if one exists; otherwise document as a
  live-import guard).
- Confirm the split `battery_charging`/`battery_discharging` representation is
  consistent across the whole month (the probe shows both series present; M1
  unit-level overlap rules apply per facility if facility panels are ever
  added).

## Exclusions carried from M1/BLK-005 (not resolved by this probe)

- Renewable-proportion/curtailment metrics: present but unvalidated —
  excluded from v1 detectors.
- Physical-window reconciliation across metrics: still not claimed.
- Named interconnector links, facility panels, causal annotations: out of
  scope.
