package au.nemlab.batterylab;

/**
 * Independent reconstruction for the fixed policy, solver results and the
 * unrestricted all-day threshold strategy.
 */
public final class DispatchValidator {
    public static final double ENERGY_TOLERANCE = 1e-7;

    private DispatchValidator() {
    }

    public static void validate(Battery battery, ScheduleWindows windows, Dispatch dispatch) {
        check(battery, windows, dispatch, true);
    }

    /** All-day dispatch with no schedule windows and no forced terminal energy. */
    public static void validateUnrestricted(Battery battery, Dispatch dispatch) {
        check(battery, null, dispatch, false);
    }

    private static void check(Battery battery, ScheduleWindows windows, Dispatch dispatch, boolean terminal) {
        if (dispatch.intervals().size() != PriceDay.INTERVALS)
            throw new IllegalArgumentException("dispatch requires 288 intervals");
        double reconstructed = battery.initialMWh();
        double previousReported = battery.initialMWh();
        for (int i = 0; i < PriceDay.INTERVALS; i++) {
            var step = dispatch.intervals().get(i);
            double c = step.importedMWh(), d = step.exportedMWh();
            if ((windows != null && !windows.canCharge(i) && c > ENERGY_TOLERANCE)
                    || (windows != null && !windows.canDischarge(i) && d > ENERGY_TOLERANCE)
                    || c > battery.effectiveChargeMW() / 12 + ENERGY_TOLERANCE
                    || d > battery.effectiveDischargeMW() / 12 + ENERGY_TOLERANCE
                    || (c > ENERGY_TOLERANCE && d > ENERGY_TOLERANCE))
                throw new IllegalArgumentException("dispatch violates windows/power/exclusivity at " + i);
            reconstructed = Numbers.finite("reconstructed energy", reconstructed
                    + battery.efficiency().charge() * c - d / battery.efficiency().discharge());
            double intervalResidual = Numbers.finite("interval balance", step.endingEnergyMWh()
                    - previousReported - battery.efficiency().charge() * c + d / battery.efficiency().discharge());
            if (Math.abs(intervalResidual) > ENERGY_TOLERANCE
                    || Math.abs(reconstructed - step.endingEnergyMWh()) > ENERGY_TOLERANCE
                    || reconstructed < battery.minimumMWh() - ENERGY_TOLERANCE
                    || reconstructed > battery.maximumMWh() + ENERGY_TOLERANCE
                    || step.endingEnergyMWh() < battery.minimumMWh() - ENERGY_TOLERANCE
                    || step.endingEnergyMWh() > battery.maximumMWh() + ENERGY_TOLERANCE)
                throw new IllegalArgumentException("energy balance/bounds violated at " + i);
            previousReported = step.endingEnergyMWh();
        }
        if (terminal && (Math.abs(reconstructed - battery.initialMWh()) > ENERGY_TOLERANCE
                || Math.abs(previousReported - battery.initialMWh()) > ENERGY_TOLERANCE))
            throw new IllegalArgumentException("terminal energy differs from initial energy");
    }
}
