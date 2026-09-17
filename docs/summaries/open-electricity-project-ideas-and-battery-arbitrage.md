---
project: aus-energy
title: Open Electricity Project Ideas and Battery Arbitrage Product Concept
created: 2026-09-11T16:29:37+10:00
updated: 2026-09-11T16:29:37+10:00
status: Discussion and product-planning handoff
---

# Open Electricity Project Ideas and Battery Arbitrage Product Concept

## Purpose of this document

This document captures the product ideas and business-logic decisions discussed for a portfolio project built with Open Electricity data. It is intended to be used as context in a separate implementation-planning chat. The current chat can remain focused on product ideas, energy-market concepts, assumptions, and business logic.

No implementation architecture, framework, or deployment platform has been selected yet.

## Project objective

The project has two connected goals:

1. Demonstrate a serious interest in and developing understanding of the Australian electricity industry.
2. Demonstrate strong software-engineering skills to potential employers in the energy industry.

The product should therefore do more than reproduce a generic energy dashboard. It should answer a useful market question, explain the result clearly, and make the quality of the underlying engineering visible through reliable data ingestion, reproducible calculations, careful modelling, and a polished interactive frontend.

## Open Electricity data available to the project

Open Electricity, formerly OpenNEM, provides a public explorer and an authenticated REST API with Python and TypeScript SDKs. The user has an Academic plan, which provides access to the full historical window rather than only the most recent two years.

The main API data relevant to the project includes:

- Generation power in MW and energy in MWh, available by network, network region, fuel technology, facility, and generation unit.
- Wholesale spot prices in AUD/MWh.
- Operational and gross demand.
- Renewable generation and renewable share, including storage-adjusted variants.
- Utility solar and wind curtailment, currently documented for the NEM.
- Interconnector imports and exports between NEM regions.
- Facility and unit metadata, including location, fuel technology, operating status, registered and maximum power capacity, battery storage capacity, dispatch type, emissions factors, and relevant operational dates.
- Calculated electricity-sector CO2 emissions.
- Annual National Pollutant Inventory data for reporting facilities.
- Bureau of Meteorology station metadata and weather observations.

The primary electricity networks are:

- NEM: New South Wales and the ACT, Queensland, South Australia, Tasmania, and Victoria. Five-minute generation, price, and demand data is available, with history beginning in 1998.
- WEM: Western Australia's South West Interconnected System. Five-minute generation, price, and demand is documented from October 2023, with other dataset history beginning in 2006.
- AEMO Rooftop and APVI secondary datasets provide rooftop-solar information at coarser intervals.

Open Electricity supports aggregation from five-minute data to hourly, daily, weekly, monthly, quarterly, seasonal, financial-year, and yearly intervals. Power and price are rates and should be aggregated by averaging. Energy, emissions, and market value are quantities and should be aggregated by summing.

API requests use network-local time. NEM data is documented using UTC+10 and WEM data using UTC+8. Time handling, interval boundaries, and daylight-saving presentation require explicit treatment in the application.

Academic use is non-commercial under the documented CC BY-NC 4.0 terms. Any public project should include the required attribution and explain its data source. A later commercial use would require separate licensing.

Useful documentation:

- Introduction: https://docs.openelectricity.org.au/introduction/
- Platform: https://docs.openelectricity.org.au/platform/introduction/
- API overview: https://docs.openelectricity.org.au/api-reference/overview/
- Metrics and aggregation: https://docs.openelectricity.org.au/api-reference/metrics/
- Data limits: https://docs.openelectricity.org.au/api-reference/data-limits/
- Market network endpoint: https://docs.openelectricity.org.au/api-reference/market/get-network-data/
- Facility time-series endpoint: https://docs.openelectricity.org.au/api-reference/data/get-facility-data/
- Facilities endpoint: https://docs.openelectricity.org.au/api-reference/facilities/get-facilities/
- Network and region guide: https://docs.openelectricity.org.au/guides/networks/
- Battery guide: https://docs.openelectricity.org.au/guides/batteries/
- Curtailment guide: https://docs.openelectricity.org.au/guides/curtailment/

## Product ideas considered

### 1. GridReplay: NEM event explorer

GridReplay would help a user discover and investigate notable grid events such as price spikes, long periods of negative prices, renewable-generation records, sharp generator output changes, unusual demand ramps, or major changes in interconnector flows.

The central experience would be a replay screen with synchronised time-series charts. A shared time cursor would show price, demand, generation by technology, regional imports and exports, and the facilities whose output changed most during an event.

Example event cards could include:

- Longest negative-price period this month.
- Largest five-minute fall in coal generation.
- Highest renewable share in a region.
- Largest evening demand ramp.
- Most significant change in interconnector flow.

The backend work would include incremental ingestion, historical backfills, event detection, temporal joins, baseline comparisons, data-quality checks, and reproducible event records.

The product must distinguish observation from causation. The data may show that a facility's output suddenly fell, but that alone does not prove a generator trip or explain a price spike. Explanations should show the supporting evidence, state uncertainty, and avoid claims that require additional operational data.

A focused first release could support one NEM region, three event types, a searchable event catalogue, and one highly polished replay screen.

### 2. BatteryLab: battery-arbitrage calculator and experiment platform

BatteryLab would let users configure a battery and simulate its operation against historical regional wholesale prices. Its central feature is the battery-arbitrage calculator described in detail later in this document.

The product would answer questions such as:

- What energy-trading margin could this battery have earned in this region on this historical day?
- How does a simple midday-to-evening strategy compare with the best theoretically possible schedule?
- Was performance limited by storage capacity or charge/discharge power?
- Would a two-hour or four-hour battery have performed better?
- How sensitive is the result to round-trip efficiency, degradation cost, connection limits, and operating strategy?
- How does performance vary across regions, seasons, months, and years?

BatteryLab provides rich engineering material through constrained optimisation, strategy backtesting, background computation, reproducibility, experiment versioning, and interactive scenario comparison.

### 3. Renewable Economics Explorer

This product would investigate whether renewable generators produce electricity when it is valuable in the wholesale market.

Its central measure would be capture price: the generation-weighted wholesale price earned by a technology or facility over a period. The interface could compare capture price with the region's average spot price, negative-price exposure, market value, output profiles, and seasonal changes.

Example questions include:

- Do two solar farms in the same region experience different wholesale value because of their output profiles?
- How has the capture price of solar or wind changed over time?
- Which facilities have the greatest exposure to negative prices?
- How do regional market conditions affect otherwise similar technologies?

The engineering challenge is to align facility generation and regional price intervals correctly, handle missing observations, account for changes in facility capacity, and distinguish estimated spot-market value from realised revenue under contracts.

### 4. Flexibility Atlas

The Flexibility Atlas would show when and where the electricity system experiences steep ramps, renewable surplus, negative prices, curtailment, and heavy inter-regional transfers.

A strong frontend could use a year-long calendar heatmap. Each day would be coloured by a selected measure, and clicking a day would reveal its detailed shape. Users could compare regions or the same season across multiple years.

This idea demonstrates that renewable integration is affected by timing, demand shape, storage, and transmission as well as total annual generation.

The metrics should be presented as indicators. Regional price, curtailment, surplus, and ramp patterns can identify interesting periods, but they do not by themselves establish where a battery should connect or whether transmission capacity is available.

### 5. Generator Observatory

Generator Observatory would track the behaviour and evolution of individual generating assets and technology groups.

Possible features include:

- Facility maps and operating-status filters.
- Output histories and representative daily profiles.
- Capacity-factor estimates and peer comparisons.
- Sustained low-output or unusual-output periods.
- Commissioning, expansion, and closure timelines.
- Comparisons among similar wind, solar, coal, gas, hydro, and battery facilities.

A significant data-engineering issue is historical metadata. Applying a facility's current capacity to its entire output history can distort historical capacity factors if the asset expanded or changed. A credible product should preserve metadata snapshots or clearly document the limits of the source data.

## Recommended product direction

BatteryLab is a strong flagship because it has a concise value proposition, an engaging interactive interface, and enough technical depth to demonstrate both software engineering and energy-market reasoning.

GridReplay remains the strongest broad platform idea. The two can eventually complement each other: GridReplay can discover a historically interesting day, while BatteryLab can answer how a hypothetical battery would have traded through that event.

Renewable Economics Explorer is a natural later module because it reuses the price and generation pipeline and introduces commercially relevant analytics.

The recommended scope for the first project is BatteryLab with a historical single-day arbitrage calculator. The application can expand to longer backtests and event discovery after the calculator is correct and polished.

## Battery arbitrage concept

Battery arbitrage means charging a battery when electricity is cheap and discharging when electricity is more valuable. Negative wholesale prices can make charging especially attractive because, under the simplified market-settlement assumption, the battery may receive value for consuming energy. A profitable trade still requires the spread between charging and discharging prices to cover energy losses, fees, degradation, and other costs.

The user-facing question should be phrased carefully:

> What energy-trading margin could this battery have earned in this region on this day under different operating strategies?

"Energy-trading margin" is more accurate than unrestricted "profit." The initial calculator will include wholesale charging costs, wholesale discharge revenue, and selected variable costs. True net profit would also require capital costs, financing, fixed operating costs, taxes, network charges, market participation costs, contracts, and potentially other revenue streams.

The initial product models energy arbitrage only. Batteries can also earn revenue from frequency-control and other ancillary services, but those require additional market data and modelling and should be treated as a later module.

## Location model

For the initial calculator, location means an electricity-market price region:

- NSW1, including the ACT.
- QLD1.
- SA1.
- TAS1.
- VIC1.
- WEM, if WEM price semantics and available history are validated separately.

A suburb, postcode, or map selection could be translated to its market region for a friendlier interface. Open Electricity's regional wholesale price does not establish a unique local price at an exact address.

The first release should focus on the NEM. This gives a consistent five-region model and avoids prematurely assuming that identical settlement and trading rules apply to the WEM.

## Calculator inputs

The battery configuration should include:

| Input | Unit | Purpose |
| --- | --- | --- |
| Market region | Region code | Selects the historical wholesale-price series |
| Historical date | Local calendar date | Selects the simulation period |
| Number of batteries | Count | Scales a repeated battery configuration |
| Usable storage capacity | kWh or MWh | Limits the energy that can be stored |
| Maximum charge power | kW or MW | Limits energy imported per interval |
| Maximum discharge power | kW or MW | Limits energy exported per interval |
| Shared connection import limit | kW or MW | Caps charging across all batteries |
| Shared connection export limit | kW or MW | Caps discharging across all batteries |
| Charge efficiency | Percentage | Models energy lost while charging |
| Discharge efficiency | Percentage | Models energy lost while discharging |
| Minimum state of charge | Percentage or MWh | Maintains a reserve and limits usable energy |
| Maximum state of charge | Percentage or MWh | Prevents overcharging |
| Initial state of charge | Percentage or MWh | Defines energy present at simulation start |
| Required final state of charge | Percentage or MWh | Prevents the result from monetising unreplaced starting energy |
| Charge window | Times | Constrains simple scheduled operation |
| Discharge window | Times | Constrains simple scheduled operation |
| Variable market and operating fees | AUD/MWh | Models selected per-energy costs |
| Degradation allowance | AUD/MWh discharged or per equivalent cycle | Estimates wear caused by cycling |

Battery power and energy capacity are distinct. A 100 MW / 200 MWh battery can theoretically operate at its rated power for two hours. It cannot buy all of its energy during a single cheap five-minute interval, because the charge-power limit controls how much energy can enter during that interval.

For multiple batteries, simply multiplying individual power and storage is valid only if the shared site connection does not impose a lower limit. The model should apply both asset-level totals and the connection import/export caps.

## Operating strategies to compare

### Perfect-hindsight optimisation

The optimiser receives the complete historical price series for the chosen day and selects the most profitable feasible charging and discharging schedule.

This is a theoretical upper benchmark under the selected assumptions. It is not a forecast and not a claim about the revenue an operator could have known how to capture at the time.

The optimiser should be free to:

- Charge or discharge partially during an interval.
- Wait when neither action is profitable.
- Skip an apparently attractive trade to preserve storage capacity or stored energy for a better later opportunity.
- Optimise over the whole day or within user-selected trading windows.

### Fixed scheduled strategy

The scheduled strategy charges during a predetermined midday window and discharges during a predetermined evening window. It could operate at a fixed rate, follow the cheapest or most expensive intervals encountered within those windows under an explicit rule, or respond to predefined thresholds.

For a fair backtest, the schedule and its parameters must be defined without examining prices from the selected day. If the user chooses the best charging and discharging windows after seeing that day's prices, the result also contains hindsight.

This is the clearest realistic strategy for the first release because it is simple, explainable, and reproducible.

### Price-threshold strategy

This strategy charges when the observable price falls below a predefined threshold and discharges when it rises above another threshold.

It can be realistic only if the simulation respects information timing. A decision for an interval must not use a price that would not yet have been known to the operator. The project must explicitly state whether it assumes the current dispatch price is immediately actionable or applies a reporting and decision delay.

Thresholds should be set before the evaluated day or learned from an earlier training period. Selecting thresholds using the evaluated day's outcome introduces future-data leakage.

### Forecast-based strategy

A later version can generate price forecasts using only information available before each decision, then optimise against those forecasts. It can compare forecast-based performance with perfect hindsight.

The forecast backtest must use walk-forward evaluation. Training data, features, and model parameters at each decision point must exclude future observations. The application should record the model version and information cutoff used for every simulation.

## Meaning of theoretical and realistic cases

The recommended labels are:

| Result | Meaning |
| --- | --- |
| Perfect hindsight | Best feasible schedule with knowledge of the complete historical price series |
| Scheduled operation | Result of an operating schedule fixed before observing the evaluated day |
| Forecast-based operation | Result of decisions made from forecasts using only information available at the time |

Efficiency losses alone do not turn perfect hindsight into a realistic case. The main distinction is whether future prices were known when decisions were made.

The comparison between practical and hindsight performance is itself a useful result. The interface can explain whether the gap arose because the strategy charged too early, discharged before a later spike, ran out of energy, lacked sufficient charge/discharge power, or preserved capacity at the wrong time.

## Core physical model

For each five-minute interval `t`, define:

- `price[t]`: regional wholesale price in AUD/MWh.
- `charge[t]`: energy imported from the grid during the interval in MWh.
- `discharge[t]`: energy exported to the grid during the interval in MWh.
- `soc[t]`: stored energy at the end of the interval in MWh.
- `eta_charge`: charge efficiency.
- `eta_discharge`: discharge efficiency.
- `delta_hours`: interval length in hours, normally 5/60 for NEM data.

The state transition is:

```text
soc[t] = soc[t-1]
       + charge[t] * eta_charge
       - discharge[t] / eta_discharge
```

This convention measures both `charge[t]` and `discharge[t]` at the grid connection. Charging purchases `charge[t]` MWh from the grid, while only `charge[t] * eta_charge` MWh enters storage. Exporting `discharge[t]` MWh removes `discharge[t] / eta_discharge` MWh from storage.

The constraints are:

```text
minimum_soc <= soc[t] <= maximum_soc
0 <= charge[t] <= maximum_charge_mw * delta_hours
0 <= discharge[t] <= maximum_discharge_mw * delta_hours
charge[t] <= connection_import_limit_mw * delta_hours
discharge[t] <= connection_export_limit_mw * delta_hours
soc[end] = required_final_soc
```

The model should prevent simultaneous charging and discharging. Depending on the optimisation method, this can use a binary operating-mode variable or another formulation that guarantees mutually exclusive operation.

For a single-day comparison, the default should require final state of charge to equal initial state of charge. Otherwise, a simulation can appear profitable merely because it sells energy that was already stored at the beginning of the day. An advanced interface can allow a different final target but must display the value assigned to remaining or consumed stored energy.

## Financial model

For each interval:

```text
charging_cost[t] = price[t] * charge[t]
discharge_revenue[t] = price[t] * discharge[t]
```

The daily gross energy-trading margin is:

```text
gross_margin = sum(discharge_revenue[t] - charging_cost[t])
```

The model's selected variable costs are then deducted:

```text
modelled_margin = gross_margin
                - variable_market_fees
                - degradation_allowance
                - other_selected_variable_costs
```

When price is negative, `charging_cost` is negative under the simplified wholesale settlement model. Subtracting a negative cost increases margin. The interface should explain this clearly rather than displaying it as an ordinary positive expense.

Illustrative example only:

- The battery imports 1 MWh at -$30/MWh.
- Charging produces a $30 credit under the simplified wholesale settlement assumption.
- After losses, it exports 0.9 MWh at $200/MWh.
- Discharge revenue is $180.
- Gross energy-trading margin is $210 before fees and degradation.

This is not an actual historical result and does not represent a household battery tariff.

## Optimisation objective

For perfect hindsight, the objective is to maximise modelled margin over all intervals:

```text
maximise sum(
    price[t] * discharge[t]
  - price[t] * charge[t]
  - variable_costs[t]
)
```

The selected degradation model may be expressed as a cost per MWh discharged for the first version. More advanced models could use equivalent full cycles, depth of discharge, temperature, battery chemistry, or nonlinear ageing, but these are unnecessary for the MVP unless reliable assumptions are available.

The optimiser must be allowed to do nothing. A result of zero trading is correct when no feasible trade covers losses and selected costs.

## Market and business assumptions

The calculator should expose or document these assumptions:

- The battery is a price taker. Its operation does not change the historical regional price.
- The historical price is applied to the simulated import/export quantity under a simplified wholesale settlement model.
- The simulation initially covers energy arbitrage only.
- Network constraints, marginal loss factors, dispatch targets, bidding bands, rebidding, ancillary-service enablement, and detailed market registration costs are outside the initial model unless explicitly added.
- The battery can execute the modelled schedule within its power and connection limits.
- Availability is 100% unless the user supplies an availability constraint.
- Prices and dispatch intervals are complete and pass data-quality checks.
- Scaling battery count is a scenario estimate. A sufficiently large battery fleet could affect market prices, so linear scaling does not predict market-wide realised returns.

These assumptions define a useful educational and comparative tool. They should appear near results in concise language, with a detailed methodology page for users who want to inspect them.

## Wholesale versus household calculator

The first release should be explicitly described as a wholesale-market simulation.

A household battery calculator would require different inputs:

- Retail import tariff and time-of-use periods.
- Solar generation and household load.
- Feed-in tariff or dynamic export tariff.
- Export and import limits.
- Retailer rules and fees.
- Whether the customer can access wholesale prices.

Regional wholesale prices alone cannot determine a household's earnings. A future residential mode should be a distinct model, not a label applied to the wholesale calculation.

## Frontend experience

The first polished screen should include:

- A NEM region selector and historical date picker.
- Battery power, usable storage, efficiency, initial charge, and cost controls.
- Optional advanced controls for separate charge/discharge efficiencies, connection limits, reserve level, final charge target, and degradation.
- Large result cards for perfect-hindsight margin, scheduled-strategy margin, and the performance gap.
- A price chart showing the five-minute regional price.
- A charging/discharging chart with distinct import and export directions.
- A state-of-charge chart.
- A shared cursor across all charts.
- A replay mode that explains each action, such as "Charging 25 MWh at -$30/MWh" or "Waiting to retain energy for the later price peak."
- A financial breakdown of discharge revenue, charging cost or credit, energy losses, fees, degradation allowance, and final modelled margin.
- A constraint explanation showing whether the battery was limited by power, storage, state-of-charge reserve, or connection capacity.
- A shareable scenario URL that reproduces the inputs, data version, strategy, and output.

The interface should make power and energy capacity visually intuitive. For example, a 100 MW / 200 MWh configuration can be labelled as a two-hour battery at maximum discharge power.

The user should be able to switch between:

- Midday-to-evening operation.
- Whole-day optimisation.

This demonstrates whether the familiar solar-to-evening story captures the day's best opportunity or whether the strongest price spread occurred elsewhere.

## Result explanations

The application should generate concise explanations from calculated facts rather than claiming causes that the data cannot establish.

Examples:

- "Storage filled before the lowest-price interval, so the battery could not use all of that interval."
- "The scheduled strategy discharged at 6:00pm; perfect hindsight retained energy for the larger 7:05pm price spike."
- "Increasing storage did not materially improve margin because export power was the binding constraint."
- "The battery did not trade because the observed price spread did not cover efficiency losses and selected costs."
- "Negative charging prices contributed $X to the result."

The product should avoid statements such as "the price rose because this generator tripped" unless another reliable source establishes that causal connection.

## Data-ingestion and processing qualities to demonstrate

The project should make these engineering qualities observable:

- Resumable historical backfills that respect API date-range and rate limits.
- Incremental ingestion of newly completed intervals.
- Idempotent processing so retries do not create duplicates.
- Raw-source retention or source-response provenance for reproducibility.
- Explicit units and network-local timestamps.
- Detection of missing, duplicated, delayed, or revised intervals.
- Calculation and strategy versioning.
- Deterministic simulations for identical inputs and source data.
- Cached results for common dates and configurations.
- Background jobs for long multi-month or multi-year backtests.
- Operational monitoring of data freshness, ingestion failures, and simulation errors.
- A public data-coverage or methodology page.

The system should store enough provenance to answer:

- Which source intervals produced this result?
- When were those intervals ingested or last updated?
- Which assumptions and optimiser version were used?
- Can the result be reproduced later?

## Data quality and calculation correctness

High-value verification should cover:

- Energy conservation through every interval.
- State of charge never falling below its minimum or exceeding its maximum.
- Charge and discharge power respecting five-minute interval limits.
- Connection import and export limits.
- No simultaneous charging and discharging.
- Required final state of charge.
- Correct handling of negative and zero prices.
- Correct application of charge and discharge efficiency.
- Correct separation of revenue, charging cost or credit, fees, and degradation.
- Correct handling of missing or duplicated source intervals.
- Correct timezone and calendar-day boundaries.
- Perfect-hindsight optimisation performing at least as well as any other feasible strategy under exactly the same assumptions.

The product should refuse to present an authoritative result for a day with material missing price intervals, or clearly label and explain any imputation policy.

## Suggested MVP

The first release should contain:

1. NEM regions only.
2. A single historical local day per simulation.
3. Five-minute regional wholesale prices.
4. Configurable usable energy capacity and charge/discharge power.
5. Configurable efficiency, initial/final state of charge, connection limits, fees, and simple degradation allowance.
6. Perfect-hindsight optimisation over the full day.
7. A predetermined midday-charge/evening-discharge strategy.
8. Side-by-side financial and operational comparison.
9. Synchronized price, power, and state-of-charge charts.
10. Reproducible shareable scenarios and a methodology page.

The MVP should favour correctness, clarity, and one excellent end-to-end user journey over a large catalogue of partially developed analytics.

## Possible later releases

- Price-threshold strategies with explicit decision timing.
- Forecast-based walk-forward strategies.
- Month, season, and full-year backtests.
- Comparisons between NEM regions.
- Battery-duration comparisons, such as one-, two-, and four-hour configurations.
- Sensitivity analysis for efficiency, degradation, connection size, and final state of charge.
- Historical event discovery linked to GridReplay.
- Comparisons with the observed dispatch of real battery facilities, with careful recognition that energy-only data may not explain ancillary-service behaviour.
- Ancillary-service revenue modelling when appropriate data is available.
- Renewable-plus-storage co-location scenarios.
- Emissions or renewable-energy context for charging intervals, kept separate from financial optimisation unless the user selects a multi-objective strategy.
- A distinct residential tariff and behind-the-meter model.
- WEM support after its data and market rules have been separately validated.

## Open product and business-logic decisions

These questions remain for future discussion:

1. Is the target user an energy-curious member of the public, a developer or analyst, a battery project proponent, or an employer reviewing the portfolio?
2. Should the product be named BatteryLab, Battery Arbitrage Calculator, or something else?
3. Which default battery presets should be provided: household, commercial and industrial, grid scale, or named generic sizes?
4. Should charge and discharge efficiency be separate controls or represented as one round-trip-efficiency input in the basic interface?
5. What default degradation allowance is defensible, and should the interface provide presets rather than implying one universal value?
6. How should the scheduled strategy behave inside its time windows: fixed power, equal allocation, or predefined price thresholds?
7. What information delay should apply to threshold and future forecast-based strategies?
8. Should perfect hindsight finish with exactly the initial state of charge, or should the user also be able to assign a terminal value to remaining energy?
9. How should missing or revised price intervals be handled?
10. Which historical days should be featured as curated examples?
11. How much market-detail should appear in the primary interface versus the methodology page?
12. Should GridReplay be a later feature within the same product or a separate application using the same data platform?

## Portfolio presentation

The project should be easy to evaluate in under a minute while retaining technical depth for someone who explores further.

A strong demonstration path is:

1. Open a curated historical scenario.
2. See what the battery earned under a scheduled strategy.
3. Compare it with perfect hindsight.
4. Move the replay cursor to understand individual charging and discharging decisions.
5. Change battery duration or power and see which constraint changes the result.
6. Open the methodology and system-status pages to inspect assumptions, data freshness, and reproducibility.

The accompanying project description should explain the energy-market question, the scope of the financial result, the modelling assumptions, the data pipeline, and one or two engineering trade-offs. This gives interviewers useful topics to explore: market understanding, optimisation, time-series correctness, reliable ingestion, testing, observability, and frontend communication.

## Decisions captured so far

- A battery-arbitrage calculator is a strong flagship feature.
- BatteryLab is the broader experiment platform around that calculator.
- The first version should focus on historical wholesale energy arbitrage in NEM regions.
- It should compare perfect hindsight with a genuinely preselected practical strategy.
- A later forecast-based strategy must prevent future-data leakage.
- Both battery power and energy storage capacity are required inputs.
- The default single-day comparison should end at the initial state of charge.
- Efficiency, connection limits, selected fees, and degradation should be modelled explicitly.
- Results should be described as simulated energy-trading margin rather than complete investment profit.
- Ancillary services, residential tariffs, price impact, and detailed network constraints remain outside the initial model.
- The frontend should explain actions, constraints, and the gap between strategies rather than only reporting a dollar figure.

## Work completed and implementation status

The discussion has produced a product concept, alternative project directions, an MVP boundary, a physical and financial model, strategy definitions, user-interface ideas, engineering-quality goals, and open business questions.

No production code, data ingestion, optimiser, database schema, API contract, interface design, or deployment configuration has been implemented as part of this discussion. Those topics are intentionally left for the separate implementation-planning chat.
