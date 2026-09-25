package au.nemlab.batterylab;

import java.math.BigDecimal;
import java.util.Objects;

/** Fixed visitor thresholds in AUD/MWh; charge threshold must be below discharge. */
public record Thresholds(BigDecimal chargeBelow, BigDecimal dischargeAbove) {
    public Thresholds {
        Objects.requireNonNull(chargeBelow, "chargeBelow");
        Objects.requireNonNull(dischargeAbove, "dischargeAbove");
        Numbers.finite("charge threshold", chargeBelow.doubleValue());
        Numbers.finite("discharge threshold", dischargeAbove.doubleValue());
        if (chargeBelow.compareTo(dischargeAbove) >= 0)
            throw new IllegalArgumentException("charge threshold must be below discharge threshold");
    }
}
