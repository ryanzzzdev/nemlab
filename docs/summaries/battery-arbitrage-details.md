---
project: aus-energy
created: 2026-09-11T16:59:40+10:00
updated: 2026-09-12T11:33:10+10:00
---

# Battery arbitrage: product and financial model

## Product question

“If I had batteries of this size, in this region, on this historical day, what could I have earned by charging when prices were low or negative and discharging when prices were high?”

The calculator is BatteryLab's core feature. Report **simulated energy-trading margin**, with a comparison between perfect hindsight and a practical strategy. The following is the proposed model for implementation planning; defaults and scope still need confirmation.

## Inputs and scope

| Input | Purpose |
| --- | --- |
| NEM region and historical date | Select the regional wholesale-price series |
| Battery count and storage capacity (kWh/MWh) | Define total stored-energy capacity |
| Charge and discharge power (kW/MW) | Limit how quickly energy can be bought or sold |
| Shared import/export connection limits | Cap the combined operation of multiple batteries |
| Charge/discharge efficiency | Account for energy losses |
| Minimum, maximum, and initial stored energy | Set operating reserves and starting conditions |
| Final stored-energy target | Default to the starting level for a fair daily comparison |
| Operating windows or strategy settings | Define when and how the battery trades |
| Variable fees and degradation allowance | Estimate selected operating costs |

A 100 MW / 200 MWh battery has a nominal two-hour duration; discharge efficiency and reserve settings affect energy actually exported. Power and storage must be separate inputs. For identical batteries, scale both by count, then apply the site's shared connection limits.

Start with NEM wholesale prices at five-minute resolution. “Location” initially means NSW/ACT, QLD, SA, TAS, or VIC. A suburb picker could map to its region, but cannot establish an address-specific wholesale price. A household mode would additionally need retail tariffs, load, solar generation, export rules, and fees.

## Strategies and fair comparison

| Strategy | Information available | Meaning |
| --- | --- | --- |
| **Perfect hindsight** | All historical prices for the simulated period | Best feasible margin under the model's constraints and costs |
| **Fixed schedule** | Charging/discharging windows set before inspecting the evaluated day | Simple practical baseline: for example, charge midday and discharge in the evening |
| **Price thresholds** | Only prices observable when each decision is made | Charge below a preset threshold; discharge above another |
| **Forecast-based** | Forecasts generated from information available before each decision | Later extension using walk-forward backtesting |

For the MVP, compare perfect hindsight with a fixed schedule. Select schedule parameters before viewing the evaluated day's results. Threshold strategies need explicit reporting/decision delays; forecasting must exclude future data from training and decisions.

Adding efficiency losses to hindsight does not make it realistic: knowledge of future prices is the central difference. Compare strategies using identical battery limits, costs, and initial/final stored energy. Offer whole-day optimisation and restricted midday/evening windows, clearly labelling any comparison with different windows.

## Physical model

Use MW for power, MWh for energy, and AUD/MWh for prices internally. For a five-minute interval, `dt = 5/60` hours. Define:

- `c[t]`: MWh imported at the grid connection during interval t.
- `d[t]`: MWh exported at the grid connection during interval t.
- `E[t]`: MWh stored at the end of interval t.
- `eta_c`, `eta_d`: charging and discharging efficiencies, each between 0 and 1.

```text
E[t] = E[t-1] + eta_c * c[t] - d[t] / eta_d

E_min <= E[t] <= E_max
0 <= c[t] <= min(total_charge_MW, connection_import_MW) * dt
0 <= d[t] <= min(total_discharge_MW, connection_export_MW) * dt
E[end] = E[start]   (default)
```

Prevent simultaneous charging and discharging. If the UI accepts one round-trip efficiency, define how it is split: a simple modelling convention is `eta_c = eta_d = sqrt(round_trip_efficiency)`. Do not apply the full round-trip loss to both legs.

Equal starting and ending energy prevents apparent profit from selling unreplaced starting inventory. For longer continuous simulations, carry stored energy across days and apply the terminal condition at the end of the full horizon; resetting every day changes the opportunity being modelled.

## Financial calculation

Let `p[t]` be the historical price, `f_c` and `f_d` the selected variable fees per imported/exported MWh, and `g` a simple degradation allowance per exported MWh. All energy quantities below are measured at the grid connection.

```text
charging_cost     = sum(p[t] * c[t])
discharge_revenue = sum(p[t] * d[t])
gross_margin      = discharge_revenue - charging_cost

variable_fees     = sum(f_c * c[t] + f_d * d[t])
degradation_cost  = g * sum(d[t])
modelled_margin   = gross_margin - variable_fees - degradation_cost
```

Negative charging prices produce a negative charging cost—a credit under the assumed wholesale settlement. Selling at a negative price produces negative discharge revenue. Efficiency is already captured in the energy balance; do not subtract its financial effect again as a separate cost.

The hindsight optimiser maximises `modelled_margin` subject to the physical constraints and any operating windows. It should allow no trading when trading is uneconomic. A predetermined practical strategy may lose money; show that outcome rather than silently replacing it with hindsight.

### Illustrative example (not historical data)

Assume sufficient battery power and capacity to import 1 MWh at -$30/MWh, then export 0.9 MWh at $200/MWh after 90% round-trip efficiency, finishing at the starting stored-energy level.

| Component | Calculation | AUD |
| --- | --- | ---: |
| Charging cost | 1 × -30 | -30.00 |
| Discharge revenue | 0.9 × 200 | 180.00 |
| Gross margin | 180 - (-30) | 210.00 |
| Import fee, assumed $2/MWh | 1 × 2 | 2.00 |
| Export fee, assumed $2/MWh | 0.9 × 2 | 1.80 |
| Degradation, assumed $10/exported MWh | 0.9 × 10 | 9.00 |
| **Modelled margin** | 210 - 2 - 1.8 - 9 | **197.20** |

The example fees and degradation are explanatory assumptions, not recommended industry defaults. For a single cycle returning to its initial energy level, let round-trip efficiency be `r`, purchase price `p_buy`, and sale price `p_sell`. Trading is profitable under this cost model when:

```text
r * (p_sell - f_d - g) > p_buy + f_c
```

## What the result represents

Assume a price-taking battery: its trades do not change historical prices. The result covers wholesale energy arbitrage with selected variable costs. It excludes capital and financing costs, fixed operating costs, detailed network and loss-factor treatment, contracts, and ancillary-service revenue unless explicitly added.

It is therefore neither a full investment return nor an estimate of household earnings. Scaling to very large fleets remains a fixed-price scenario, since actual fleet behaviour could change prices.

## Frontend and explanations

Provide configuration controls, comparison cards, and three synchronised charts: price, charging/discharging power, and stored energy. Show cumulative margin and a breakdown of charging cost or credit, sales revenue, fees, degradation, and energy lost. Include a replay cursor and shareable scenario links.

Explain calculated differences: “The scheduled strategy sold before the later spike,” “Export power limited sales during the highest-price interval,” or “More storage provided little benefit because charging power was the limit.” Such explanations should follow from model results, not inferred causes of market events.

## MVP and engineering handoff

Start with a single NEM day, five-minute prices, one aggregate battery/site configuration, fixed-schedule versus perfect-hindsight strategies, and an inspectable financial breakdown. Later add monthly/yearly backtests, region and battery-duration comparisons, thresholds, forecasts, real-facility comparisons, and links to GridReplay events.

The backend should support reliable price ingestion, missing/duplicate interval checks, explicit market timezones, repeatable simulations, and versioned inputs/results. Verify energy conservation, limits, mutually exclusive charging/discharging, terminal energy, negative prices, and cost accounting. Under identical constraints, the optimiser should perform at least as well as every feasible baseline.

Open decisions: target audience, battery presets, default efficiency and degradation, exact scheduled policy, decision timing for reactive strategies, missing-data policy, and initial demonstration dates. No architecture or implementation has been agreed in this discussion.

Sources: [market API](https://docs.openelectricity.org.au/api-reference/market/get-network-data/), [networks](https://docs.openelectricity.org.au/guides/networks/), [battery guide](https://docs.openelectricity.org.au/guides/batteries/). Companion: [NEMLab project ideas](nemlab-project-ideas.md).
