"""Immutable unrounded interval dispatch and independent validation."""

from dataclasses import dataclass
from enum import Enum

from nemlab_core import numbers
from nemlab_core.battery import Battery
from nemlab_core.prices import INTERVALS
from nemlab_core.windows import ScheduleWindows

ENERGY_TOLERANCE = 1e-7


class Limit(Enum):
    ENERGY_HEADROOM = "ENERGY_HEADROOM"
    CHARGE_WINDOW = "CHARGE_WINDOW"
    DISCHARGE_WINDOW = "DISCHARGE_WINDOW"
    NOT_EVALUATED = "NOT_EVALUATED"


@dataclass(frozen=True)
class Interval:
    imported_mwh: float
    exported_mwh: float
    ending_energy_mwh: float

    def __post_init__(self) -> None:
        numbers.nonnegative("imported energy", self.imported_mwh)
        numbers.nonnegative("exported energy", self.exported_mwh)
        numbers.finite("ending energy", self.ending_energy_mwh)


@dataclass(frozen=True)
class Dispatch:
    intervals: tuple[Interval, ...]
    limiting_reason: Limit

    def __post_init__(self) -> None:
        object.__setattr__(self, "intervals", tuple(self.intervals))


def validate(battery: Battery, windows: ScheduleWindows, dispatch: Dispatch) -> None:
    _check(battery, windows, dispatch, terminal=True)


def validate_unrestricted(battery: Battery, dispatch: Dispatch) -> None:
    """All-day dispatch with no schedule windows and no forced terminal energy."""
    _check(battery, None, dispatch, terminal=False)


def _check(
    battery: Battery,
    windows: ScheduleWindows | None,
    dispatch: Dispatch,
    terminal: bool,
) -> None:
    if len(dispatch.intervals) != INTERVALS:
        raise ValueError("dispatch requires 288 intervals")
    reconstructed = battery.initial_mwh
    previous_reported = battery.initial_mwh
    charge_eta = battery.efficiency.charge
    discharge_eta = battery.efficiency.discharge
    charge_cap = battery.effective_charge_mw() / 12 + ENERGY_TOLERANCE
    discharge_cap = battery.effective_discharge_mw() / 12 + ENERGY_TOLERANCE
    for i, step in enumerate(dispatch.intervals):
        c, d = step.imported_mwh, step.exported_mwh
        if (
            (windows is not None and not windows.can_charge(i) and c > ENERGY_TOLERANCE)
            or (
                windows is not None
                and not windows.can_discharge(i)
                and d > ENERGY_TOLERANCE
            )
            or c > charge_cap
            or d > discharge_cap
            or (c > ENERGY_TOLERANCE and d > ENERGY_TOLERANCE)
        ):
            raise ValueError(f"dispatch violates windows/power/exclusivity at {i}")
        reconstructed = numbers.finite(
            "reconstructed energy", reconstructed + charge_eta * c - d / discharge_eta
        )
        interval_residual = numbers.finite(
            "interval balance",
            step.ending_energy_mwh
            - previous_reported
            - charge_eta * c
            + d / discharge_eta,
        )
        if (
            abs(interval_residual) > ENERGY_TOLERANCE
            or abs(reconstructed - step.ending_energy_mwh) > ENERGY_TOLERANCE
            or reconstructed < battery.minimum_mwh - ENERGY_TOLERANCE
            or reconstructed > battery.maximum_mwh + ENERGY_TOLERANCE
            or step.ending_energy_mwh < battery.minimum_mwh - ENERGY_TOLERANCE
            or step.ending_energy_mwh > battery.maximum_mwh + ENERGY_TOLERANCE
        ):
            raise ValueError(f"energy balance/bounds violated at {i}")
        previous_reported = step.ending_energy_mwh
    if terminal and (
        abs(reconstructed - battery.initial_mwh) > ENERGY_TOLERANCE
        or abs(previous_reported - battery.initial_mwh) > ENERGY_TOLERANCE
    ):
        raise ValueError("terminal energy differs from initial energy")
