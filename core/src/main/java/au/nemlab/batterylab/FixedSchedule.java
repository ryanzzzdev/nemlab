package au.nemlab.batterylab;

import java.util.ArrayList;
import java.util.Objects;

/** Price-independent policy: neither prices nor costs appear in this interface. */
public final class FixedSchedule {
    public static final String VERSION = "ordered-windows-v1";
    public Dispatch plan(Battery battery, ScheduleWindows windows) {
        Objects.requireNonNull(battery, "battery");
        Objects.requireNonNull(windows, "windows");
        double etaC = battery.efficiency().charge();
        double etaD = battery.efficiency().discharge();
        double chargeLimit = battery.effectiveChargeMW() / 12;
        double dischargeLimit = battery.effectiveDischargeMW() / 12;
        double headroom = battery.maximumMWh() - battery.initialMWh();
        double availableCharge = Numbers.finite("charge window energy",
                chargeLimit * etaC * (windows.chargeEnd() - windows.chargeStart()));
        double availableDischarge = Numbers.finite("discharge window energy",
                dischargeLimit / etaD * (windows.dischargeEnd() - windows.dischargeStart()));
        double excursion = Math.min(headroom, Math.min(availableCharge, availableDischarge));
        Dispatch.Limit limit = excursion == headroom ? Dispatch.Limit.ENERGY_HEADROOM
                : excursion == availableCharge ? Dispatch.Limit.CHARGE_WINDOW : Dispatch.Limit.DISCHARGE_WINDOW;
        double remainingCharge = Numbers.finite("total import", excursion / etaC);
        double remainingDischarge = Numbers.finite("total export", excursion * etaD);
        double energy = battery.initialMWh();
        var intervals = new ArrayList<Dispatch.Interval>(PriceDay.INTERVALS);
        for (int i = 0; i < PriceDay.INTERVALS; i++) {
            double charge = windows.canCharge(i) ? Math.min(chargeLimit, remainingCharge) : 0;
            double discharge = windows.canDischarge(i) ? Math.min(dischargeLimit, remainingDischarge) : 0;
            remainingCharge -= charge;
            remainingDischarge -= discharge;
            energy += etaC * charge - discharge / etaD;
            intervals.add(new Dispatch.Interval(charge, discharge, energy));
        }
        Dispatch result = new Dispatch(intervals, limit);
        DispatchValidator.validate(battery, windows, result);
        return result;
    }
}
