"""Exact ordered-window LP — ports Java ``OrderedHindsight`` onto HiGHS.

The primal solves in *stored-energy* variables so balance coefficients are
exactly +1/-1. Dispatch and accounting are reconstructed and validated
independently of the solver, and the dual upper bound is re-evaluated in
exact decimal arithmetic from whatever multipliers the certificate LP
returned — solver duals are never trusted.

HiGHS (bundled with SciPy, ``linprog(method="highs-ds")``) replaces ojAlgo.
``time_limit`` maps the millisecond cooperative budget and ``maxiter`` maps
the simplex iteration budget; feasibility tolerances are tightened to 1e-9
so a solver-certified point cannot straddle the 1e-7 dispatch validator
boundary. Only a certified OPTIMAL outcome publishes dispatch.
"""

import math
import re
import time
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

import numpy as np
import scipy.optimize
from scipy.optimize._highspy import _core as _highs

from nemlab_core import numbers
from nemlab_core.accounting import Accounting, calculate, reconciles
from nemlab_core.battery import Battery, TradingCosts
from nemlab_core.dispatch import Dispatch, Interval, Limit
from nemlab_core.dispatch import validate as validate_dispatch
from nemlab_core.prices import INTERVALS, PriceDay
from nemlab_core.windows import ScheduleWindows

VERSION = "ordered-hindsight-v1"
HIGHS_VERSION = (
    f"{_highs.HIGHS_VERSION_MAJOR}."
    f"{_highs.HIGHS_VERSION_MINOR}."
    f"{_highs.HIGHS_VERSION_PATCH}"
)
SOLVER = f"HiGHS {HIGHS_VERSION} via SciPy {scipy.__version__} linprog/highs-ds"
METHOD = "highs-ds"
GAP_TOLERANCE = 0.01


class Status(Enum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE_NOT_PROVEN = "FEASIBLE_NOT_PROVEN"
    NO_SOLUTION = "NO_SOLUTION"
    INFEASIBLE = "INFEASIBLE"
    FAILED_VALIDATION = "FAILED_VALIDATION"
    ERROR = "ERROR"


@dataclass(frozen=True)
class Limits:
    milliseconds: int
    iterations: int

    def __post_init__(self) -> None:
        if self.milliseconds < 0 or self.milliseconds > 60_000 or self.iterations < 0:
            raise ValueError(
                "limits require 0..60000 milliseconds and nonnegative iterations"
            )

    @classmethod
    def standard(cls) -> "Limits":
        return cls(5_000, 100_000)


@dataclass(frozen=True)
class Outcome:
    """Dispatch/accounting are None when no independently validated solution
    exists; bound/gap may be unavailable."""

    status: Status
    solver_state: str
    certificate_state: str
    dispatch: Dispatch | None
    accounting: Accounting | None
    solver_objective: float | None
    upper_bound: float | None
    absolute_gap: float | None
    elapsed_nanos: int
    limits: Limits
    diagnostic: str


def can_claim_optimal(
    solver_optimal: bool, gap: float | None, budget_expired: bool
) -> bool:
    return (
        solver_optimal
        and gap is not None
        and math.isfinite(gap)
        and 0 <= gap <= GAP_TOLERANCE
        and not budget_expired
    )


def dual_upper_bound(
    windows: ScheduleWindows,
    buy: list[float],
    sell: list[float],
    charge_unit: float,
    discharge_unit: float,
    headroom: float,
    lam: float,
    mu: float,
) -> float:
    """Evaluate the Lagrangian upper bound with a conservative numerical
    allowance. ``Decimal`` operations on exact float representations avoid
    cancellation in the certificate calculation."""
    l_dec, m_dec = Decimal(lam), Decimal(mu)
    bound = Decimal(headroom) * m_dec
    coefficient_scale = 0.0
    for i in range(INTERVALS):
        if windows.can_charge(i):
            coefficient_scale += abs(buy[i]) * charge_unit
        if windows.can_discharge(i):
            coefficient_scale += abs(sell[i]) * discharge_unit
        if windows.can_charge(i):
            term = Decimal(-buy[i]) - l_dec - m_dec
            bound += Decimal(charge_unit) * max(term, Decimal(0))
        if windows.can_discharge(i):
            term = Decimal(sell[i]) + l_dec
            bound += Decimal(discharge_unit) * max(term, Decimal(0))
    value = numbers.finite("dual upper bound", float(bound))
    return numbers.finite(
        "dual bound with allowance",
        math.nextafter(
            value + 1e-6 + 1e-9 * max(abs(value), coefficient_scale), math.inf
        ),
    )


def solve(
    battery: Battery,
    windows: ScheduleWindows,
    costs: TradingCosts,
    prices: PriceDay,
    limits: Limits,
) -> Outcome:
    started = time.monotonic_ns()
    if limits.milliseconds == 0 or limits.iterations == 0:
        return _failure(
            Status.NO_SOLUTION,
            "NOT_RUN",
            "Budget exhausted before solve",
            started,
            limits,
        )
    try:
        # Stored-energy variables make balance coefficients exactly +1/-1.
        charge_unit = numbers.finite(
            "stored charge limit",
            battery.effective_charge_mw() / 12 * battery.efficiency.charge,
        )
        discharge_unit = numbers.finite(
            "stored discharge limit",
            battery.effective_discharge_mw() / 12 / battery.efficiency.discharge,
        )
        headroom = battery.maximum_mwh - battery.initial_mwh
        charge_idx = [i for i in range(INTERVALS) if windows.can_charge(i)]
        discharge_idx = [i for i in range(INTERVALS) if windows.can_discharge(i)]
        buy = [0.0] * INTERVALS
        sell = [0.0] * INTERVALS
        for i in charge_idx:
            buy[i] = numbers.finite(
                "stored import cost",
                (float(prices.intervals[i].price) + costs.import_fee)
                / battery.efficiency.charge,
            )
        for i in discharge_idx:
            sell[i] = numbers.finite(
                "stored export revenue",
                (
                    float(prices.intervals[i].price)
                    - costs.export_fee
                    - costs.degradation_per_exported_mwh
                )
                * battery.efficiency.discharge,
            )
        nc, nd = len(charge_idx), len(discharge_idx)
        # Minimise buy·c - sell·d: the negation of the primal margin.
        objective = np.array(
            [buy[i] for i in charge_idx] + [-sell[i] for i in discharge_idx]
        )
        balance = np.array([[1.0] * nc + [-1.0] * nd])
        capacity = np.array([[1.0] * nc + [0.0] * nd])
        bounds = [(0.0, charge_unit)] * nc + [(0.0, discharge_unit)] * nd
        if _expired(started, limits):
            return _failure(
                Status.NO_SOLUTION,
                "NOT_RUN",
                "Budget exhausted building model",
                started,
                limits,
            )
        res = scipy.optimize.linprog(
            objective,
            A_ub=capacity,
            b_ub=np.array([headroom]),
            A_eq=balance,
            b_eq=np.array([0.0]),
            bounds=bounds,
            method=METHOD,
            options=_options(limits, started),
        )
        state = _state_name(res)
        if state == "INFEASIBLE":
            return _failure(
                Status.INFEASIBLE,
                state,
                "Idle is feasible: investigate solver/model numerics",
                started,
                limits,
            )
        solver_optimal = res.status == 0
        x = getattr(res, "x", None)
        if not solver_optimal and (
            x is None or res.fun is None or not np.isfinite(x).all()
        ):
            return _failure(
                Status.ERROR if res.status == 4 else Status.NO_SOLUTION,
                state,
                "No solver-certified feasible point",
                started,
                limits,
            )
        assert x is not None
        charge_col = {i: k for k, i in enumerate(charge_idx)}
        discharge_col = {i: nc + k for k, i in enumerate(discharge_idx)}
        intervals: list[Interval] = []
        energy = float(battery.initial_mwh)
        eta_c = float(battery.efficiency.charge)
        eta_d = float(battery.efficiency.discharge)
        for i in range(INTERVALS):
            c = float(x[charge_col[i]]) / eta_c if i in charge_col else 0.0
            d = float(x[discharge_col[i]]) * eta_d if i in discharge_col else 0.0
            energy += eta_c * c - d / eta_d
            intervals.append(Interval(c, d, energy))
        dispatch = Dispatch(tuple(intervals), Limit.NOT_EVALUATED)
        validate_dispatch(battery, windows, dispatch)
        accounting = calculate(battery, costs, prices, dispatch)
        # +0.0 normalises -0.0 so stored payloads render like Java's 0.0.
        solver_objective = numbers.finite("solver objective", -float(res.fun) + 0.0)
        if not reconciles(solver_objective, accounting.margin):
            return _failure(
                Status.FAILED_VALIDATION,
                state,
                "Objective differs from independent accounting",
                started,
                limits,
            )
        upper = None
        gap = None
        certificate_state = "NOT_RUN"
        if not _expired(started, limits):
            certificate = _certificate(
                windows,
                buy,
                sell,
                charge_unit,
                discharge_unit,
                headroom,
                limits,
                started,
            )
            certificate_state = certificate[0]
            upper = certificate[1]
            if upper is not None:
                gap = upper - accounting.margin
                if not math.isfinite(gap) or gap < 0:
                    return _failure(
                        Status.FAILED_VALIDATION,
                        state,
                        "Invalid primal/dual bound",
                        started,
                        limits,
                    )
        proven = can_claim_optimal(solver_optimal, gap, _expired(started, limits))
        return Outcome(
            Status.OPTIMAL if proven else Status.FEASIBLE_NOT_PROVEN,
            state,
            certificate_state,
            dispatch,
            accounting,
            solver_objective,
            upper,
            gap,
            time.monotonic_ns() - started,
            limits,
            "Validated with independently evaluated dual upper bound"
            if proven
            else "Feasible point; proof or budget incomplete",
        )
    except ValueError as ex:
        return _failure(
            Status.FAILED_VALIDATION, "VALIDATION_ERROR", str(ex), started, limits
        )
    except Exception as ex:
        return _failure(
            Status.ERROR,
            "ERROR",
            f"{type(ex).__name__}: {ex}",
            started,
            limits,
        )


def _certificate(
    windows: ScheduleWindows,
    buy: list[float],
    sell: list[float],
    charge_unit: float,
    discharge_unit: float,
    headroom: float,
    limits: Limits,
    started: int,
) -> tuple[str, float | None]:
    """Minimise headroom·mu + unit·slacks subject to the dual covering
    constraints; the returned bound is re-evaluated, not read from the solver."""
    charge_idx = [i for i in range(INTERVALS) if windows.can_charge(i)]
    discharge_idx = [i for i in range(INTERVALS) if windows.can_discharge(i)]
    nc, nd = len(charge_idx), len(discharge_idx)
    n = 2 + nc + nd
    objective = np.zeros(n)
    objective[1] = headroom
    objective[2:] = [charge_unit] * nc + [discharge_unit] * nd
    rows = np.zeros((nc + nd, n))
    rhs = np.zeros(nc + nd)
    for k, i in enumerate(charge_idx):
        # s_k + lam + mu >= -buy_i  <=>  -lam - mu - s_k <= buy_i
        rows[k, 0] = -1.0
        rows[k, 1] = -1.0
        rows[k, 2 + k] = -1.0
        rhs[k] = buy[i]
    for k, i in enumerate(discharge_idx):
        # t_k - lam >= sell_i  <=>  lam - t_k <= -sell_i
        row = nc + k
        rows[row, 0] = 1.0
        rows[row, 2 + nc + k] = -1.0
        rhs[row] = -sell[i]
    bounds = [(None, None), (0.0, None)] + [(0.0, None)] * (nc + nd)
    if _expired(started, limits):
        return "BUDGET_EXHAUSTED", None
    res = scipy.optimize.linprog(
        objective,
        A_ub=rows,
        b_ub=rhs,
        bounds=bounds,
        method=METHOD,
        options=_options(limits, started),
    )
    state = _state_name(res)
    if res.status != 0 or res.x is None or not np.isfinite(res.x).all():
        return state, None
    lam = numbers.finite("dual lambda", float(res.x[0]))
    # Any lambda and nonnegative mu give an upper bound; the slacks are
    # rebuilt exactly instead of trusting dual feasibility.
    mu = max(0.0, numbers.finite("dual mu", float(res.x[1])))
    return state, dual_upper_bound(
        windows, buy, sell, charge_unit, discharge_unit, headroom, lam, mu
    )


def _state_name(res: scipy.optimize.OptimizeResult) -> str:
    """Truthful HiGHS model-status name (e.g. ``OPTIMAL``, ``TIME_LIMIT``)."""
    match = re.search(r"HiGHS Status (\d+)", str(res.message))
    if match:
        try:
            raw = _highs.HighsModelStatus(int(match.group(1))).name
            return re.sub(r"(?<!^)(?=[A-Z])", "_", raw.removeprefix("k")).upper()
        except ValueError:
            pass
    return {0: "OPTIMAL", 1: "LIMIT", 2: "INFEASIBLE", 3: "UNBOUNDED"}.get(
        res.status, "ERROR"
    )


def _options(limits: Limits, started: int) -> dict[str, object]:
    remaining_ms = limits.milliseconds - (time.monotonic_ns() - started) / 1e6
    return {
        "time_limit": max(0.001, remaining_ms / 1000.0),
        "maxiter": limits.iterations,
        "presolve": True,
        "disp": False,
        "primal_feasibility_tolerance": 1e-9,
        "dual_feasibility_tolerance": 1e-9,
    }


def _expired(started: int, limits: Limits) -> bool:
    return time.monotonic_ns() - started >= limits.milliseconds * 1_000_000


def _failure(
    status: Status, state: str, message: str, started: int, limits: Limits
) -> Outcome:
    return Outcome(
        status,
        state,
        "NOT_AVAILABLE",
        None,
        None,
        None,
        None,
        None,
        time.monotonic_ns() - started,
        limits,
        message,
    )
