# NEM-069 solver evidence — HiGHS port of OrderedHindsight

Recorded 2026-10-01. Java reference: `reference/java/core/.../OrderedHindsight.java`.
Python port: `core/src/nemlab_core/hindsight.py` (+ `comparison.py`).

## Runtime and native-library versions

| Component | Version |
| --- | --- |
| Python | CPython 3.13.14 (`.python-version`) |
| LP solver | HiGHS 1.12.0 (bundled in SciPy 1.18.1, `linprog(method="highs-ds")` dual simplex) |
| Replaces | ojAlgo 57.3.0 (`OrderedHindsight.SOLVER`) |
| Reported identity | `hindsight.SOLVER` = `"HiGHS 1.12.0 via SciPy 1.18.1 linprog/highs-ds"` |

`hindsight.VERSION` remains `ordered-hindsight-v1` — the mathematical model is
unchanged; only the solver/execution identity differs, which must alter scenario
keys (proven by `test_scenario_keys_change_with_python_execution_identity`).

## LP formulation (unchanged from Java)

- Stored-energy variables (charge_i, discharge_i) so the balance row is
  exactly +1/-1; `charge_unit = effChargeMW/12·ηc`,
  `discharge_unit = effDischargeMW/12/ηd`, `headroom = max−initial`.
- Constraints: Σc − Σd = 0 (equality), Σc ≤ headroom, per-variable box bounds.
- Certificate: independent minimisation LP over (λ free, μ ≥ 0, charge/discharge
  slacks ≥ 0); the bound is re-evaluated with `Decimal` arithmetic
  (`dual_upper_bound`) plus the same `1e-6 + 1e-9·scale` allowance and
  `nextafter` rounding — solver duals are never trusted.
- `can_claim_optimal` requires solver-optimal + finite gap ∈ [0, 0.01] +
  budget not expired — unchanged.

## Parity vs frozen fixtures (`tests/parity/test_java_parity.py::test_hindsight_runs`)

All 10 frozen runs: status OPTIMAL, solverState OPTIMAL, certificateState
OPTIMAL, objectives reconcile (`1e-6 + 1e-9·rel`), upper bounds and gaps
reconcile with fixture values, accounting (margin/imported/exported)
reconciles, dispatch passes `DispatchValidator`. Dispatch *vertices* differ
from ojAlgo on tied optima (expected; permitted by the plan — feasibility,
objective, bound and gap are the parity surface, not bitwise intervals).
`no-headroom` degenerate case: Java `DISTINCT` ↔ HiGHS `OPTIMAL`, status
OPTIMAL both — solver-state names are runtime-specific.

## Budget behaviour (measured 2026-10-01, this machine)

| Probe | Outcome |
| --- | --- |
| `nemlab_core` cold import (incl. SciPy) | ~255 ms |
| Cold first solve (in-process) | ~6 ms |
| Warm 288-interval solves (n=30 over fixture days) | min 2.4 / median 3.2 / max 4.0 ms |
| `Limits(0, 100000)` | NO_SOLUTION / NOT_RUN, no dispatch |
| `Limits(5000, 0)` | NO_SOLUTION / NOT_RUN, no dispatch |
| `Limits(1, 100000)` | FEASIBLE_NOT_PROVEN (primal OPTIMAL, certificate NOT_RUN), dispatch published unproven |
| `Limits(5000, 1)` / `(5000, 2)` | NO_SOLUTION / ITERATION_LIMIT, no dispatch |

Cooperative 5 s budget: warm solves use <0.1% of it. Parent 15 s deadline:
a fresh subprocess pays ~255 ms interpreter+SciPy import + ~6 ms solve,
leaving ~14.7 s headroom.

## Failure-path coverage (`core/tests/test_hindsight.py`, `test_comparison.py`)

- Zero budgets → NO_SOLUTION before solve (`omitted_proof_is_never_reported_as_optimal`).
- Iteration-limit abort → NO_SOLUTION or feasible-but-unproven; never OPTIMAL without a bounded gap.
- `Efficiency(1, denormal_min)` → discharge unit overflows to ∞ → FAILED_VALIDATION, no dispatch (Java parity).
- Degenerate allowance (capacity 1e6) → FEASIBLE_NOT_PROVEN, margin 230e6 verified, gap > 0.01.
- `comparison.validate` rejects: tampered dispatch, solverState ≠ OPTIMAL, gap > 0.01,
  elapsed ≥ limit, nonfinite metadata, missing/unexpected/mismatched threshold results,
  dispatch published on failed status.
- Exact-enumeration oracle (4-window binary dispatch, 40 seeded trials) and
  fractional-efficiency closed-form cases prove objective correctness.
