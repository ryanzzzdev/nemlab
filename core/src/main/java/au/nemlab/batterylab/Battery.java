package au.nemlab.batterylab;

import java.util.Objects;

/** Aggregate site values in MW and MWh; connection limits apply after aggregation. */
public record Battery(double capacityMWh, double minimumMWh, double maximumMWh,
                      double initialMWh, double chargeMW, double dischargeMW,
                      double importLimitMW, double exportLimitMW, Efficiency efficiency) {
    public Battery {
        Numbers.nonnegative("capacity", capacityMWh);
        Numbers.nonnegative("minimum energy", minimumMWh);
        Numbers.nonnegative("maximum energy", maximumMWh);
        Numbers.nonnegative("initial energy", initialMWh);
        if (capacityMWh == 0 || minimumMWh > initialMWh || initialMWh > maximumMWh
                || maximumMWh > capacityMWh) throw new IllegalArgumentException("invalid energy bounds");
        Numbers.nonnegative("charge power", chargeMW);
        Numbers.nonnegative("discharge power", dischargeMW);
        Numbers.nonnegative("import limit", importLimitMW);
        Numbers.nonnegative("export limit", exportLimitMW);
        Objects.requireNonNull(efficiency, "efficiency");
    }
    public double effectiveChargeMW() { return Math.min(chargeMW, importLimitMW); }
    public double effectiveDischargeMW() { return Math.min(dischargeMW, exportLimitMW); }
}
