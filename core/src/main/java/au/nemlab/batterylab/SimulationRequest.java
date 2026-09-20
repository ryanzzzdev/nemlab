package au.nemlab.batterylab;

import java.math.BigDecimal;
import java.time.Clock;
import java.time.LocalDate;
import java.util.List;

/** Exact request values; normalisation is independent of HTTP, storage and execution. */
public record SimulationRequest(PriceDay.Region region, LocalDate day, Site site,
        EfficiencyInput efficiency, Costs costs, Windows windows) {
    public record Site(BigDecimal capacityMWh, BigDecimal minimumMWh, BigDecimal maximumMWh,
            BigDecimal initialMWh, BigDecimal chargeMW, BigDecimal dischargeMW,
            BigDecimal importLimitMW, BigDecimal exportLimitMW) {
    }

    public record EfficiencyInput(BigDecimal charge, BigDecimal discharge, BigDecimal roundTrip) {
    }

    public record Costs(BigDecimal importFee, BigDecimal exportFee, BigDecimal degradationPerExportedMWh) {
    }

    public record Windows(Integer chargeStart, Integer chargeEnd, Integer dischargeStart, Integer dischargeEnd) {
    }

    public static final class Invalid extends IllegalArgumentException {
        private final String field;
        private final String code;

        public Invalid(String field, String code) {
            super(field + ": " + code);
            this.field = field;
            this.code = code;
        }

        public String field() { return field; }
        public String code() { return code; }
    }

    /** Constructed only by normalise; decimal provenance and executable values stay together. */
    public static final class Normalised {
        private final SimulationRequest values;
        private final Battery battery;
        private final TradingCosts costs;
        private final ScheduleWindows windows;

        private Normalised(SimulationRequest values) {
            this.values = values;
            Site s = values.site();
            battery = new Battery(s.capacityMWh().doubleValue(), s.minimumMWh().doubleValue(),
                    s.maximumMWh().doubleValue(), s.initialMWh().doubleValue(), s.chargeMW().doubleValue(),
                    s.dischargeMW().doubleValue(), s.importLimitMW().doubleValue(), s.exportLimitMW().doubleValue(),
                    new Efficiency(values.efficiency().charge().doubleValue(), values.efficiency().discharge().doubleValue()));
            costs = new TradingCosts(values.costs().importFee().doubleValue(), values.costs().exportFee().doubleValue(),
                    values.costs().degradationPerExportedMWh().doubleValue());
            Windows w = values.windows();
            windows = ScheduleWindows.minutes(w.chargeStart(), w.chargeEnd(), w.dischargeStart(), w.dischargeEnd());
        }

        public SimulationRequest values() { return values; }
        public Battery battery() { return battery; }
        public TradingCosts costs() { return costs; }
        public ScheduleWindows windows() { return windows; }

        /** Fixed order is part of request-v1; all values exclude newline characters. */
        public String canonical() {
            Site s = values.site();
            var decimals = List.of(s.capacityMWh(), s.minimumMWh(), s.maximumMWh(), s.initialMWh(),
                    s.chargeMW(), s.dischargeMW(), s.importLimitMW(), s.exportLimitMW(),
                    values.efficiency().charge(), values.efficiency().discharge(),
                    values.costs().importFee(), values.costs().exportFee(), values.costs().degradationPerExportedMWh());
            StringBuilder text = new StringBuilder("simulation-request-v1\n")
                    .append(values.region()).append('\n').append(values.day());
            for (BigDecimal value : decimals) text.append('\n').append(value.toPlainString());
            Windows w = values.windows();
            for (int minute : new int[] { w.chargeStart(), w.chargeEnd(), w.dischargeStart(), w.dischargeEnd() })
                text.append('\n').append(minute);
            return text.toString();
        }
    }

    public Normalised normalise(Clock clock) {
        required("region", region);
        required("day", day);
        if (day.isBefore(LocalDate.of(2021, 10, 1)) || !day.isBefore(LocalDate.now(clock.withZone(PriceDay.NEM_OFFSET))))
            throw new Invalid("day", "OUT_OF_RANGE");
        required("site", site);
        required("efficiency", efficiency);
        required("costs", costs);
        required("windows", windows);
        Site s = new Site(quantity("site.capacityMWh", site.capacityMWh()),
                quantity("site.minimumMWh", site.minimumMWh()), quantity("site.maximumMWh", site.maximumMWh()),
                quantity("site.initialMWh", site.initialMWh()), quantity("site.chargeMW", site.chargeMW()),
                quantity("site.dischargeMW", site.dischargeMW()), quantity("site.importLimitMW", site.importLimitMW()),
                quantity("site.exportLimitMW", site.exportLimitMW()));
        if (s.capacityMWh().signum() == 0) throw new Invalid("site.capacityMWh", "OUT_OF_RANGE");
        if (s.minimumMWh().compareTo(s.initialMWh()) > 0 || s.initialMWh().compareTo(s.maximumMWh()) > 0
                || s.maximumMWh().compareTo(s.capacityMWh()) > 0)
            throw new Invalid("site", "INVALID_BOUNDS");
        EfficiencyInput legs;
        if (efficiency.roundTrip() != null) {
            if (efficiency.charge() != null || efficiency.discharge() != null)
                throw new Invalid("efficiency", "AMBIGUOUS_EFFICIENCY");
            BigDecimal roundTrip = decimal("efficiency.roundTrip", efficiency.roundTrip(), "0.0001", "1");
            double leg = Efficiency.roundTrip(roundTrip.doubleValue()).charge();
            BigDecimal value = BigDecimal.valueOf(leg).stripTrailingZeros();
            legs = new EfficiencyInput(value, value, null);
        } else {
            legs = new EfficiencyInput(decimal("efficiency.charge", efficiency.charge(), "0.01", "1"),
                    decimal("efficiency.discharge", efficiency.discharge(), "0.01", "1"), null);
        }
        Costs c = new Costs(quantity("costs.importFee", costs.importFee()),
                quantity("costs.exportFee", costs.exportFee()),
                quantity("costs.degradationPerExportedMWh", costs.degradationPerExportedMWh()));
        minute("windows.chargeStart", windows.chargeStart());
        minute("windows.chargeEnd", windows.chargeEnd());
        minute("windows.dischargeStart", windows.dischargeStart());
        minute("windows.dischargeEnd", windows.dischargeEnd());
        try {
            ScheduleWindows.minutes(windows.chargeStart(), windows.chargeEnd(), windows.dischargeStart(), windows.dischargeEnd());
        } catch (IllegalArgumentException e) {
            throw new Invalid("windows", "INVALID_WINDOWS");
        }
        return new Normalised(new SimulationRequest(region, day, s, legs, c, windows));
    }

    private static void required(String field, Object value) {
        if (value == null) throw new Invalid(field, "REQUIRED");
    }

    private static void minute(String field, Integer value) {
        required(field, value);
        if (value < 0 || value > 1440 || value % 5 != 0) throw new Invalid(field, "INVALID_WINDOWS");
    }

    private static BigDecimal quantity(String field, BigDecimal value) {
        return decimal(field, value, "0", "1000000");
    }

    private static BigDecimal decimal(String field, BigDecimal value, String minimum, String maximum) {
        required(field, value);
        if (value.precision() > 38 || Math.abs((long) value.scale()) > 18)
            throw new Invalid(field, "DECIMAL_LIMIT");
        if (value.compareTo(new BigDecimal(minimum)) < 0 || value.compareTo(new BigDecimal(maximum)) > 0)
            throw new Invalid(field, "OUT_OF_RANGE");
        return value.stripTrailingZeros();
    }
}
