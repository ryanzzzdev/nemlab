---
project: NEMLab
created: 2026-09-11T16:59:40+10:00
updated: 2026-09-12T11:33:10+10:00
---

# NEMLab — project ideas

## Project name and scope

**NEMLab** is the chosen umbrella name for this personal project. It combines the National Electricity Market (NEM) with the idea of a laboratory for historical analysis and experiments. Focusing on the NEM is sufficient for the project's goals; WEM support is outside the chosen scope. The user reported domain availability when selecting the name on 12 September 2026; no specific domain or registration is recorded here.

GridReplay and BatteryLab remain feature names within NEMLab. The intended direction is one project with a shared backend for data ingestion and processing, serving the different analytical features. Repository structure and implementation architecture remain to be planned.

Other names considered:

- Initial suggestions: Current Atlas, GridScope, Wattwise, GridLens, Southern Current.
- Historical-analysis suggestions: WattEpoch, WattRewind, GridRetrospect, GridBackcast, GridAlmanac, WattHindsight, DispatchLens, WattAlmanac, GridMemoir, WattArchive, WattVestige.
- Additional candidates screened during online searches: VoltEpoch, WattChronicle, WattBack, WattRetrospect, WattThen, WattAfter, DispatchPast, GridAgo, DispatchArchive.

Current Atlas was rejected because it suggested a real-time focus. Searches found existing uses of VoltEpoch, WattChronicle, and WattBack. Other search results were preliminary screening, not domain or trademark clearance. NEMLab was selected because its market scope and experimental character fit the project.

## Purpose and context

Build a portfolio project that demonstrates interest in Australia's energy industry and strong software-engineering skills to potential employers. It should combine a backend that ingests and processes Open Electricity data with an engaging frontend that answers useful industry questions.

The user has an Open Electricity Academic plan. This discussion explored five ideas; BatteryLab received the most detailed attention. The scope below is a planning recommendation, not an approved implementation specification. This chat is reserved for ideas and business logic; implementation planning will happen separately.

## Ideas discussed

| Idea | Main question | Frontend experience | Engineering opportunity |
| --- | --- | --- | --- |
| **GridReplay** | What changed around a price spike, negative-price period, renewable peak, or generation drop? | Event catalogue and historical replay with synchronised price, demand, generation, and regional-flow charts | Event detection, temporal joins, historical baselines, reproducible investigations |
| **BatteryLab** | What could a battery have earned through energy arbitrage, and which strategy performs best? | Configure a battery and compare dispatch, stored energy, and trading margin under different strategies | Constrained optimisation, backtesting, simulation jobs, experiment versioning |
| **Renewable Economics Explorer** | How does the timing of renewable generation affect its wholesale value? | Compare facilities and technologies using capture prices, output profiles, and negative-price exposure | Interval alignment, weighted calculations, cohort comparisons, data-quality handling |
| **Flexibility Atlas** | When and where are steep ramps, renewable surplus, and curtailment occurring? | Calendar heatmaps, regional comparisons, and daily profiles across seasons and years | Time-series analytics, event classification, seasonal baselines |
| **Generator Observatory** | How do generating assets perform and change over time? | Facility map, generation histories, capacity factors, peer comparisons, and asset timelines | Metadata history, anomaly detection, coverage-aware metrics |

### GridReplay

An event card such as “Longest negative-price period this month” opens a replay showing what changed before, during, and after the event. Users can inspect the facilities whose output changed most. Start with one region, three event types, and one polished replay screen.

Show observations and evidence carefully: an output drop alone does not establish a generator trip or prove the cause of a price spike.

### BatteryLab

The battery-arbitrage calculator is the core feature; BatteryLab is the broader experiment platform. Users choose a region, date, battery power, storage capacity, efficiency, and costs, then compare practical operation with perfect hindsight. Later, compare battery durations, regions, and annual performance.

See [Battery arbitrage details](battery-arbitrage-details.md) for the proposed business logic and financial model.

### Renewable Economics Explorer

Calculate **capture price** as generation-weighted wholesale price, then compare it with the region's average spot price. Explore why different output profiles earn different wholesale value and how this changes over time. Distinguish calculated spot-market value from actual revenue under contracts.

### Flexibility Atlas

Let users discover unusual days through heatmaps, then inspect demand ramps, renewable output, curtailment, and inter-regional transfers. These are useful screening indicators; they do not establish connection capacity or prove that a particular site is suitable for a battery.

### Generator Observatory

Track assets through commissioning, operation, expansion, and retirement. A key challenge is historical capacity: using today's capacity for all historical generation can distort capacity factors. Preserve metadata changes or explain the available history's limitations.

## Data foundation

The core documented API inputs are regional wholesale prices, demand, generation, energy, market value, emissions, renewable metrics, curtailment, regional imports/exports, and facility/unit metadata. NEMLab covers NEM regions: NSW/ACT, Queensland, South Australia, Tasmania, and Victoria. Open Electricity also provides WEM data, but that is outside this project's chosen scope. Data availability varies by metric and period.

Academic access supports full historical access subject to dataset coverage and query limits; the documentation describes non-commercial licensing. Weather and annual pollution data are discussed in the broader guides, but their usable API access should be verified before making them a dependency.

Sources: [API overview](https://docs.openelectricity.org.au/api-reference/overview/), [metrics](https://docs.openelectricity.org.au/api-reference/metrics/), [access limits](https://docs.openelectricity.org.au/api-reference/data-limits/), [facilities](https://docs.openelectricity.org.au/guides/facilities/).

## API sufficiency: assessment pending validation

The documentation supports the core BatteryLab and GridReplay concepts, but no authenticated responses have been tested in this discussion. Documented availability is not proof of complete historical coverage or correct behaviour for every metric/endpoint combination.

| Feature | Assessment |
| --- | --- |
| BatteryLab hindsight and fixed-schedule simulations | Strong documentary support: historical regional prices plus user-supplied battery parameters are sufficient inputs. Observed battery dispatch and state of charge are not required. |
| BatteryLab forecast-based trading | Historical data can support model development, but an operational backtest must account for what was published and available at each decision time, including revisions and delays. |
| GridReplay replay and event detection | Prices, demand, generation by technology, and unit output support a focused MVP. Regional import/export totals support regional flow displays. |
| GridReplay causal explanations and individual interconnector animations | Additional evidence is needed to confirm trips, constraints, or bidding-related causes. Regional flow totals do not establish availability of named interconnector time series. |

The metrics documentation contains an aggregation table mentioning earlier bugs and a later section saying those bugs are fixed. Endpoint pages also expose broad shared metric lists. Validate actual behaviour rather than assuming every listed metric works on every endpoint.

## Data-validation exercise before implementation planning

Use Academic credentials to collect a small, reproducible sample. This exercise is proposed and has not yet been run.

1. **Recent prices:** retrieve one completed NEM market day at five-minute resolution for an initial region. Verify AUD/MWh units, numeric values, nulls, duplicates, and gaps. Confirm timestamp timezone and whether timestamps label interval starts or ends. Expect 288 intervals for a complete 24-hour NEM market day after correctly handling inclusive query boundaries; do not confuse fixed UTC+10 market time with daylight-saving civil time.
2. **Historical prices:** repeat for a date more than two years ago to verify Academic access and compare response structure and coverage. Record the actual date tested; one successful sample does not establish full-history completeness. Before simulating older settlement regimes, verify what the historical price series represents.
3. **Matching grid series:** retrieve demand, generation grouped by fuel technology, and regional imports/exports for the same windows. Confirm supported metric/endpoint combinations, units, sign conventions, grouping, and timestamp alignment. Spot-check hourly aggregation against the five-minute values; do not expect demand and generation to match without reconciling their definitions and coverage.
4. **Facility output:** discover valid facility/unit codes, then retrieve several facilities' unit-level power over the same periods. Include different technologies and check identifiers, metadata joins, missing observations, and unit coverage. A missing observation must remain distinct from zero output.
5. **Optional metrics:** sample curtailment and renewable metrics across recent and older periods. Record supported regions, earliest tested availability, nulls, errors, and gaps. Keep optional metrics out of the initial feature promise if coverage is inadequate. Separately verify named interconnector data if link-level visualisation is desired.

Save sanitised request parameters, retrieval times, sample responses, and a compact findings table: endpoint/metric, region, tested dates, expected/returned interval counts, gaps, units, and outcome. Never include API keys. Record any aggregation discrepancies, historical limitations, and follow-up questions for the provider.

**Decision gate:** proceed with BatteryLab when sampled price series are complete and their interval/price semantics are understood. Proceed with the corresponding GridReplay views when the sampled grid and facility series align reliably. Missing optional metrics should narrow feature scope rather than block the core products. Before advertising support for all regions or a long historical range, extend validation to that promised coverage.

Endpoint references: [market data](https://docs.openelectricity.org.au/api-reference/market/get-network-data/), [network generation](https://docs.openelectricity.org.au/api-reference/data/get-network-data/), [facility time series](https://docs.openelectricity.org.au/api-reference/data/get-facility-data/).

## Recommended direction and shared engineering goals

BatteryLab offers a focused first product with an understandable question and substantial algorithmic depth. GridReplay is a complementary expansion: discover an interesting historical day, then simulate a battery through it. Renewable Economics could reuse the same price and generation pipeline later.

Across any idea, demonstrate resumable ingestion, safe retries, explicit units and timezones, missing-data detection, reproducible calculations, versioned results, monitoring, and a deployed demo. A visitor should understand one interesting result within a minute and be able to inspect the methodology afterward.

Next planning decisions: select the first product and audience, agree the MVP boundaries, validate actual API responses, and choose architecture in the implementation chat. No implementation was produced in this discussion.
