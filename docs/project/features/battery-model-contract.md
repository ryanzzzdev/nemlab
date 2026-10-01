# Battery engine contract v1

Date: 2026-09-17  
Status: M2 fixed schedule, input validation, physical validation and accounting implemented and tested in core. Ordered-window hindsight is implemented and independently certified; unrestricted hindsight is deferred. Demo preset values are illustrative, not industry recommendations or a final launch UI decision.

This is the executable specification for [BatteryLab](batterylab.md), refining the earlier [mathematical proposal](../../initial-ideas/battery-arbitrage-details.md). Model version: `battery-v1`; schedule version: `ordered-windows-v1`.

## Inputs and time

A production run requires one complete regional NEM market day: exactly 288 distinct, contiguous five-minute intervals, fixed UTC+10 without daylight saving. Normalise OE interval-end timestamps into explicit start/end instants; the first interval ends at 00:05 and the last at next midnight. Reject missing, duplicate, non-finite, irregular or wrong-region prices; never interpolate or replace missing values with zero. Zero and negative prices are valid. Smaller synthetic horizons are test inputs only.

Use MW, MWh, hours and AUD/MWh. Aggregate identical batteries before applying shared connection limits; the engine accepts aggregate values. Require finite numbers; capacity > 0; power, connection limits, fees and degradation >= 0; `0 <= E_min <= E_initial <= E_max <= capacity`; efficiencies in `(0,1]`. Terminal energy is always initial energy in v1. Zero power/connection headroom is valid and yields no trading.

Accept either both efficiency legs or one round-trip efficiency, never ambiguous simultaneous inputs. For round-trip input r, normalise to `eta_c = eta_d = sqrt(r)` and persist both derived legs. No implicit defaults in the core constructor: clients must pass a complete normalised scenario.

Illustrative demo configuration: 1 MW charge/discharge and import/export limits, 2 MWh capacity, E_min=0, E_max=2, E_initial=0, r=0.90, all fees/degradation=0. Explicitly display excluded costs. Default scheduled windows: 10:00–14:00 charge, 17:00–21:00 discharge, NEM time. Region/date must come from available validated coverage rather than a hard-coded promise of history.

## Physical and financial invariants

For each interval dt=1/12 h, grid imports c and exports d are nonnegative MWh:

```text
E[t] = E[t-1] + eta_c*c[t] - d[t]/eta_d
c[t] <= min(charge_MW, import_limit_MW)*dt
d[t] <= min(discharge_MW, export_limit_MW)*dt
E_min <= E[t] <= E_max
c[t] = 0 OR d[t] = 0
E[last] = E_initial
```

Outside the corresponding operating window, its dispatch must be zero. There is no self-discharge or auxiliary load in v1.

```text
charging_cost = sum(price[t]*c[t])
revenue = sum(price[t]*d[t])
fees = import_fee*sum(c) + export_fee*sum(d)
degradation = degradation_per_exported_MWh*sum(d)
margin = revenue - charging_cost - fees - degradation
losses_MWh = (1-eta_c)*sum(c) + (1/eta_d-1)*sum(d)
```

Negative charging cost is a credit. Do not subtract losses financially a second time. Independently reconstruct energy and totals from returned dispatch.

## Fixed schedule: one ordered cycle

V1 accepts exactly one nonempty charging window followed by one nonempty discharging window. Boundaries are five-minute aligned in [00:00,24:00]; windows are half-open by interval start, cannot wrap midnight, overlap or be reversed. Adjacent windows are valid. Reject unsupported window configurations rather than silently rearranging them. Multi-cycle schedules are deferred.

Let Nc and Nd be the number of eligible charge/discharge intervals, Pc/Pd the effective MW limits above. Compute the stored-energy excursion before looking at prices:

```text
Q = min(E_max-E_initial, eta_c*Pc*Nc/12, Pd*Nd/(12*eta_d))
C_total = Q/eta_c
D_total = Q*eta_d
```

Allocate C_total greedily from the earliest charging interval at Pc/12 MWh per interval, with a partial last active interval. Allocate D_total the same way from the earliest discharging interval at Pd/12. All remaining dispatch is zero. This produces the maximum feasible single charge-then-discharge excursion, always returns to initial energy, and never draws below initial energy. E_min still applies but does not increase the scheduled excursion. Q=0 is a valid idle result with an explanatory limiting reason.

Prices and costs affect accounting only, never schedule allocation or terminal repair. A losing schedule remains a losing schedule. Changing any price while holding physical inputs/windows fixed must leave dispatch identical.

## Hindsight and comparison

The primary comparison uses the same charge/discharge windows and all physical/cost/terminal constraints. Maximise margin. No trading is always feasible. Optional whole-day hindsight permits either action in any interval, still with explicit exclusivity; label it as a different operating opportunity and not an equal-window strategy comparison.

The solver must enforce exclusivity, including at negative prices; do not rely on positive-price intuition or an unchecked continuous relaxation. Multiple optimal schedules are allowed; compare objective and constraints rather than requiring identical dispatch. Persist solver/version/options, objective, bound, gap and termination status when available.

Only label a result “optimal within tolerance” when the solver establishes that status, the absolute objective bound gap is <= AUD 0.01, and independent feasibility/accounting checks pass. A feasible timeout is `FEASIBLE_NOT_PROVEN`; preserve it diagnostically but do not show it as perfect hindsight. Other outcomes include `FAILED_VALIDATION`, `INFEASIBLE` and `ERROR`. With validated inputs idle is feasible, so an infeasible solver result signals a modelling/numerical problem. The [NEM-010 findings](../evidence/engine/findings.md) select ojAlgo 57.3.0, define bound certification and propose execution limits. `NO_SOLUTION` explicitly covers exhausted budgets without a feasible point; `OPTIMAL` means optimal within the documented tolerance.

## Numerical contract

Use Java double for physical calculations and optimisation; parse/preserve source price decimals and normalised input values for provenance. Do not round intermediate dispatch, state or objective. Reject overflow/non-finite derived quantities. Compensated summation is preferred for totals.

Independent validation tolerances: 1e-7 MWh absolute for each energy bound, interval balance, terminal balance and per-interval energy limit; exclusivity fails if both c and d exceed 1e-7 MWh. Accounting reconciliation tolerance is AUD 1e-6 absolute plus 1e-9 times the larger absolute compared total. These tolerances are validation allowances, not extra dispatch capacity; never silently repair an invalid result. NEM-010 must measure whether these values are achievable at supported scale and record a versioned change if needed. Public scale limits remain a launch task.

Recompute solver margin from dispatch, compare using accounting tolerance, and compare proven optimum against baseline with AUD 0.01 plus accounting tolerance. Display currency at two decimals, energy at three and MW at three, HALF_UP; persist unrounded values. Cumulative totals are computed before display rounding, so show that rounded components may differ by a cent.

## Independent reference fixtures

All cases below use two adjacent five-minute intervals, first charge-only and second discharge-only, E_initial=E_min=0, zero costs, unit efficiencies unless overridden. Extend to 288 intervals with idle windows when testing production day validation. Expected values follow direct arithmetic, not a solver's output.

| Case | Inputs | Expected fixed schedule and optimum |
| --- | --- | --- |
| Negative purchase | capacity=1, Pc=Pd=12, prices=(-30,200) | c=(1,0), d=(0,1), E=(1,0), margin=230; optimum=230 |
| Losses and costs | capacity=1, Pc=Pd=12, eta_c=1, eta_d=.9, prices=(-30,200), import/export fees=2, degradation=10 | imports=1, exports=.9, losses=.1, charging cost=-30, revenue=180, fees=3.8, degradation=9, margin=197.2; optimum=197.2 |
| Losing schedule | capacity=1, Pc=Pd=12, prices=(100,10) | fixed imports=exports=1, margin=-90; hindsight idle, margin=0 |
| Export connection limit | capacity=1, charge/discharge power=12, import limit=12, export limit=6, prices=(0,100) | Q=.5, imports=exports=.5, final energy=0, margin=50; optimum=50 |
| No headroom | capacity=1, E_initial=E_max=1, Pc=Pd=12, prices=(0,100) | both strategies idle under ordered windows, energy stays 1, margin=0 |
| Zero prices | capacity=1, Pc=Pd=12, prices=(0,0) | fixed imports=exports=1, margin=0; optimum=0 with nonunique dispatch |
| Disabled import | capacity=1, Pc=0, Pd=12, prices=(-30,200) | both idle, final energy=0, margin=0 |

Additional negative-sale case: unit efficiency and prices=(-30,-10) still gives margin=20 for a full cycle. Terminal condition prevents selling unreplaced initial inventory. For unrestricted one-interval hindsight at price=-100, E_initial=E_min=E_max=0, capacity=1 and eta_c=eta_d=.9, only idle is physical; a relaxation admitting simultaneous import/export would incorrectly earn money.

[NEM-009](../backlog.md#nem-009) implements the fixed-schedule references as [Java tests](../../../reference/java/core/src/test/java/au/nemlab/batterylab/BatteryEngineTest.java), including rejection cases, price permutation, partial allocation, nonzero initial energy, round-trip efficiencies and 200 seeded physical/accounting scenarios. Both validated NSW1 days run from saved fixtures. [NEM-010](../backlog.md#nem-010) validates the ordered-window optimum references against ojAlgo, tiny exact enumeration and fractional manual optima; see the [solver tests](../../../reference/java/core/src/test/java/au/nemlab/batterylab/HindsightTest.java). The unrestricted example remains a requirement for any future whole-day solver, not implemented evidence. Display rounding belongs to the later presentation boundary; the core returns unrounded values.
