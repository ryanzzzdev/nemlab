# NEM-010 — Ordered-window hindsight evaluation

For a nontechnical introduction, read [the plain-language explanation](findings-explained.md).

Date: 2026-09-17  
Outcome: Pass for the v1 ordered-window comparison. Whole-day/unrestricted optimisation is not implemented or certified.

## Reproduction and environment

```sh
export JAVA_HOME=/usr/lib/jvm/java-25-openjdk-amd64
./gradlew clean build :core:hindsightBenchmark --offline --no-daemon
```

The first dependency resolution requires network access; subsequent runs are offline. The benchmark intentionally overwrites [benchmark.csv](benchmark.csv) and [budget-probes.csv](budget-probes.csv). The [harness](../../../../reference/java/core/src/test/java/au/nemlab/batterylab/HindsightBenchmark.java) runs in a separate JVM with `-Xmx512m -XX:ActiveProcessorCount=2`. These are local experiments, not production SLA/load tests.

Environment: Linux 7.0.0-31-generic x86_64, Intel Core Ultra 5 225H, OpenJDK 25.0.4+7 Ubuntu, Gradle 9.7.1, ojAlgo 57.3.0, JUnit 6.1.3. No API, database or network request is part of measured solving.

`elapsed_ms` covers model creation, primal solve, physical/accounting validation and dual certification. `cpu_ms` is process CPU time, includes JVM work and has coarse resolution (zero is possible for a short run). `heap_peak_mib` sums per-pool peak usage reset before each solve; it is an approximate conservative JVM heap measurement, not retained solver allocation. `jvm_peak_rss_kib` is Linux VmHWM: cumulative process peak, not per-case incremental memory. First recent run includes solver cold-start work; all later runs share the same JVM. No claims about statistically stable percentiles.

## Exact model and exclusivity

This formulation is valid only for one charge window followed by one discharge window. They are disjoint by validated construction; there is no interval with both variables, so exclusivity is enforced structurally even at negative prices. This is an exact LP for this scope, not a relaxation of an unrestricted battery model.

Let x_i be stored energy added by charging, y_j stored energy removed by discharging:

```text
u = eta_c * min(charge_MW, import_limit_MW) / 12
v = min(discharge_MW, export_limit_MW) / (12 * eta_d)
H = E_max - E_initial
b_i = (price_i + import_fee) / eta_c
s_j = (price_j - export_fee - degradation) * eta_d

maximise sum(s_j*y_j) - sum(b_i*x_i)
0 <= x_i <= u; 0 <= y_j <= v
sum(x_i) = sum(y_j)
sum(x_i) <= H
```

All charging precedes all discharging; therefore these aggregate constraints imply every intermediate state lies between E_initial and E_max. E_initial is validated >= E_min. Reconstruct grid imports `x/eta_c`, exports `y*eta_d` and all 288 energy states, then independently validate physical constraints and recompute accounting. Idle is always feasible. No result is repaired by clipping dispatch.

## Independent bound and numerical checks

A second LP finds dual multipliers lambda (free) and mu >= 0. For *any* such multipliers the following is an upper bound on every feasible primal objective:

```text
U = mu*H
  + sum(u * max(0, -b_i-lambda-mu))
  + sum(v * max(0, s_j+lambda))
```

This follows by adding lambda times the zero energy balance and mu times unused nonnegative headroom to the primal objective, then maximising each bounded variable independently. Rebuild the positive-part terms from multipliers rather than trusting reported dual slacks/objective. BigDecimal evaluates the expression on the exact binary-double coefficient values. Add a conservative numerical allowance `1e-6 + 1e-9*max(abs(U), sum(abs(b_i)*u)+sum(abs(s_j)*v))`, then round upward to double. Large or badly scaled scenarios can fail the one-cent proof gate; never silently widen it.

ojAlgo feasibility context is precision 14, scale 10. Independent physical tolerance remains 1e-7 MWh; accounting remains 1e-6 AUD + 1e-9 relative. Label `OPTIMAL` only if the primal solver reports optimality, all independent checks pass, evaluated bound minus recomputed margin is in [0,0.01] AUD, and the overall budget has not elapsed. Save raw primal/certificate states, bound, gap, elapsed time and limits. Solver/strategy versions are explicit constants in the implementation.

## Correctness evidence

The clean experiment build passed 46 cases. A final `./gradlew build --offline --no-daemon` after adding the oversized-scenario regression passed **47 JUnit cases, zero failures/errors/skips**. This includes the prior 33 core cases, 40 seeded tiny cases exhaustively enumerated inside one test, and 20 fractional efficiency/fee cases inside another. Enumeration uses unit capacities and energy balance (an integral flow polytope), so binary enumeration finds the continuous optimum for those particular tiny instances. It is not claimed to prove arbitrary MIP correctness.

Manual oracles cover negative purchases/sales, zero prices, deliberately losing schedules, .9 discharge efficiency with fees, connection limits, full initial inventory, disabled power and legitimate loss-making/credit-earning cycles. Every tiny enumerated solution is compared to the feasible fixed baseline. Altered physical outputs and accounting are checked by the NEM-009 validator tests. Status-gate tests reject feasible-but-unproven, expired, missing-bound, nonfinite and excessive-gap proofs. The two immutable NSW1 source fixtures require no credentials.

## Full-day measurements

All cases contain 288 five-minute intervals, r=.9, import/export fees=2 AUD/MWh, degradation=10 AUD/exported MWh, E_initial=0. Standard site is 1 MW / 2 MWh; large-site is 100 MW / 200 MWh. OE cases use 10:00–14:00 and 17:00–21:00 NEM windows. Synthetic cases use first-half charging and second-half discharging (144 eligible intervals each).

| Case | Fixed margin AUD | Hindsight margin AUD | Wall range ms, three runs |
| --- | ---: | ---: | ---: |
| NSW1 2026-09-11 | 54.949676 | 91.472558 | 5.10–165.55 (includes cold start) |
| NSW1 2023-09-11 | 437.258414 | 479.141462 | 3.62–10.42 |
| Synthetic varying prices | -72.874143 | 513.131266 | 7.21–10.09 |
| Synthetic all -100 prices | -5.902918 | 0 | 4.05–4.50 |
| NSW1 historical, large site | 43725.841418 | 47914.146176 | 2.22–2.46 |

All 15 runs: raw primal/certificate states OPTIMAL, independent status OPTIMAL, optimum >= baseline. Largest bound gap: AUD 0.000100675. Maximum measured pooled heap peak: 28.75 MiB; cumulative RSS peak: 96,784 KiB (~94.52 MiB). Resource use includes the harness/JVM. Margins are simulated under illustrative assumptions, not historical facility revenue.

## Termination and execution limits

Actual probes: zero time and zero iteration limits return `NO_SOLUTION/NOT_RUN` without a dispatch; 1 ms and one-iteration probes returned `NO_SOLUTION/UNEXPLORED`. The 1 ms run took 4.19 ms. Library aborts are cooperative; model construction, presolve and validation can overrun. A feasible solver return without a completed proof or within-budget certification is `FEASIBLE_NOT_PROVEN`, never perfect hindsight. That classification is regression-tested; the short probes did not happen to yield a feasible incomplete point. A separate oversized-scenario test produced an actual `FEASIBLE_NOT_PROVEN` result: the dispatch is feasible, but its conservative numerical bound gap exceeds one cent. It was preserved without widening the proof tolerance.

`INFEASIBLE` is a model/numerical diagnostic because idle should be feasible. Nonfinite arithmetic or physical/accounting/bound failure yields `FAILED_VALIDATION`; runtime library exceptions yield `ERROR`. Failed outcomes contain no publishable dispatch. If a feasible result is preserved without proof, consumers must inspect its status before displaying a comparison.

Proposed operational baseline: one active simulation per worker, 5-second cooperative budget shared across primal/dual work, 100,000 iterations per solve, 512 MiB JVM heap and a provisionally 1 GiB process/container budget. Add a 15-second external process watchdog when worker execution is implemented; a Java Future timeout alone does not stop CPU work. These deployment limits are not implemented by this library and need measurement on the chosen host. NEM-013 owns enforcement; NEM-020 owns load/resource validation. Initially admit single-day ordered-window scenarios only; final public power/capacity/efficiency limits require explicit API validation. The measured large-site case is not an exhaustive numerical envelope.

## Choice and remaining scope

Select ojAlgo 57.3.0 for ordered-window v1 (see [decision 007](../../decisions/007-hindsight-solver.md)). The model and tests do not support overlapping windows, multiple cycles or whole-day unrestricted operation. Those require a separate exclusivity formulation, correctness proof and benchmark before exposure. They are optional and deferred, not required to close the agreed primary comparison's M2 gate.
