"""Exact request values and normalisation — ports Java ``SimulationRequest``.

Normalisation is independent of HTTP, storage and execution. Field validation
order and ``Invalid(field, code)`` pairs match the Java implementation so the
first reported error is identical.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from nemlab_core.battery import Battery, Efficiency, TradingCosts
from nemlab_core.decimal_text import (
    strip_trailing_zeros,
    to_plain_string,
    within_decimal_limits,
)
from nemlab_core.prices import NEM_OFFSET, Region
from nemlab_core.threshold import THRESHOLD_VERSION, Thresholds
from nemlab_core.windows import ScheduleWindows

REQUEST_VERSION = "simulation-request-v1"
EARLIEST_DAY = date(2021, 10, 1)


class Invalid(ValueError):
    """First validation failure, carrying the contract's field/code pair."""

    def __init__(self, field: str, code: str) -> None:
        super().__init__(f"{field}: {code}")
        self.field = field
        self.code = code


@dataclass(frozen=True)
class Site:
    capacity_mwh: Decimal | None
    minimum_mwh: Decimal | None
    maximum_mwh: Decimal | None
    initial_mwh: Decimal | None
    charge_mw: Decimal | None
    discharge_mw: Decimal | None
    import_limit_mw: Decimal | None
    export_limit_mw: Decimal | None


@dataclass(frozen=True)
class EfficiencyInput:
    charge: Decimal | None
    discharge: Decimal | None
    round_trip: Decimal | None


@dataclass(frozen=True)
class Costs:
    import_fee: Decimal | None
    export_fee: Decimal | None
    degradation_per_exported_mwh: Decimal | None


@dataclass(frozen=True)
class Windows:
    charge_start: int | None
    charge_end: int | None
    discharge_start: int | None
    discharge_end: int | None


@dataclass(frozen=True)
class ThresholdInput:
    """Raw optional threshold experiment input; both parts required together
    after normalisation."""

    charge_below: Decimal | None
    discharge_above: Decimal | None


@dataclass(frozen=True)
class SimulationRequest:
    region: Region | None
    day: date | None
    site: Site | None
    efficiency: EfficiencyInput | None
    costs: Costs | None
    windows: Windows | None
    thresholds: ThresholdInput | None = None

    def normalise(self, today: date | None = None) -> "Normalised":
        if today is None:
            today = datetime.now(NEM_OFFSET).date()
        _required("region", self.region)
        _required("day", self.day)
        assert self.day is not None
        if self.day < EARLIEST_DAY or self.day >= today:
            raise Invalid("day", "OUT_OF_RANGE")
        _required("site", self.site)
        _required("efficiency", self.efficiency)
        _required("costs", self.costs)
        _required("windows", self.windows)
        assert self.site is not None and self.efficiency is not None
        assert self.costs is not None and self.windows is not None
        s = Site(
            _quantity("site.capacityMWh", self.site.capacity_mwh),
            _quantity("site.minimumMWh", self.site.minimum_mwh),
            _quantity("site.maximumMWh", self.site.maximum_mwh),
            _quantity("site.initialMWh", self.site.initial_mwh),
            _quantity("site.chargeMW", self.site.charge_mw),
            _quantity("site.dischargeMW", self.site.discharge_mw),
            _quantity("site.importLimitMW", self.site.import_limit_mw),
            _quantity("site.exportLimitMW", self.site.export_limit_mw),
        )
        assert s.capacity_mwh is not None
        if s.capacity_mwh == 0:
            raise Invalid("site.capacityMWh", "OUT_OF_RANGE")
        if (
            _d(s.minimum_mwh) > _d(s.initial_mwh)
            or _d(s.initial_mwh) > _d(s.maximum_mwh)
            or _d(s.maximum_mwh) > s.capacity_mwh
        ):
            raise Invalid("site", "INVALID_BOUNDS")
        if self.efficiency.round_trip is not None:
            if (
                self.efficiency.charge is not None
                or self.efficiency.discharge is not None
            ):
                raise Invalid("efficiency", "AMBIGUOUS_EFFICIENCY")
            round_trip = _decimal(
                "efficiency.roundTrip", self.efficiency.round_trip, "0.0001", "1"
            )
            leg = Efficiency.round_trip(float(round_trip)).charge
            value = strip_trailing_zeros(Decimal(repr(leg)))
            legs = EfficiencyInput(value, value, None)
        else:
            legs = EfficiencyInput(
                _decimal("efficiency.charge", self.efficiency.charge, "0.01", "1"),
                _decimal(
                    "efficiency.discharge", self.efficiency.discharge, "0.01", "1"
                ),
                None,
            )
        c = Costs(
            _quantity("costs.importFee", self.costs.import_fee),
            _quantity("costs.exportFee", self.costs.export_fee),
            _quantity(
                "costs.degradationPerExportedMWh",
                self.costs.degradation_per_exported_mwh,
            ),
        )
        w = self.windows
        _minute("windows.chargeStart", w.charge_start)
        _minute("windows.chargeEnd", w.charge_end)
        _minute("windows.dischargeStart", w.discharge_start)
        _minute("windows.dischargeEnd", w.discharge_end)
        try:
            ScheduleWindows.minutes(
                _i(w.charge_start),
                _i(w.charge_end),
                _i(w.discharge_start),
                _i(w.discharge_end),
            )
        except ValueError:
            raise Invalid("windows", "INVALID_WINDOWS") from None
        t = None
        if self.thresholds is not None:
            charge_below = _decimal(
                "thresholds.chargeBelow",
                self.thresholds.charge_below,
                "-1000000",
                "1000000",
            )
            discharge_above = _decimal(
                "thresholds.dischargeAbove",
                self.thresholds.discharge_above,
                "-1000000",
                "1000000",
            )
            try:
                Thresholds(charge_below, discharge_above)
            except ValueError:
                raise Invalid("thresholds", "INVALID_ORDER") from None
            t = ThresholdInput(charge_below, discharge_above)
        return Normalised(SimulationRequest(self.region, self.day, s, legs, c, w, t))


def _d(value: Decimal | None) -> Decimal:
    """Normalise-internal narrowing: fields are non-None after validation."""
    assert value is not None
    return value


def _f(value: Decimal | None) -> float:
    return float(_d(value))


def _i(value: int | None) -> int:
    assert value is not None
    return value


class Normalised:
    """Constructed only by ``normalise``; decimal provenance and executable
    values stay together."""

    def __init__(self, values: SimulationRequest) -> None:
        self.values = values
        s, e, c, w = values.site, values.efficiency, values.costs, values.windows
        assert s is not None and e is not None and c is not None and w is not None
        self.battery = Battery(
            _f(s.capacity_mwh),
            _f(s.minimum_mwh),
            _f(s.maximum_mwh),
            _f(s.initial_mwh),
            _f(s.charge_mw),
            _f(s.discharge_mw),
            _f(s.import_limit_mw),
            _f(s.export_limit_mw),
            Efficiency(_f(e.charge), _f(e.discharge)),
        )
        self.costs = TradingCosts(
            _f(c.import_fee), _f(c.export_fee), _f(c.degradation_per_exported_mwh)
        )
        self.windows = ScheduleWindows.minutes(
            _i(w.charge_start),
            _i(w.charge_end),
            _i(w.discharge_start),
            _i(w.discharge_end),
        )
        t = values.thresholds
        self.thresholds = (
            None if t is None else Thresholds(_d(t.charge_below), _d(t.discharge_above))
        )

    def canonical(self) -> str:
        """Fixed order is part of request-v1; all values exclude newlines."""
        v = self.values
        s, e, c, w = v.site, v.efficiency, v.costs, v.windows
        assert s is not None and e is not None and c is not None and w is not None
        decimals = (
            s.capacity_mwh,
            s.minimum_mwh,
            s.maximum_mwh,
            s.initial_mwh,
            s.charge_mw,
            s.discharge_mw,
            s.import_limit_mw,
            s.export_limit_mw,
            e.charge,
            e.discharge,
            c.import_fee,
            c.export_fee,
            c.degradation_per_exported_mwh,
        )
        parts = [
            REQUEST_VERSION,
            _d_region(v.region),
            _d_day(v.day),
        ]
        parts.extend(to_plain_string(_d(x)) for x in decimals)
        parts.extend(
            str(_i(m))
            for m in (w.charge_start, w.charge_end, w.discharge_start, w.discharge_end)
        )
        if self.thresholds is not None:
            parts.extend(
                (
                    THRESHOLD_VERSION,
                    to_plain_string(self.thresholds.charge_below),
                    to_plain_string(self.thresholds.discharge_above),
                )
            )
        return "\n".join(parts)


def _d_region(region: Region | None) -> str:
    assert region is not None
    return region.name


def _d_day(day: date | None) -> str:
    assert day is not None
    return day.isoformat()


def _required(field: str, value: object) -> None:
    if value is None:
        raise Invalid(field, "REQUIRED")


def _minute(field: str, value: int | None) -> None:
    _required(field, value)
    if isinstance(value, bool) or not isinstance(value, int):
        raise Invalid(field, "INVALID_WINDOWS")
    if value < 0 or value > 1440 or value % 5 != 0:
        raise Invalid(field, "INVALID_WINDOWS")


def _quantity(field: str, value: Decimal | None) -> Decimal:
    return _decimal(field, value, "0", "1000000")


def _decimal(field: str, value: Decimal | None, minimum: str, maximum: str) -> Decimal:
    _required(field, value)
    assert value is not None
    if not within_decimal_limits(value):
        raise Invalid(field, "DECIMAL_LIMIT")
    if value < Decimal(minimum) or value > Decimal(maximum):
        raise Invalid(field, "OUT_OF_RANGE")
    return strip_trailing_zeros(value)
