package au.nemlab.infrastructure.parity;

import au.nemlab.batterylab.*;
import au.nemlab.infrastructure.batterylab.ScenarioPreparation;
import au.nemlab.infrastructure.prices.PriceBatch;
import tools.jackson.databind.json.JsonMapper;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.*;
import java.util.*;

/**
 * Freezes Java runtime behaviour as machine-readable parity fixtures for the
 * Python rebuild. Not a unit test: run via `./gradlew :infrastructure:parityExport`.
 * Output is deterministic except where marked; elapsedNanos is never emitted.
 */
public final class ParityExport {
    private static final Clock CLOCK = Clock.fixed(Instant.parse("2026-10-01T00:00:00Z"), ZoneOffset.UTC);
    private static final String EXAMPLE_REVISION = "00000000-0000-0000-0000-000000000000";

    public static void main(String[] args) throws Exception {
        Path output = Path.of(args[0]);
        Path pricesDir = Path.of(args[1]);
        var out = new LinkedHashMap<String, Object>();
        var versions = ScenarioPreparation.Versions.current();
        out.put("provenance", Map.of(
                "runtime", System.getProperty("java.version"),
                "solver", OrderedHindsight.SOLVER,
                "model", BatterySimulation.MODEL_VERSION,
                "command", "JAVA_HOME=<jdk25> ./gradlew :infrastructure:parityExport --offline"));
        out.put("versions", Map.of("request", versions.request(), "model", versions.model(),
                "fixed", versions.fixed(), "hindsight", versions.hindsight(), "solver", versions.solver(),
                "executionProfile", versions.executionProfile(),
                "limitsMillis", versions.limits().milliseconds(), "limitsIterations", versions.limits().iterations(),
                "canonical", versions.canonical()));
        out.put("sha256Anchor", PriceBatch.hash("nemlab"));
        out.put("decimalForms", decimalForms());
        out.put("requests", requests());
        var days = List.of(priceDay(pricesDir, "2026-09-11"), priceDay(pricesDir, "2023-09-11"));
        out.put("priceDays", days.stream().map(DayFixture::summary).toList());
        out.put("scenarioKeys", scenarioKeys());
        out.put("runs", runs(days));
        out.put("savedResults", savedResults(days.get(0)));
        Files.createDirectories(output.toAbsolutePath().getParent());
        new JsonMapper().writerWithDefaultPrettyPrinter().writeValue(output.toFile(), out);
    }

    /** Raw BigDecimal parse/strip/plain behaviour plus acceptance under quantity() bounds. */
    private static List<Map<String, Object>> decimalForms() {
        var rows = new ArrayList<Map<String, Object>>();
        for (String input : new String[] { "0", "0.0", "-0.00", "1E+2", "1e-3", "100.000", "0.10", "-0.5",
                ".5", "5.", "1234567890.123456789", "0.000000000000000001", "0.0000000000000000001",
                "12345678901234567890123456789012345678", "123456789012345678901234567890123456789",
                "9007199254740993.5", "NaN", "Infinity", "1,000.5", " 1.5", "" }) {
            var row = new LinkedHashMap<String, Object>();
            row.put("input", input);
            try {
                BigDecimal parsed = new BigDecimal(input);
                row.put("plain", parsed.toPlainString());
                row.put("canonical", parsed.stripTrailingZeros().toPlainString());
                row.put("precision", parsed.precision());
                row.put("scale", parsed.scale());
                row.put("withinFieldBounds", parsed.precision() <= 38 && Math.abs((long) parsed.scale()) <= 18
                        && parsed.compareTo(new BigDecimal("0")) >= 0
                        && parsed.compareTo(new BigDecimal("1000000")) <= 0);
            } catch (RuntimeException e) {
                row.put("error", e.getClass().getSimpleName());
            }
            rows.add(row);
        }
        return rows;
    }

    private static SimulationRequest request(String day, String cap, String min, String max, String initial,
            String chargeMW, String dischargeMW, String importMW, String exportMW,
            String effCharge, String effDischarge, String roundTrip,
            String importFee, String exportFee, String degradation,
            Integer cs, Integer ce, Integer ds, Integer de, String chargeBelow, String dischargeAbove) {
        return new SimulationRequest(PriceDay.Region.NSW1, day == null ? null : LocalDate.parse(day),
                new SimulationRequest.Site(dec(cap), dec(min), dec(max), dec(initial), dec(chargeMW),
                        dec(dischargeMW), dec(importMW), dec(exportMW)),
                new SimulationRequest.EfficiencyInput(dec(effCharge), dec(effDischarge), dec(roundTrip)),
                new SimulationRequest.Costs(dec(importFee), dec(exportFee), dec(degradation)),
                new SimulationRequest.Windows(cs, ce, ds, de),
                chargeBelow == null && dischargeAbove == null ? null
                        : new SimulationRequest.ThresholdInput(dec(chargeBelow), dec(dischargeAbove)));
    }

    private static BigDecimal dec(String value) {
        return value == null ? null : new BigDecimal(value);
    }

    private static SimulationRequest standard(String day, String chargeBelow, String dischargeAbove) {
        return request(day, "2", "0", "2", "0", "1", "1", "1", "1", null, null, "0.9",
                "2", "2", "10", 600, 840, 1020, 1260, chargeBelow, dischargeAbove);
    }

    private static List<Map<String, Object>> requests() {
        var cases = new LinkedHashMap<String, SimulationRequest>();
        cases.put("standard", standard("2026-09-11", null, null));
        cases.put("thresholds", standard("2026-09-11", "-10.0", "150"));
        cases.put("threshold-extremes", standard("2026-09-11", "-1000000", "1000000"));
        cases.put("split-legs", request("2026-09-11", "2", "0", "2", "0", "1", "1", "1", "1",
                "0.95", "0.94", null, "2", "2", "10", 600, 840, 1020, 1260, null, null));
        cases.put("trailing-zeros", request("2026-09-11", "2.000000", "0.0", "2.00", "0", "1.000", "1", "1.00", "1",
                null, null, "0.90", "2.0", "2.00", "10.000", 600, 840, 1020, 1260, null, null));
        cases.put("exponent-input", request("2026-09-11", "2E+0", "0", "0.2E+1", "0", "1", "1", "1", "1",
                null, null, "9E-1", "2", "2", "10", 600, 840, 1020, 1260, null, null));
        cases.put("edge-windows", standard("2026-09-11", null, null));
        cases.put("zero-costs-partial-inventory", request("2026-09-11", "10", "1", "9", "5", "2", "2", "1.5", "0.5",
                null, null, "0.8", "0", "0", "0", 0, 60, 1380, 1440, null, null));
        // Error cases
        cases.put("err-day-too-old", standard("2021-09-30", null, null));
        cases.put("err-day-today", standard("2026-10-01", null, null));
        cases.put("err-capacity-zero", request("2026-09-11", "0", "0", "0", "0", "1", "1", "1", "1",
                null, null, "0.9", "2", "2", "10", 600, 840, 1020, 1260, null, null));
        cases.put("err-bounds", request("2026-09-11", "2", "1.5", "2", "1", "1", "1", "1", "1",
                null, null, "0.9", "2", "2", "10", 600, 840, 1020, 1260, null, null));
        cases.put("err-negative-cost", request("2026-09-11", "2", "0", "2", "0", "1", "1", "1", "1",
                null, null, "0.9", "-0.01", "2", "10", 600, 840, 1020, 1260, null, null));
        cases.put("err-efficiency-zero", request("2026-09-11", "2", "0", "2", "0", "1", "1", "1", "1",
                "0", null, null, "2", "2", "10", 600, 840, 1020, 1260, null, null));
        cases.put("err-efficiency-above-one", request("2026-09-11", "2", "0", "2", "0", "1", "1", "1", "1",
                "1.01", null, null, "2", "2", "10", 600, 840, 1020, 1260, null, null));
        cases.put("err-ambiguous-efficiency", request("2026-09-11", "2", "0", "2", "0", "1", "1", "1", "1",
                "0.95", null, "0.9", "2", "2", "10", 600, 840, 1020, 1260, null, null));
        cases.put("err-window-unaligned", request("2026-09-11", "2", "0", "2", "0", "1", "1", "1", "1",
                null, null, "0.9", "2", "2", "10", 7, 840, 1020, 1260, null, null));
        cases.put("err-windows-overlap", request("2026-09-11", "2", "0", "2", "0", "1", "1", "1", "1",
                null, null, "0.9", "2", "2", "10", 600, 1100, 1020, 1260, null, null));
        cases.put("err-threshold-order", standard("2026-09-11", "150", "-10"));
        cases.put("err-threshold-single", standard("2026-09-11", "30", null));
        cases.put("err-decimal-scale", request("2026-09-11", "0.0000000000000000001", "0", "2", "0", "1", "1", "1", "1",
                null, null, "0.9", "2", "2", "10", 600, 840, 1020, 1260, null, null));
        cases.put("err-decimal-precision", request("2026-09-11", "12345678901234567890123456789012345678.9", "0", "2", "0", "1", "1", "1", "1",
                null, null, "0.9", "2", "2", "10", 600, 840, 1020, 1260, null, null));
        var rows = new ArrayList<Map<String, Object>>();
        cases.forEach((name, req) -> {
            var row = new LinkedHashMap<String, Object>();
            row.put("name", name);
            try {
                var normalised = req.normalise(CLOCK);
                row.put("canonical", normalised.canonical());
            } catch (SimulationRequest.Invalid e) {
                row.put("error", Map.of("field", e.field(), "code", e.code()));
            }
            rows.add(row);
        });
        return rows;
    }

    private static Map<String, Object> scenarioKeys() {
        var rows = new ArrayList<Map<String, Object>>();
        for (var req : List.of(standard("2026-09-11", null, null), standard("2026-09-11", "-10.0", "150"),
                request("2026-09-11", "2", "0", "2", "0", "1", "1", "1", "1", "0.95", "0.94", null,
                        "2", "2", "10", 600, 840, 1020, 1260, null, null))) {
            var canonical = req.normalise(CLOCK).canonical();
            rows.add(Map.of("canonical", canonical, "key", PriceBatch.hash(
                    canonical + "\n" + EXAMPLE_REVISION + "\n" + ScenarioPreparation.Versions.current().canonical())));
        }
        return Map.of("exampleRevision", EXAMPLE_REVISION, "cases", rows);
    }

    private record DayFixture(String file, LocalDate day, List<PriceBatch.Slot> slots, PriceBatch batch) {
        Map<String, Object> summary() {
            return Map.of("file", file, "region", "NSW1", "day", day.toString(),
                    "contentHash", batch.contentHash(), "valid", batch.count(PriceBatch.Kind.VALUE),
                    "missing", batch.count(PriceBatch.Kind.MISSING), "sourceNull",
                    batch.count(PriceBatch.Kind.SOURCE_NULL));
        }

        PriceDay priceDay() {
            return batch.toPriceDay();
        }
    }

    private static DayFixture priceDay(Path dir, String date) throws Exception {
        var slots = new ArrayList<PriceBatch.Slot>(288);
        var lines = Files.readAllLines(dir.resolve(date + ".csv"), StandardCharsets.UTF_8);
        for (int i = 1; i < lines.size(); i++) {
            var parts = lines.get(i).split(",", -1);
            slots.add(new PriceBatch.Slot(PriceBatch.Kind.VALUE, new BigDecimal(parts[1])));
        }
        return new DayFixture(date + ".csv", LocalDate.parse(date), slots,
                new PriceBatch(PriceDay.Region.NSW1, LocalDate.parse(date), slots));
    }

    private record RunCase(String name, DayFixture day, Battery battery, ScheduleWindows windows,
            TradingCosts costs, Thresholds thresholds) {
    }

    private static RunCase runCase(String name, DayFixture day, double scale, double initial, double min,
            double max, Integer cs, Integer ce, Integer ds, Integer de,
            String chargeBelow, String dischargeAbove) {
        return new RunCase(name, day,
                new Battery(2 * scale, min, max, initial, scale, scale, scale, scale, Efficiency.roundTrip(.9)),
                ScheduleWindows.minutes(cs, ce, ds, de), new TradingCosts(2, 2, 10),
                chargeBelow == null ? null
                        : new Thresholds(new BigDecimal(chargeBelow), new BigDecimal(dischargeAbove)));
    }

    private static List<Map<String, Object>> runs(List<DayFixture> days) {
        var recent = days.get(0);
        var historical = days.get(1);
        var cases = List.of(
                runCase("recent-standard", recent, 1, 0, 0, 2, 600, 840, 1020, 1260, null, null),
                runCase("recent-thresholds", recent, 1, 0, 0, 2, 600, 840, 1020, 1260, "-10.0", "150"),
                runCase("recent-charge-heavy", recent, 1, 0, 0, 2, 600, 840, 1020, 1260, "1000", "2000"),
                runCase("recent-idle-thresholds", recent, 1, 0, 0, 2, 600, 840, 1020, 1260, "-1000", "1000000"),
                runCase("historical-standard", historical, 1, 0, 0, 2, 600, 840, 1020, 1260, null, null),
                runCase("historical-negative-prices", historical, 1, 0, 0, 2, 0, 240, 960, 1440, "-5", "100"),
                runCase("partial-inventory", recent, 1, 1, 0.5, 1.5, 0, 60, 1380, 1440, null, null),
                runCase("no-headroom", recent, 1, 2, 0, 2, 600, 840, 1020, 1260, null, null),
                runCase("large-site", historical, 100, 0, 0, 200, 600, 840, 1020, 1260, null, null),
                runCase("narrow-windows", recent, 1, 0, 0, 2, 600, 605, 1420, 1440, "0", "300"));
        var rows = new ArrayList<Map<String, Object>>();
        var limits = OrderedHindsight.Limits.standard();
        for (var c : cases) {
            var row = new LinkedHashMap<String, Object>();
            var prices = c.day().priceDay();
            row.put("name", c.name());
            row.put("day", c.day().day().toString());
            row.put("battery", c.battery());
            row.put("windows", c.windows());
            row.put("costs", c.costs());
            if (c.thresholds() != null) row.put("thresholds", c.thresholds());
            var fixed = new BatterySimulation().run(c.battery(), c.windows(), c.costs(), prices);
            row.put("fixed", strategy(fixed.dispatch(), fixed.accounting()));
            if (c.thresholds() != null) {
                var dispatch = new PriceThreshold().plan(c.battery(), c.thresholds(), prices);
                row.put("threshold", strategy(dispatch,
                        Accounting.calculate(c.battery(), c.costs(), prices, dispatch)));
            }
            var outcome = new OrderedHindsight().solve(c.battery(), c.windows(), c.costs(), prices, limits);
            var h = new LinkedHashMap<String, Object>();
            h.put("status", outcome.status().name());
            h.put("solverState", outcome.solverState());
            h.put("certificateState", outcome.certificateState());
            h.put("solverObjective", outcome.solverObjective());
            h.put("upperBound", outcome.upperBound());
            h.put("absoluteGap", outcome.absoluteGap());
            h.put("diagnostic", outcome.diagnostic());
            h.put("limits", Map.of("milliseconds", outcome.limits().milliseconds(),
                    "iterations", outcome.limits().iterations()));
            if (outcome.dispatch() != null)
                h.put("dispatch", strategy(outcome.dispatch(), outcome.accounting()));
            row.put("hindsight", h);
            rows.add(row);
        }
        return rows;
    }

    private static Map<String, Object> strategy(Dispatch dispatch, Accounting accounting) {
        var intervals = new ArrayList<List<Double>>(288);
        for (var interval : dispatch.intervals())
            intervals.add(List.of(interval.importedMWh(), interval.exportedMWh(), interval.endingEnergyMWh()));
        return Map.of("limitingReason", dispatch.limitingReason().name(), "accounting", accounting,
                "intervals", intervals);
    }

    /** The exact stored simulation_result payload shape for two- and three-strategy runs. */
    private static Map<String, Object> savedResults(DayFixture day) throws Exception {
        var json = new JsonMapper();
        var results = new LinkedHashMap<String, Object>();
        var prices = day.priceDay();
        for (var thresholds : new Thresholds[] { null, new Thresholds(new BigDecimal("-10"), new BigDecimal("150")) }) {
            var request = thresholds == null ? standard("2026-09-11", null, null)
                    : standard("2026-09-11", "-10", "150");
            var parameters = request.normalise(CLOCK);
            var comparison = SimulationComparison.run(parameters, prices, OrderedHindsight.Limits.standard());
            results.put(thresholds == null ? "twoStrategy" : "threeStrategy",
                    json.readValue(json.writeValueAsString(comparison), Map.class));
        }
        return results;
    }

    private ParityExport() {
    }
}
