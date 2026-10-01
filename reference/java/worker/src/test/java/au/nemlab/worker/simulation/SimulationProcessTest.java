package au.nemlab.worker.simulation;

import au.nemlab.batterylab.*;
import au.nemlab.infrastructure.batterylab.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import java.math.BigDecimal;
import java.nio.file.*;
import java.time.*;
import java.util.*;
import java.util.concurrent.*;
import static org.junit.jupiter.api.Assertions.*;

class SimulationProcessTest {
    @TempDir Path temporary;

    static SimulationJobs.Input input() {
        BigDecimal zero = BigDecimal.ZERO, one = BigDecimal.ONE, power = BigDecimal.valueOf(12);
        LocalDate day = LocalDate.of(2023, 9, 11);
        var request = new SimulationRequest(PriceDay.Region.NSW1, day,
                new SimulationRequest.Site(one, zero, one, zero, power, power, power, power),
                new SimulationRequest.EfficiencyInput(one, one, null),
                new SimulationRequest.Costs(zero, zero, zero), new SimulationRequest.Windows(0, 5, 5, 10));
        var intervals = new ArrayList<PriceDay.Interval>();
        Instant start = day.atStartOfDay().toInstant(PriceDay.NEM_OFFSET);
        for (int i = 0; i < 288; i++) intervals.add(PriceDay.Interval.fromEnd(PriceDay.Region.NSW1,
                start.plusSeconds((i + 1L) * 300), BigDecimal.valueOf(i == 0 ? -30 : 200)));
        return new SimulationJobs.Input("a".repeat(64), request, new PriceDay(PriceDay.Region.NSW1, day, intervals),
                ScenarioPreparation.Versions.current());
    }

    static SimulationProcess fixture(String scenario, Path marker, Duration timeout) {
        return new SimulationProcess(List.of(java(), "-Xmx512m", "-XX:ActiveProcessorCount=2", "-cp",
                System.getProperty("worker.test.classpath"), SimulationFixture.class.getName(), scenario, marker.toString()), timeout);
    }

    static String java() { return Path.of(System.getProperty("java.home"), "bin", "java").toString(); }

    static void awaitMarker(Path marker) throws Exception {
        long end = System.nanoTime() + Duration.ofSeconds(5).toNanos();
        while ((!Files.exists(marker) || Files.size(marker) == 0) && System.nanoTime() < end) Thread.sleep(20);
        assertTrue(Files.exists(marker));
    }

    static void assertCleaned(Path marker) throws Exception {
        var lines = Files.readAllLines(marker);
        assertFalse(ProcessHandle.of(Long.parseLong(lines.getFirst())).map(ProcessHandle::isAlive).orElse(false));
        assertFalse(Files.exists(Path.of(lines.get(1))));
        assertFalse(Files.exists(Path.of(lines.get(2))));
    }

    @Test
    void actualChildComputesBothStrategiesWithoutCredentialsAndCleansFiles() throws Exception {
        Path marker = temporary.resolve("success");
        try (var process = fixture("success", marker, Duration.ofSeconds(15))) {
            var outcome = process.execute(input());
            assertNull(outcome.failure());
            assertEquals(OrderedHindsight.Status.OPTIMAL, outcome.result().hindsight().status());
            assertEquals(230, outcome.result().fixedAccounting().margin(), 1e-9);
            assertCleaned(marker);
        }
    }

    @Test
    void packagedBootJarSupportsTheSameChildMode() throws Exception {
        try (var process = new SimulationProcess(List.of(java(), "-Xmx512m", "-XX:ActiveProcessorCount=2", "-jar",
                System.getProperty("worker.test.jar")), Duration.ofSeconds(15))) {
            var outcome = process.execute(input());
            assertNull(outcome.failure());
            assertEquals(230, outcome.result().hindsight().accounting().margin(), 1e-9);
        }
    }

    @Test
    void parentDeadlineKillsStalledChildBeforeReturning() throws Exception {
        Path marker = temporary.resolve("hang");
        try (var process = fixture("hang", marker, Duration.ofSeconds(1))) {
            var outcome = process.execute(input());
            assertEquals("SIMULATION_DEADLINE_EXCEEDED", outcome.failure());
            assertTrue(outcome.retryable());
            assertCleaned(marker);
        }
    }

    @Test
    void shutdownKillsChildAndPreventsNewExecution() throws Exception {
        Path marker = temporary.resolve("stop");
        try (var executor = Executors.newSingleThreadExecutor(); var process = fixture("hang", marker, Duration.ofSeconds(15))) {
            var future = executor.submit(() -> process.execute(input()));
            awaitMarker(marker);
            process.close();
            assertNotNull(future.get(5, TimeUnit.SECONDS).failure());
            assertCleaned(marker);
            assertThrows(InterruptedException.class, () -> process.execute(input()));
        }
    }

    @Test
    void corruptResultsAreTerminalAndCrashesAreRetryable() throws Exception {
        for (String scenario : List.of("malformed", "oversized", "crash")) {
            Path marker = temporary.resolve(scenario);
            try (var process = fixture(scenario, marker, Duration.ofSeconds(15))) {
                var outcome = process.execute(input());
                assertEquals(scenario.equals("crash") ? "SIMULATION_PROCESS_FAILED" : "INVALID_CHILD_RESULT", outcome.failure());
                assertEquals(scenario.equals("crash"), outcome.retryable());
                assertCleaned(marker);
            }
        }
    }

    @Test
    void childWatchdogBoundsAnOrphanWithoutTheParentDeadline() throws Exception {
        Path marker = temporary.resolve("watchdog");
        long start = System.nanoTime();
        try (var process = fixture("watchdog", marker, Duration.ofSeconds(25))) {
            var outcome = process.execute(input());
            assertEquals("SIMULATION_DEADLINE_EXCEEDED", outcome.failure());
            assertTrue(Duration.ofNanos(System.nanoTime() - start).toSeconds() < 23);
            assertCleaned(marker);
        }
    }

    @Test
    void unsupportedStoredVersionDoesNotLaunchChild() throws Exception {
        var i = input();
        var v = i.versions();
        var old = new ScenarioPreparation.Versions(v.request(), "old-model", v.fixed(), v.hindsight(), v.solver(), v.executionProfile(), v.limits());
        Path marker = temporary.resolve("unsupported");
        try (var process = fixture("success", marker, Duration.ofSeconds(15))) {
            var outcome = process.execute(new SimulationJobs.Input(i.key(), i.request(), i.prices(), old));
            assertEquals("UNSUPPORTED_SIMULATION_VERSION", outcome.failure());
            assertFalse(outcome.retryable());
            assertFalse(Files.exists(marker));
        }
    }
}
