"""Price-independent ordered-window policy — ports Java ``FixedSchedule`` and
``BatterySimulation``."""

from dataclasses import dataclass

from nemlab_core import dispatch as dispatch_module
from nemlab_core import numbers
from nemlab_core.accounting import Accounting, calculate
from nemlab_core.battery import Battery, TradingCosts
from nemlab_core.dispatch import Dispatch, Interval, Limit
from nemlab_core.prices import INTERVALS, PriceDay
from nemlab_core.windows import ScheduleWindows

FIXED_VERSION = "ordered-windows-v1"
MODEL_VERSION = "battery-v1"


def plan(battery: Battery, windows: ScheduleWindows) -> Dispatch:
    eta_c = battery.efficiency.charge
    eta_d = battery.efficiency.discharge
    charge_limit = battery.effective_charge_mw() / 12
    discharge_limit = battery.effective_discharge_mw() / 12
    headroom = battery.maximum_mwh - battery.initial_mwh
    available_charge = numbers.finite(
        "charge window energy",
        charge_limit * eta_c * (windows.charge_end - windows.charge_start),
    )
    available_discharge = numbers.finite(
        "discharge window energy",
        discharge_limit / eta_d * (windows.discharge_end - windows.discharge_start),
    )
    excursion = min(headroom, min(available_charge, available_discharge))
    if excursion == headroom:
        limit = Limit.ENERGY_HEADROOM
    elif excursion == available_charge:
        limit = Limit.CHARGE_WINDOW
    else:
        limit = Limit.DISCHARGE_WINDOW
    remaining_charge = numbers.finite("total import", excursion / eta_c)
    remaining_discharge = numbers.finite("total export", excursion * eta_d)
    energy = battery.initial_mwh
    intervals: list[Interval] = []
    for i in range(INTERVALS):
        charge = min(charge_limit, remaining_charge) if windows.can_charge(i) else 0
        discharge = (
            min(discharge_limit, remaining_discharge) if windows.can_discharge(i) else 0
        )
        remaining_charge -= charge
        remaining_discharge -= discharge
        energy += eta_c * charge - discharge / eta_d
        intervals.append(Interval(charge, discharge, energy))
    result = Dispatch(tuple(intervals), limit)
    dispatch_module.validate(battery, windows, result)
    return result


@dataclass(frozen=True)
class SimulationResult:
    """Validated complete-day fixed schedule result."""

    model_version: str
    strategy_version: str
    battery: Battery
    windows: ScheduleWindows
    costs: TradingCosts
    prices: PriceDay
    dispatch: Dispatch
    accounting: Accounting


def run(
    battery: Battery, windows: ScheduleWindows, costs: TradingCosts, prices: PriceDay
) -> SimulationResult:
    dispatch = plan(battery, windows)
    return SimulationResult(
        MODEL_VERSION,
        FIXED_VERSION,
        battery,
        windows,
        costs,
        prices,
        dispatch,
        calculate(battery, costs, prices, dispatch),
    )
