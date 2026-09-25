# BatteryLab price-threshold experiment

Date: 2026-09-25

Status: Implemented (2026-09-25). Engine and lifecycle in backend `98015d0` (NEM-049–NEM-050); visitor experience in frontend `d4540c7` (NEM-051). The v1 rules below are the shipped design.

## Purpose and scope

Let visitors explore “charge when cheap, discharge when expensive” by adjusting two fixed price thresholds and inspecting the resulting battery behavior. The user explicitly prioritised an interesting, understandable experiment over commercial-grade realism. Keep the existing fixed-schedule and hindsight comparison; add a price-threshold strategy rather than replacing the baseline.

Sequence: finish NEM-047–NEM-048 UI refinements, then NEM-049–NEM-051 below. This is an optional post-M4 extension, not a new launch prerequisite or a reopening of completed M4 acceptance.

## Proposed v1 rules

- Two inputs in AUD/MWh: charge below and discharge above. Allow negative thresholds; require charge threshold < discharge threshold. Preserve decimal strings and apply bounded numeric validation consistent with the request contract.
- At each five-minute interval: charge if price is strictly below the charge threshold; discharge if strictly above the discharge threshold; otherwise hold. Equality means hold. Set thresholds before the replay; do not optimise them using that day's future prices.
- Run throughout the complete market day, independently of fixed-schedule windows. Multiple cycles are allowed. Mark that difference explicitly wherever the strategies are displayed together.
- Charge/discharge at the greatest feasible power, respecting existing energy bounds, charge/discharge MW, import/export MW and efficiency. Clamp the final partial interval to the energy limit. Never charge and discharge simultaneously.
- Reuse existing energy and financial accounting: purchases, sales, import/export fees, degradation per exported MWh and physical conversion losses. Thresholds apply to the raw regional price; there is no hidden profit filter. Fees and losses can therefore make an apparently attractive threshold pair lose money.
- Example inputs: charge below 30, discharge above 150 AUD/MWh. These are editable illustrative values, not recommended trading settings. Existing site/efficiency/cost inputs are shared with the other strategies.

## Simple, explicit historical model

Use each stored interval price to evaluate the rule and settle that interval's simulated energy, assuming execution at that price for the interval. Describe this as an **idealised historical price-rule replay**, not a live controller or a reconstruction of actual NEM dispatch. It does not use later intervals, but it abstracts away publication timing, bidding, latency, ramps and dispatch uncertainty. A one-sentence UI explanation and methodology detail are sufficient; no commercial market simulator is required.

No forecasts, automatic threshold tuning, adaptive bids, household load/solar, FCAS, multi-day optimisation or new unrestricted hindsight solver in v1.

## Ending energy and comparison

Keep the experiment simple: do not force an end-of-day trade to restore initial energy. The rule may end partly charged or below its initial level. Report initial energy, final energy and the change prominently next to the threshold strategy's net trading cashflow. Do not invent a salvage price or count leftover energy as realised revenue.

The fixed-schedule/hindsight pair retains its existing equal-window and equal-terminal-energy comparison. The threshold strategy is a separate all-day experiment: do not calculate a hindsight advantage against it, rank it as the winner, or call the existing restricted hindsight result its upper bound. Explain that different operating hours and ending energy affect the comparison. A terminal-energy valuation or matched all-day hindsight benchmark can be considered later if useful, not as a prerequisite for this experiment.

## Visitor experience

- Add an optional “Price thresholds” experiment control and the two threshold fields; retain fixed schedule.
- Show the threshold dispatch alongside the existing result views with a distinct accessible series style and clear legend. Preserve automatic chart visibility from NEM-047.
- Draw labelled horizontal charge/discharge thresholds on the price chart, allowing negative values.
- Include threshold power, energy, cumulative cashflow and a small summary/financial breakdown, prominently identifying ending energy and all-day operation.
- At the selected interval, explain “Charge: below threshold”, “Discharge: above threshold”, “Hold: between thresholds”, or a binding energy/power limit. No extra execution decision is hidden in the explanation.
- Saved links reproduce the thresholds, exact price revision and resulting dispatch. Older saved results remain readable and simply omit the new experiment.

## Delivery plan

1. **NEM-049 — Deterministic threshold engine.** Finalise the v1 rules above as the versioned model contract, implement a pure strategy and reuse the accounting checks. Cover threshold equality/order, negative prices, no trades, repeated cycles, partial intervals, zero power, energy/connection limits, efficiency/fees and unequal ending energy. Verify energy conservation and no future-price dependence.
2. **NEM-050 — Persist and expose the experiment.** Add optional versioned request/result fields, include thresholds and strategy version in scenario identity, and preserve old saved results. Reuse the existing job/worker and immutable price snapshot; regenerate the contract and verify round trips and deduplication. Do not widen the existing hindsight optimality claim.
3. **NEM-051 — Interactive threshold comparison.** Add controls, chart lines/series, accounting and interval explanations. Verify saved-link reopening, old-result compatibility, themes, mobile/keyboard behavior and agreement with engine fixtures. Keep the ending-energy/comparison caveat short and visible.

These tasks implement an educational strategy, not commercial trading infrastructure. Existing data integrity and arithmetic checks still apply.
