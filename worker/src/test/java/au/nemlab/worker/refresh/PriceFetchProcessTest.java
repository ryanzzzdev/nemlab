package au.nemlab.worker.refresh;

import au.nemlab.batterylab.PriceDay;
import au.nemlab.infrastructure.jobs.RefreshJob;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.*;

class PriceFetchProcessTest {
    @TempDir
    Path temporary;

    @Test
    void roundTripsValidatedPricesAndDeletesTemporaryOutput() throws Exception {
        Path marker = temporary.resolve("child");
        try (var fetcher = fixture("success", marker, Duration.ofSeconds(10))) {
            FetchOutcome result = fetcher.fetch(job());
            assertNull(result.failure());
            assertEquals(288, result.fetch().batch().slots().size());
            assertFalse(Files.exists(Path.of(Files.readAllLines(marker).get(1))));
        }
    }

    @Test
    void killsAStalledChildBeforeReturningATimeout() throws Exception {
        Path marker = temporary.resolve("child");
        try (var fetcher = fixture("hang", marker, Duration.ofSeconds(1))) {
            FetchOutcome result = fetcher.fetch(job());
            assertEquals("FETCH_DEADLINE_EXCEEDED", result.failure());
            assertTrue(result.retryable());
            assertChildStopped(marker);
        }
    }

    @Test
    void shutdownKillsTheActiveChildAndDisallowsAnotherFetch() throws Exception {
        Path marker = temporary.resolve("child");
        try (var executor = Executors.newSingleThreadExecutor();
                var fetcher = fixture("hang", marker, Duration.ofSeconds(30))) {
            var result = executor.submit(() -> fetcher.fetch(job()));
            awaitMarker(marker);
            fetcher.close();
            assertNotNull(result.get(5, TimeUnit.SECONDS).failure());
            assertChildStopped(marker);
            assertThrows(InterruptedException.class, () -> fetcher.fetch(job()));
        }
    }

    @Test
    void crashedAndMalformedChildrenProduceSafeDiagnosticCodes() throws Exception {
        for (String scenario : List.of("crash", "malformed")) {
            try (var fetcher = fixture(scenario, temporary.resolve(scenario), Duration.ofSeconds(10))) {
                assertEquals("FETCH_PROCESS_FAILED", fetcher.fetch(job()).failure());
            }
        }
    }

    static PriceFetchProcess fixture(String scenario, Path marker, Duration timeout) {
        String java = Path.of(System.getProperty("java.home"), "bin", "java").toString();
        List<String> command = List.of(java, "-cp", System.getProperty("worker.test.classpath"),
                FetchFixture.class.getName(), scenario, marker.toString());
        return new PriceFetchProcess(command, Map.of("OPEN_ELECTRICITY_API_KEY", "test-only"), timeout);
    }

    static void awaitMarker(Path marker) throws Exception {
        long deadline = System.nanoTime() + Duration.ofSeconds(5).toNanos();
        while ((!Files.exists(marker) || Files.size(marker) == 0) && System.nanoTime() < deadline) {
            Thread.sleep(20);
        }
        assertTrue(Files.exists(marker));
    }

    static void assertChildStopped(Path marker) throws Exception {
        long pid = Long.parseLong(Files.readAllLines(marker).getFirst());
        assertFalse(ProcessHandle.of(pid).map(ProcessHandle::isAlive).orElse(false));
    }

    private static RefreshJob job() {
        return new RefreshJob(UUID.randomUUID(), UUID.randomUUID(), PriceDay.Region.NSW1,
                LocalDate.of(2023, 9, 11), RefreshJob.Status.RUNNING, 1, UUID.randomUUID(),
                Instant.now().plusSeconds(300), Instant.now(), null);
    }
}
