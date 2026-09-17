# Battery engine findings — plain-language explanation

Date: 2026-09-17

This is a companion to the technical [findings document](findings.md). It explains what we tested, why we tested it, and what the results mean.

## What were we trying to prove?

We wanted to answer this question:

**Can we reliably calculate the best battery trading result under our chosen rules, using Java, fast enough for the app?**

The experiment says yes, for the limited scenario we tested. It gives us confidence in the calculation engine before we build the API and user interface around it.

It does not prove that the whole website works, that it can handle many simultaneous users, or that a real battery would earn these amounts.

## What is a solver?

A solver is a software library that finds the best answer to a problem with many possible choices and rules.

For BatteryLab, we give it:

- Electricity prices for every five-minute period of a historical day.
- The battery's capacity and charging/discharging speed.
- Energy losses and selected costs.
- The times when charging and discharging are allowed.
- The requirement to finish with the same stored energy it started with.

We ask: **“Within those rules, when should the battery charge and discharge to earn the highest margin?”**

The solver we selected is called **ojAlgo**. It runs inside our Java application. It is a mathematical software library, not an AI model or a price forecasting service.

## What are the two strategies?

| Strategy | What it does |
| --- | --- |
| Fixed schedule | Follows a predetermined routine regardless of prices, even if it loses money. |
| Perfect hindsight | Looks at the entire historical day's prices and chooses the best trades allowed by the rules. |

Perfect hindsight is an idealised benchmark. It knows prices a real operator would not have known in advance. It is not a forecast or a realistic earnings promise.

Both strategies use the same battery, costs and allowed windows in this comparison. The difference is how they choose trades within those windows.

## What did we test?

### 1. Does it respect the battery's physical limits?

The calculation must not:

- Overfill the battery or use energy below its minimum reserve.
- Charge or discharge faster than the battery and connection allow.
- Create energy or ignore charging/discharging losses.
- Charge and discharge at the same time.
- Sell its starting energy without replacing it by the end of the day.

That last rule makes the daily comparison fair. Otherwise, a strategy could appear profitable simply by emptying a battery that started full.

We check the returned trading plan separately from the solver, reconstructing the stored energy throughout the day.

### 2. Does it get answers we can check ourselves?

For example, with no losses or fees, buying 1 MWh at $30 and selling it at $100 gives a $70 margin.

We test simple examples with known answers, then add complications: losses, fees, negative prices, power limits and situations where doing nothing is best.

Negative prices matter because buying electricity can earn a credit, while selling it can cost money. The calculation must handle these cases without inventing physically impossible trades.

For some tiny examples, we also list every relevant possible trading plan and compare the solver's answer with the best one. Those examples are deliberately constructed so this enumeration establishes the correct optimum.

The final build passed **47 automated test cases**. Some cases contain many scenarios, including 40 tiny enumerated examples and 20 examples with efficiencies and fees.

### 3. Is its answer actually the best?

A workable plan is not necessarily the best plan.

We calculate a separate mathematical ceiling on what any allowed plan could earn. Think of it as establishing: “No valid plan can earn more than this amount.” We then compare the solver's result with that ceiling.

We label the result **optimal within tolerance** only if:

- The solver reports that it found an optimum.
- The independent physical and financial checks pass.
- Its margin is within one cent of the calculated ceiling.
- It finishes within the configured time budget.

The technical document calls that ceiling an **upper bound**, and the difference between the result and the ceiling a **gap**. Its “dual” calculation is the mathematical method used to establish the ceiling.

If the proof is incomplete, we do not label the result perfect hindsight. We may have a valid trading plan without knowing that it is the best one.

### 4. Is it fast and small enough to run in the app?

A day contains 288 five-minute periods. We tested full days using both synthetic prices and our two saved NSW price samples.

All **15 full-day benchmark runs** passed the physical, financial and optimality checks.

| Measurement | What we observed |
| --- | --- |
| First calculation | About 166 milliseconds, including solver startup work |
| Later calculations | Roughly 2–11 milliseconds |
| Peak resident memory of the benchmark Java process | About 95 MiB |

These are measurements on the development computer. They are not promises about website response times or performance with many users. The measured process includes Java and the experiment harness, not just the solver.

## What did the comparison show?

For the sampled NSW day **11 September 2026**, the illustrative 1 MW / 2 MWh battery produced:

| Strategy | Simulated energy-trading margin |
| --- | ---: |
| Fixed schedule | $54.95 |
| Perfect hindsight within the same windows | $91.47 |

This example uses 90% round-trip efficiency, $2 per MWh import and export fees, and a $10 per exported MWh degradation allowance. Charging is allowed from 10:00–14:00 and discharging from 17:00–21:00 in NEM market time.

The improvement comes from choosing better trades within those windows. These are illustrative model assumptions, not recommended costs or evidence of actual facility earnings. The margin excludes capital costs and other items described in the [battery model contract](../../features/battery-model-contract.md).

## What happens if the calculation takes too long?

We give the solver a time budget. If it stops without proving an optimum, the application must not present the answer as perfect hindsight.

The experiment also found that the solver's time limit is cooperative: it checks when it should stop, rather than being forcibly stopped at an exact instant. A 1 millisecond budget took about 4 milliseconds to return with no solution.

We therefore proposed a five-second solver budget, plus a separate hard timeout when worker execution is implemented. The worker-level enforcement is future work.

| Technical status | Plain-language meaning |
| --- | --- |
| OPTIMAL | A physically valid result was proved best within the allowed tolerance. |
| FEASIBLE_NOT_PROVEN | A valid plan exists, but we cannot claim it is the best within our rules for proof. |
| NO_SOLUTION | No validated plan was returned, for example because the calculation budget ran out. This does not mean trading is mathematically impossible. |
| INFEASIBLE | The solver says the rules cannot be satisfied. Since doing nothing should be allowed here, this signals a modelling or numerical problem to investigate. |
| FAILED_VALIDATION | Independent checks rejected the calculation or its numerical results. |
| ERROR | The calculation encountered a software error. |

## What have we not proved?

**The tested model allows one charging window followed by one discharging window.** For example, it can charge during the middle of the day and discharge in the evening.

We have not implemented unrestricted trading throughout the day with repeated charge/discharge cycles. That requires a separate model and more testing.

We also still need to build and verify the API, worker operations, storage and user interface; test the deployed application under load; and set the final public input and resource limits.

The engine proof is a foundation for that work. The detailed equations, exact measurements, reproduction commands and limitations remain in [findings.md](findings.md).
