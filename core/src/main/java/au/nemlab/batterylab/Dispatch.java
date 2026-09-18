package au.nemlab.batterylab;

import java.util.List;

/** Immutable unrounded interval dispatch and stored energy. */
public record Dispatch(List<Interval> intervals, Limit limitingReason) {
    public enum Limit {
        ENERGY_HEADROOM, CHARGE_WINDOW, DISCHARGE_WINDOW, NOT_EVALUATED
    }

    public record Interval(double importedMWh, double exportedMWh, double endingEnergyMWh) {
        public Interval {
            Numbers.nonnegative("imported energy", importedMWh);
            Numbers.nonnegative("exported energy", exportedMWh);
            Numbers.finite("ending energy", endingEnergyMWh);
        }
    }

    public Dispatch {
        intervals = List.copyOf(intervals);
        java.util.Objects.requireNonNull(limitingReason, "limiting reason");
    }
}
