package au.nemlab.batterylab;

import java.util.ArrayList;
import java.util.Objects;

/**
 * Idealised same-interval price rule: charge below the charge threshold,
 * discharge above the discharge threshold, otherwise hold. Runs the whole day
 * independently of the schedule windows and never forces a terminal trade.
 */
public final class PriceThreshold {
    public static final String VERSION = "price-threshold-v1";

    public Dispatch plan(Battery battery, Thresholds thresholds, PriceDay prices) {
        Objects.requireNonNull(battery, "battery");
        Objects.requireNonNull(thresholds, "thresholds");
        Objects.requireNonNull(prices, "prices");
        double etaC = battery.efficiency().charge(), etaD = battery.efficiency().discharge();
        double chargeLimit = battery.effectiveChargeMW() / 12;
        double dischargeLimit = battery.effectiveDischargeMW() / 12;
        double energy = battery.initialMWh();
        var intervals = new ArrayList<Dispatch.Interval>(PriceDay.INTERVALS);
        for (int i = 0; i < PriceDay.INTERVALS; i++) {
            var price = prices.intervals().get(i).price();
            double charge = 0, discharge = 0;
            if (price.compareTo(thresholds.chargeBelow()) < 0)
                charge = Math.min(chargeLimit, Math.max(0, (battery.maximumMWh() - energy) / etaC));
            else if (price.compareTo(thresholds.dischargeAbove()) > 0)
                discharge = Math.min(dischargeLimit, Math.max(0, (energy - battery.minimumMWh()) * etaD));
            energy += etaC * charge - discharge / etaD;
            intervals.add(new Dispatch.Interval(charge, discharge, energy));
        }
        Dispatch result = new Dispatch(intervals, Dispatch.Limit.NOT_EVALUATED);
        DispatchValidator.validateUnrestricted(battery, result);
        return result;
    }
}
