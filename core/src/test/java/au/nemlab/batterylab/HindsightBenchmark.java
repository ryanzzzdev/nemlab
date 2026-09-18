package au.nemlab.batterylab;

import java.io.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.math.BigDecimal;
import java.time.*;
import java.util.*;
import java.lang.management.*;

/**
 * Explicit experiment harness, separate from unit tests. Writes
 * machine-readable measurements.
 */
public final class HindsightBenchmark {
    public static void main(String[] args) throws Exception {
        Path output = Path.of(args[0]);
        Files.createDirectories(output.toAbsolutePath().getParent());
        try (var writer = Files.newBufferedWriter(output)) {
            writer.write(
                    "case,repeat,status,solver_state,certificate_state,elapsed_ms,cpu_ms,heap_peak_mib,jvm_peak_rss_kib,fixed_margin,optimal_margin,upper_bound,gap\n");
            for (String name : List.of("recent", "historical", "synthetic-wide", "synthetic-negative", "large-site")) {
                var day = switch (name) {
                    case "recent" -> sample("2026-09-11");
                    case "historical", "large-site" -> sample("2023-09-11");
                    default -> synthetic(name.equals("synthetic-negative"));
                };
                var windows = name.startsWith("synthetic") ? new ScheduleWindows(0, 144, 144, 288)
                        : ScheduleWindows.minutes(600, 840, 1020, 1260);
                double scale = name.equals("large-site") ? 100 : 1;
                var battery = new Battery(2 * scale, 0, 2 * scale, 0, scale, scale, scale, scale,
                        Efficiency.roundTrip(.9));
                var costs = new TradingCosts(2, 2, 10);
                var fixed = new BatterySimulation().run(battery, windows, costs, day);
                for (int repeat = 0; repeat < 3; repeat++) {
                    for (var pool : ManagementFactory.getMemoryPoolMXBeans())
                        pool.resetPeakUsage();
                    long before = cpu();
                    var result = new OrderedHindsight().solve(battery, windows, costs, day,
                            OrderedHindsight.Limits.standard());
                    double cpuMillis = (cpu() - before) / 1e6;
                    double peakHeap = ManagementFactory.getMemoryPoolMXBeans().stream()
                            .filter(pool -> pool.getType() == MemoryType.HEAP)
                            .mapToLong(pool -> pool.getPeakUsage().getUsed()).sum() / 1048576.0;
                    if (result.status() != OrderedHindsight.Status.OPTIMAL)
                        throw new IllegalStateException(name + ": " + result);
                    if (result.accounting().margin() + 1e-6 < fixed.accounting().margin())
                        throw new IllegalStateException("Hindsight worse than baseline");
                    writer.write(String.format(Locale.ROOT, "%s,%d,%s,%s,%s,%.6f,%.6f,%.6f,%d,%.9f,%.9f,%.9f,%.9f%n",
                            name, repeat, result.status(), result.solverState(), result.certificateState(),
                            result.elapsedNanos() / 1e6, cpuMillis, peakHeap, rss(),
                            fixed.accounting().margin(), result.accounting().margin(), result.upperBound(),
                            result.absoluteGap()));
                    writer.flush();
                }
            }
        }
        try (var writer = Files.newBufferedWriter(output.resolveSibling("budget-probes.csv"))) {
            writer.write("budget_ms,iteration_limit,status,raw_state,elapsed_ms,has_dispatch,has_bound\n");
            var battery = new Battery(2, 0, 2, 0, 1, 1, 1, 1, Efficiency.roundTrip(.9));
            for (var limits : List.of(new OrderedHindsight.Limits(0, 100000), new OrderedHindsight.Limits(5000, 0),
                    new OrderedHindsight.Limits(1, 100000), new OrderedHindsight.Limits(5000, 1))) {
                var result = new OrderedHindsight().solve(battery, new ScheduleWindows(0, 144, 144, 288),
                        new TradingCosts(2, 2, 10), synthetic(false), limits);
                writer.write(String.format(Locale.ROOT, "%d,%d,%s,%s,%.6f,%b,%b%n", limits.milliseconds(),
                        limits.iterations(), result.status(),
                        result.solverState(), result.elapsedNanos() / 1e6, result.dispatch() != null,
                        result.upperBound() != null));
            }
        }
        System.out.println("Wrote solver measurements to " + output.toAbsolutePath());
    }

    static long cpu() {
        return ((com.sun.management.OperatingSystemMXBean) ManagementFactory.getOperatingSystemMXBean())
                .getProcessCpuTime();
    }

    static long rss() throws IOException {
        for (String line : Files.readAllLines(Path.of("/proc/self/status")))
            if (line.startsWith("VmHWM:"))
                return Long.parseLong(line.trim().split("\\s+")[1]);
        return -1;
    }

    static PriceDay sample(String date) throws IOException {
        var entries = new ArrayList<PriceDay.Interval>();
        try (var reader = new BufferedReader(new InputStreamReader(
                Objects.requireNonNull(HindsightBenchmark.class.getResourceAsStream("/prices/" + date + ".csv")),
                StandardCharsets.UTF_8))) {
            reader.readLine();
            for (String line; (line = reader.readLine()) != null;) {
                var cells = line.split(",");
                entries.add(PriceDay.Interval.fromEnd(PriceDay.Region.NSW1, OffsetDateTime.parse(cells[0]).toInstant(),
                        new BigDecimal(cells[1])));
            }
        }
        return new PriceDay(PriceDay.Region.NSW1, LocalDate.parse(date), entries);
    }

    static PriceDay synthetic(boolean negative) {
        var date = LocalDate.of(2026, 9, 11);
        var entries = new ArrayList<PriceDay.Interval>();
        var start = date.atStartOfDay().toInstant(PriceDay.NEM_OFFSET);
        for (int i = 0; i < 288; i++) {
            double price = negative ? -100 : (i % 7 == 0 ? -50 : 20 + (i * 37) % 250);
            entries.add(PriceDay.Interval.fromEnd(PriceDay.Region.NSW1, start.plusSeconds((i + 1L) * 300),
                    BigDecimal.valueOf(price)));
        }
        return new PriceDay(PriceDay.Region.NSW1, date, entries);
    }
}
