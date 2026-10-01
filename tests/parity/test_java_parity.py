"""Cross-runtime parity against the frozen Java export.

Fixtures were produced by ``:infrastructure:parityExport`` at the recorded
baseline; inputs are reconstructed from ``reference/java/.../ParityExport.java``
(the fixture stores expected outputs, not inputs). hindsight intervals may pick
a different equally-optimal vertex than ojAlgo, so the solver parity surface is
status + objective/bound/gap + independently validated dispatch + reconciled
accounting — not bitwise dispatch equality.
"""

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from nemlab_core import accounting, decimal_text, fixed, hindsight, threshold
from nemlab_core import dispatch as dispatch_module
from nemlab_core.battery import Battery, Efficiency, TradingCosts
from nemlab_core.prices import INTERVALS, Interval, PriceDay, Region
from nemlab_core.request import (
    Costs,
    EfficiencyInput,
    Invalid,
    SimulationRequest,
    Site,
    ThresholdInput,
    Windows,
)
from nemlab_core.threshold import Thresholds
from nemlab_core.windows import ScheduleWindows

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = json.loads(
    (
        ROOT / "docs/project/evidence/python-rebuild/fixtures/parity-fixtures.json"
    ).read_text()
)
PRICES_DIR = ROOT / "reference/java/core/src/test/resources/prices"
# ParityExport froze the clock at 2026-10-01T00:00:00Z → 2026-10-01 in NEM time.
FIXED_TODAY = date(2026, 10, 1)
EXAMPLE_REVISION = "00000000-0000-0000-0000-000000000000"


def _dec(value: str | None) -> Decimal | None:
    return None if value is None else decimal_text.parse(value)


def _request(
    day: str | None,
    cap: str | None,
    min_: str | None,
    max_: str | None,
    initial: str | None,
    charge_mw: str | None,
    discharge_mw: str | None,
    import_mw: str | None,
    export_mw: str | None,
    eff_charge: str | None,
    eff_discharge: str | None,
    round_trip: str | None,
    import_fee: str | None,
    export_fee: str | None,
    degradation: str | None,
    cs: int | None,
    ce: int | None,
    ds: int | None,
    de: int | None,
    charge_below: str | None,
    discharge_above: str | None,
) -> SimulationRequest:
    return SimulationRequest(
        Region.NSW1,
        None if day is None else date.fromisoformat(day),
        Site(
            _dec(cap),
            _dec(min_),
            _dec(max_),
            _dec(initial),
            _dec(charge_mw),
            _dec(discharge_mw),
            _dec(import_mw),
            _dec(export_mw),
        ),
        EfficiencyInput(_dec(eff_charge), _dec(eff_discharge), _dec(round_trip)),
        Costs(_dec(import_fee), _dec(export_fee), _dec(degradation)),
        Windows(cs, ce, ds, de),
        None
        if charge_below is None and discharge_above is None
        else ThresholdInput(_dec(charge_below), _dec(discharge_above)),
    )


def _standard(
    day: str | None, charge_below: str | None, discharge_above: str | None
) -> SimulationRequest:
    return _request(
        day,
        "2",
        "0",
        "2",
        "0",
        "1",
        "1",
        "1",
        "1",
        None,
        None,
        "0.9",
        "2",
        "2",
        "10",
        600,
        840,
        1020,
        1260,
        charge_below,
        discharge_above,
    )


REQUEST_CASES = {
    "standard": _standard("2026-09-11", None, None),
    "thresholds": _standard("2026-09-11", "-10.0", "150"),
    "threshold-extremes": _standard("2026-09-11", "-1000000", "1000000"),
    "split-legs": _request(
        "2026-09-11",
        "2",
        "0",
        "2",
        "0",
        "1",
        "1",
        "1",
        "1",
        "0.95",
        "0.94",
        None,
        "2",
        "2",
        "10",
        600,
        840,
        1020,
        1260,
        None,
        None,
    ),
    "trailing-zeros": _request(
        "2026-09-11",
        "2.000000",
        "0.0",
        "2.00",
        "0",
        "1.000",
        "1",
        "1.00",
        "1",
        None,
        None,
        "0.90",
        "2.0",
        "2.00",
        "10.000",
        600,
        840,
        1020,
        1260,
        None,
        None,
    ),
    "exponent-input": _request(
        "2026-09-11",
        "2E+0",
        "0",
        "0.2E+1",
        "0",
        "1",
        "1",
        "1",
        "1",
        None,
        None,
        "9E-1",
        "2",
        "2",
        "10",
        600,
        840,
        1020,
        1260,
        None,
        None,
    ),
    "edge-windows": _standard("2026-09-11", None, None),
    "zero-costs-partial-inventory": _request(
        "2026-09-11",
        "10",
        "1",
        "9",
        "5",
        "2",
        "2",
        "1.5",
        "0.5",
        None,
        None,
        "0.8",
        "0",
        "0",
        "0",
        0,
        60,
        1380,
        1440,
        None,
        None,
    ),
    "err-day-too-old": _standard("2021-09-30", None, None),
    "err-day-today": _standard("2026-10-01", None, None),
    "err-capacity-zero": _request(
        "2026-09-11",
        "0",
        "0",
        "0",
        "0",
        "1",
        "1",
        "1",
        "1",
        None,
        None,
        "0.9",
        "2",
        "2",
        "10",
        600,
        840,
        1020,
        1260,
        None,
        None,
    ),
    "err-bounds": _request(
        "2026-09-11",
        "2",
        "1.5",
        "2",
        "1",
        "1",
        "1",
        "1",
        "1",
        None,
        None,
        "0.9",
        "2",
        "2",
        "10",
        600,
        840,
        1020,
        1260,
        None,
        None,
    ),
    "err-negative-cost": _request(
        "2026-09-11",
        "2",
        "0",
        "2",
        "0",
        "1",
        "1",
        "1",
        "1",
        None,
        None,
        "0.9",
        "-0.01",
        "2",
        "10",
        600,
        840,
        1020,
        1260,
        None,
        None,
    ),
    "err-efficiency-zero": _request(
        "2026-09-11",
        "2",
        "0",
        "2",
        "0",
        "1",
        "1",
        "1",
        "1",
        "0",
        None,
        None,
        "2",
        "2",
        "10",
        600,
        840,
        1020,
        1260,
        None,
        None,
    ),
    "err-efficiency-above-one": _request(
        "2026-09-11",
        "2",
        "0",
        "2",
        "0",
        "1",
        "1",
        "1",
        "1",
        "1.01",
        None,
        None,
        "2",
        "2",
        "10",
        600,
        840,
        1020,
        1260,
        None,
        None,
    ),
    "err-ambiguous-efficiency": _request(
        "2026-09-11",
        "2",
        "0",
        "2",
        "0",
        "1",
        "1",
        "1",
        "1",
        "0.95",
        None,
        "0.9",
        "2",
        "2",
        "10",
        600,
        840,
        1020,
        1260,
        None,
        None,
    ),
    "err-window-unaligned": _request(
        "2026-09-11",
        "2",
        "0",
        "2",
        "0",
        "1",
        "1",
        "1",
        "1",
        None,
        None,
        "0.9",
        "2",
        "2",
        "10",
        7,
        840,
        1020,
        1260,
        None,
        None,
    ),
    "err-windows-overlap": _request(
        "2026-09-11",
        "2",
        "0",
        "2",
        "0",
        "1",
        "1",
        "1",
        "1",
        None,
        None,
        "0.9",
        "2",
        "2",
        "10",
        600,
        1100,
        1020,
        1260,
        None,
        None,
    ),
    "err-threshold-order": _standard("2026-09-11", "150", "-10"),
    "err-threshold-single": _standard("2026-09-11", "30", None),
    "err-decimal-scale": _request(
        "2026-09-11",
        "0.0000000000000000001",
        "0",
        "2",
        "0",
        "1",
        "1",
        "1",
        "1",
        None,
        None,
        "0.9",
        "2",
        "2",
        "10",
        600,
        840,
        1020,
        1260,
        None,
        None,
    ),
    "err-decimal-precision": _request(
        "2026-09-11",
        "12345678901234567890123456789012345678.9",
        "0",
        "2",
        "0",
        "1",
        "1",
        "1",
        "1",
        None,
        None,
        "0.9",
        "2",
        "2",
        "10",
        600,
        840,
        1020,
        1260,
        None,
        None,
    ),
}


@pytest.mark.parametrize("row", FIXTURES["decimalForms"], ids=lambda r: r["input"])
def test_decimal_forms(row: dict) -> None:
    if "error" in row:
        with pytest.raises(ValueError):
            decimal_text.parse(row["input"])
        return
    value = decimal_text.parse(row["input"])
    assert decimal_text.to_plain_string(value) == row["plain"]
    assert decimal_text.canonical_decimal(value) == row["canonical"]
    assert decimal_text.precision(value) == row["precision"]
    assert decimal_text.scale(value) == row["scale"]
    within = decimal_text.within_decimal_limits(value) and Decimal(
        0
    ) <= value <= Decimal(1000000)
    assert within == row["withinFieldBounds"]


@pytest.mark.parametrize("row", FIXTURES["requests"], ids=lambda r: r["name"])
def test_request_canonicalisation(row: dict) -> None:
    request = REQUEST_CASES[row["name"]]
    if "error" in row:
        with pytest.raises(Invalid) as caught:
            request.normalise(today=FIXED_TODAY)
        assert caught.value.field == row["error"]["field"]
        assert caught.value.code == row["error"]["code"]
    else:
        assert request.normalise(today=FIXED_TODAY).canonical() == row["canonical"]


def _price_day(day: str) -> PriceDay:
    lines = (PRICES_DIR / f"{day}.csv").read_text().splitlines()
    intervals = []
    for line in lines[1:]:
        end_text, price_text = line.split(",")
        end = datetime.fromisoformat(end_text)
        intervals.append(Interval.from_end(Region.NSW1, end, Decimal(price_text)))
    assert len(intervals) == INTERVALS
    return PriceDay(Region.NSW1, date.fromisoformat(day), tuple(intervals))


@pytest.mark.parametrize("case", FIXTURES["scenarioKeys"]["cases"])
def test_scenario_keys(case: dict) -> None:
    index = FIXTURES["scenarioKeys"]["cases"].index(case)
    request = [
        _standard("2026-09-11", None, None),
        _standard("2026-09-11", "-10.0", "150"),
        REQUEST_CASES["split-legs"],
    ][index]
    canonical = request.normalise(today=FIXED_TODAY).canonical()
    assert canonical == case["canonical"]
    digest = hashlib.sha256(
        (
            canonical
            + "\n"
            + EXAMPLE_REVISION
            + "\n"
            + FIXTURES["versions"]["canonical"]
        ).encode("utf-8")
    ).hexdigest()
    assert digest == case["key"]


def _battery(data: dict) -> Battery:
    return Battery(
        data["capacityMWh"],
        data["minimumMWh"],
        data["maximumMWh"],
        data["initialMWh"],
        data["chargeMW"],
        data["dischargeMW"],
        data["importLimitMW"],
        data["exportLimitMW"],
        Efficiency(data["efficiency"]["charge"], data["efficiency"]["discharge"]),
    )


def _assert_strategy(
    actual_intervals, actual_limit, actual_accounting, expected: dict
) -> None:
    assert actual_limit.name == expected["limitingReason"]
    assert len(actual_intervals) == INTERVALS
    pairs = zip(actual_intervals, expected["intervals"], strict=True)
    for i, (step, want) in enumerate(pairs):
        got = [step.imported_mwh, step.exported_mwh, step.ending_energy_mwh]
        assert got == want, f"interval {i}: {got} != {want}"
    fields = (
        "importedMWh",
        "exportedMWh",
        "chargingCost",
        "revenue",
        "fees",
        "degradation",
        "margin",
        "lossesMWh",
    )
    snake = (
        "imported_mwh",
        "exported_mwh",
        "charging_cost",
        "revenue",
        "fees",
        "degradation",
        "margin",
        "losses_mwh",
    )
    for camel, attr in zip(fields, snake, strict=True):
        assert getattr(actual_accounting, attr) == expected["accounting"][camel], attr


@pytest.mark.parametrize("run", FIXTURES["runs"], ids=lambda r: r["name"])
def test_fixed_and_threshold_runs(run: dict) -> None:
    battery = _battery(run["battery"])
    w = run["windows"]
    windows = ScheduleWindows(
        w["chargeStart"], w["chargeEnd"], w["dischargeStart"], w["dischargeEnd"]
    )
    c = run["costs"]
    costs = TradingCosts(c["importFee"], c["exportFee"], c["degradationPerExportedMWh"])
    prices = _price_day(run["day"])

    dispatch = fixed.plan(battery, windows)
    _assert_strategy(
        dispatch.intervals,
        dispatch.limiting_reason,
        accounting.calculate(battery, costs, prices, dispatch),
        run["fixed"],
    )

    if "thresholds" in run:
        t = run["thresholds"]
        thresholds = Thresholds(
            Decimal(str(t["chargeBelow"])), Decimal(str(t["dischargeAbove"]))
        )
        tdispatch = threshold.plan(battery, thresholds, prices)
        _assert_strategy(
            tdispatch.intervals,
            tdispatch.limiting_reason,
            accounting.calculate(battery, costs, prices, tdispatch),
            run["threshold"],
        )


@pytest.mark.parametrize("run", FIXTURES["runs"], ids=lambda r: r["name"])
def test_hindsight_runs(run: dict) -> None:
    """HiGHS may choose a different equally-optimal vertex than ojAlgo, so the
    parity surface is certified status, objective, bound, gap and an
    independently validated dispatch — not bitwise interval equality."""
    battery = _battery(run["battery"])
    w = run["windows"]
    windows = ScheduleWindows(
        w["chargeStart"], w["chargeEnd"], w["dischargeStart"], w["dischargeEnd"]
    )
    c = run["costs"]
    costs = TradingCosts(c["importFee"], c["exportFee"], c["degradationPerExportedMWh"])
    prices = _price_day(run["day"])
    expected = run["hindsight"]

    outcome = hindsight.solve(
        battery, windows, costs, prices, hindsight.Limits.standard()
    )

    assert expected["status"] == "OPTIMAL"  # fixture baseline
    assert outcome.status is hindsight.Status.OPTIMAL
    assert outcome.solver_state == "OPTIMAL"
    assert outcome.certificate_state == "OPTIMAL"
    assert outcome.diagnostic == expected["diagnostic"]
    assert outcome.limits.milliseconds == expected["limits"]["milliseconds"]
    assert outcome.limits.iterations == expected["limits"]["iterations"]
    assert outcome.dispatch is not None and outcome.accounting is not None
    dispatch_module.validate(battery, windows, outcome.dispatch)
    assert accounting.reconciles(
        expected["solverObjective"], outcome.solver_objective
    ), f"objective {outcome.solver_objective} != {expected['solverObjective']}"
    assert outcome.upper_bound is not None
    assert accounting.reconciles(expected["upperBound"], outcome.upper_bound)
    assert outcome.absolute_gap is not None
    assert 0 <= outcome.absolute_gap <= hindsight.GAP_TOLERANCE
    assert accounting.reconciles(expected["absoluteGap"], outcome.absolute_gap)
    assert accounting.reconciles(
        outcome.upper_bound - outcome.accounting.margin, outcome.absolute_gap
    )
    expected_accounting = expected["dispatch"]["accounting"]
    for camel, actual in (
        ("margin", outcome.accounting.margin),
        ("importedMWh", outcome.accounting.imported_mwh),
        ("exportedMWh", outcome.accounting.exported_mwh),
    ):
        assert accounting.reconciles(expected_accounting[camel], actual), camel


def test_scenario_keys_change_with_python_execution_identity() -> None:
    """Same request and price revision must hash differently once the solver
    identity moves off ojAlgo — proven by recomputing the fixture key."""
    case = FIXTURES["scenarioKeys"]["cases"][0]
    python_versions = "\n".join(
        (
            "simulation-request-v1",
            fixed.MODEL_VERSION,
            fixed.FIXED_VERSION,
            hindsight.VERSION,
            hindsight.SOLVER,
            "ordered-comparison-v1",
            "5000",
            "100000",
        )
    )
    python_key = hashlib.sha256(
        (case["canonical"] + "\n" + EXAMPLE_REVISION + "\n" + python_versions).encode(
            "utf-8"
        )
    ).hexdigest()
    assert python_key != case["key"]
    other = hashlib.sha256(
        (
            case["canonical"]
            + "\n"
            + EXAMPLE_REVISION
            + "\n"
            + python_versions.replace(hindsight.SOLVER, "HiGHS 0.0.0")
        ).encode("utf-8")
    ).hexdigest()
    assert other != python_key
