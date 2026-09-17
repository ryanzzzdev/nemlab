# 006 — Battery model and strategy contract

Date: 2026-09-13  
Status: Accepted
Accepted for M2: 2026-09-17

## Context

Comparisons require consistent constraints and accounting. The idea document defines a mathematical model but leaves schedule allocation, defaults and tolerances open.

## Decision

Use grid-side MWh, explicit five-minute duration, distinct efficiency legs, no simultaneous charge/discharge, and equal initial/final energy. Compare deterministic price-independent scheduled operation with proven hindsight optimum under documented constraints. Reject incomplete price days. Use the [v1 engine contract](../features/battery-model-contract.md) for explicit defaults, one ordered charge/discharge cycle, price-independent terminal feasibility, tolerances, solver statuses and independent reference fixtures.

## Alternatives

Dropping the terminal condition can inflate margin by selling initial energy. Continuous relaxations can permit nonphysical simultaneous operation at negative prices. Thresholds/forecasts add information-timing requirements and remain deferred.

## Consequences and follow-up

Separate feasibility, numerical validation and accounting from solver implementation. Report differing operating windows transparently and do not call an unproven feasible result optimal.

## Acceptance source

Engineering baseline selected by the agent under the user’s instruction to proceed through runtime and model planning on 2026-09-17; this is not a claim of explicit user approval of each numerical default. Illustrative presets are not final launch assumptions. [Decision 007](007-hindsight-solver.md) now records the tested ordered-window solver and measured tolerances/performance. Public limits remain NEM-020 work. Earlier proposed mathematical principles are retained; multi-cycle schedules are deferred.

## References

[BatteryLab](../features/batterylab.md), [NEM-008](../backlog.md#nem-008), [BLK-004](../blockers.md#blk-004).
