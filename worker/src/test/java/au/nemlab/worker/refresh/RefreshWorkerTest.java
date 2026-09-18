package au.nemlab.worker.refresh;

import au.nemlab.batterylab.PriceDay;
import au.nemlab.infrastructure.jobs.RefreshJob;
import au.nemlab.infrastructure.jobs.RefreshJobConfiguration;
import au.nemlab.infrastructure.jobs.RefreshJobService;
import au.nemlab.infrastructure.prices.PriceStore;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.postgresql.ds.PGSimpleDataSource;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;
import org.springframework.jdbc.core.JdbcTemplate;
import org.testcontainers.postgresql.PostgreSQLContainer;

import javax.sql.DataSource;
import java.nio.file.Path;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.List;
import java.util.UUID;
import java.util.function.BooleanSupplier;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.*;

class RefreshWorkerTest {
    private static final PostgreSQLContainer POSTGRES = new PostgreSQLContainer("postgres:18.6-alpine");
    private static final LocalDate DAY = LocalDate.of(2023, 9, 11);
    private static AnnotationConfigApplicationContext context;
    private static RefreshJobService jobs;
    private static PriceStore prices;
    private static JdbcTemplate jdbc;

    @TempDir
    Path temporary;

    @BeforeAll
    static void start() {
        POSTGRES.start();
        var source = new PGSimpleDataSource();
        source.setURL(POSTGRES.getJdbcUrl());
        source.setUser(POSTGRES.getUsername());
        source.setPassword(POSTGRES.getPassword());
        PriceStore.migrate(source);
        context = new AnnotationConfigApplicationContext();
        context.registerBean(DataSource.class, () -> source);
        context.register(RefreshJobConfiguration.class);
        context.refresh();
        jobs = context.getBean(RefreshJobService.class);
        prices = context.getBean(PriceStore.class);
        jdbc = new JdbcTemplate(source);
    }

    @AfterAll
    static void stop() {
        if (context != null) {
            context.close();
        }
        POSTGRES.stop();
    }

    @BeforeEach
    void reset() {
        jdbc.execute("""
                TRUNCATE refresh_job_event, refresh_request, refresh_job,
                    price_snapshot, price_current, price_import_attempt, price_revision, price_backfill
                """);
    }

    @Test
    void executesAManuallySubmittedJobThroughTheRealQueue() throws Exception {
        UUID id = jobs.submit("manual", PriceDay.Region.NSW1, DAY, "test-operator");
        RefreshWorker worker = worker("success");
        try {
            worker.start();
            await(() -> jobs.find(id).orElseThrow().status() == RefreshJob.Status.SUCCEEDED);
            assertEquals(288, prices.coverage(PriceDay.Region.NSW1, DAY).orElseThrow().valid());
        } finally {
            worker.stop();
        }
        assertFalse(worker.isRunning());
    }

    @Test
    void restartRecoversAnExpiredClaimAndDoesNotReuseItsToken() throws Exception {
        UUID id = jobs.submit("manual", PriceDay.Region.NSW1, DAY, "test-operator");
        RefreshJob abandoned = jobs.claim().orElseThrow();
        jdbc.update("""
                UPDATE refresh_job SET lease_until = clock_timestamp() - interval '1 second' WHERE id = ?
                """, id);
        RefreshWorker restarted = worker("success");
        try {
            restarted.start();
            await(() -> jobs.find(id).orElseThrow().status() == RefreshJob.Status.QUEUED);
            jdbc.update("UPDATE refresh_job SET available_at = clock_timestamp() WHERE id = ?", id);
            await(() -> jobs.find(id).orElseThrow().status() == RefreshJob.Status.SUCCEEDED);
            assertEquals(2, jobs.find(id).orElseThrow().attempts());
            assertThrows(RefreshJobService.StaleClaimException.class,
                    () -> jobs.fail(id, abandoned.claimToken(), "OLD_WORKER"));
        } finally {
            restarted.stop();
        }
    }

    @Test
    void credentialFailureIsTerminalAfterOneAttempt() throws Exception {
        UUID id = jobs.submit("manual", PriceDay.Region.NSW1, DAY, "test-operator");
        RefreshWorker worker = worker("unauthorised");
        try {
            worker.start();
            await(() -> jobs.find(id).orElseThrow().status() == RefreshJob.Status.FAILED);
            assertEquals(1, jobs.find(id).orElseThrow().attempts());
            assertEquals("HTTP_401", jobs.find(id).orElseThrow().diagnostic());
        } finally {
            worker.stop();
        }
    }

    @Test
    void shutdownKillsFetchAndLeavesJobRecoverable() throws Exception {
        UUID id = jobs.submit("manual", PriceDay.Region.NSW1, DAY, "test-operator");
        RefreshWorker worker = worker("hang");
        try {
            worker.start();
            PriceFetchProcessTest.awaitMarker(temporary.resolve("hang"));
        } finally {
            worker.stop();
        }
        PriceFetchProcessTest.assertChildStopped(temporary.resolve("hang"));
        assertEquals(RefreshJob.Status.QUEUED, jobs.find(id).orElseThrow().status());
        assertEquals(0, prices.history(PriceDay.Region.NSW1, DAY).stream()
                .filter(attempt -> attempt.status().equals("COMPLETE")).count());
    }

    @Test
    void dailyScheduleUsesFixedNemTimeAndDeduplicatesAcrossRestarts() {
        List<PriceDay.Region> regions = List.of(PriceDay.Region.NSW1, PriceDay.Region.VIC1);
        Clock before = Clock.fixed(Instant.parse("2023-09-12T14:14:59Z"), ZoneOffset.UTC);
        Clock after = Clock.fixed(Instant.parse("2023-09-12T14:15:00Z"), ZoneOffset.UTC);
        RefreshSchedule schedule = new RefreshSchedule(jobs, before, regions);
        schedule.submitDue();
        schedule.submitDue();
        new RefreshSchedule(jobs, before, regions).submitDue();
        assertEquals(2, jdbc.queryForObject("SELECT count(*) FROM refresh_job", Integer.class));
        assertEquals(DAY, jdbc.queryForObject("SELECT min(market_day) FROM refresh_job", LocalDate.class));
        new RefreshSchedule(jobs, after, regions).submitDue();
        assertEquals(4, jdbc.queryForObject("SELECT count(*) FROM refresh_job", Integer.class));
        assertEquals(DAY.plusDays(1),
                jdbc.queryForObject("SELECT max(market_day) FROM refresh_job", LocalDate.class));
    }

    @Test
    void packagedWorkerLaunchesItsFetchChildWithoutLiveOeTraffic() throws Exception {
        UUID id = jobs.submit("packaged", PriceDay.Region.NSW1, DAY, "test-operator");
        // Deliberately corrupt this test job to force source validation before any network call.
        jdbc.update("UPDATE refresh_job SET market_day = DATE '2200-01-01' WHERE id = ?", id);
        String java = Path.of(System.getProperty("java.home"), "bin", "java").toString();
        ProcessBuilder builder = new ProcessBuilder(java, "-jar", System.getProperty("worker.test.jar"));
        builder.environment().clear();
        builder.environment().put("NEMLAB_WORKER_ENABLED", "true");
        builder.environment().put("NEMLAB_WORKER_SCHEDULE_ENABLED", "false");
        builder.environment().put("NEMLAB_DB_URL", POSTGRES.getJdbcUrl());
        builder.environment().put("NEMLAB_DB_USER", POSTGRES.getUsername());
        builder.environment().put("NEMLAB_DB_PASSWORD", POSTGRES.getPassword());
        builder.environment().put("OPEN_ELECTRICITY_API_KEY", "test-only");
        builder.redirectOutput(ProcessBuilder.Redirect.DISCARD);
        builder.redirectError(ProcessBuilder.Redirect.DISCARD);
        Process process = builder.start();
        try {
            await(() -> jobs.find(id).orElseThrow().status() == RefreshJob.Status.FAILED);
            assertEquals("INVALID_SOURCE_DATA_OR_CONFIGURATION", jobs.find(id).orElseThrow().diagnostic());
            assertEquals(1, jobs.find(id).orElseThrow().attempts());
        } finally {
            process.destroy();
            if (!process.waitFor(10, TimeUnit.SECONDS)) {
                process.destroyForcibly();
                assertTrue(process.waitFor(5, TimeUnit.SECONDS));
            }
        }
    }

    @Test
    void optInConfigurationStartsAgainstMigratedDatabaseAndStopsCleanly() {
        configuredRunner().run(application -> {
            assertNull(application.getStartupFailure());
            assertTrue(application.getBean(RefreshWorker.class).isRunning());
        });
    }

    @Test
    void disabledConfigurationNeedsNoDatabaseOrCredential() {
        new ApplicationContextRunner().withUserConfiguration(WorkerRefreshConfiguration.class)
                .run(application -> {
                    assertNull(application.getStartupFailure());
                    assertEquals(0, application.getBeansOfType(RefreshWorker.class).size());
                });
    }

    @Test
    void invalidConfigurationFailsBeforePolling() {
        configuredRunner().withPropertyValues("nemlab.worker.poll-ms=0")
                .run(application -> assertNotNull(application.getStartupFailure()));
        configuredRunner().withPropertyValues("nemlab.worker.schedule-enabled=true", "nemlab.worker.regions=BOGUS")
                .run(application -> assertNotNull(application.getStartupFailure()));
        configuredRunner().withPropertyValues("OPEN_ELECTRICITY_API_KEY=")
                .run(application -> assertNotNull(application.getStartupFailure()));
    }

    private RefreshWorker worker(String scenario) {
        var fetcher = PriceFetchProcessTest.fixture(scenario, temporary.resolve(scenario), Duration.ofSeconds(10));
        var schedule = new RefreshSchedule(jobs, Clock.systemUTC(), List.of());
        return new RefreshWorker(jobs, schedule, fetcher, Duration.ofMillis(20));
    }

    private static ApplicationContextRunner configuredRunner() {
        return new ApplicationContextRunner().withUserConfiguration(WorkerRefreshConfiguration.class)
                .withPropertyValues("nemlab.worker.enabled=true", "nemlab.worker.schedule-enabled=false",
                        "NEMLAB_DB_URL=" + POSTGRES.getJdbcUrl(), "NEMLAB_DB_USER=" + POSTGRES.getUsername(),
                        "NEMLAB_DB_PASSWORD=" + POSTGRES.getPassword(), "OPEN_ELECTRICITY_API_KEY=test-only");
    }

    private static void await(BooleanSupplier condition) throws Exception {
        long deadline = System.nanoTime() + Duration.ofSeconds(10).toNanos();
        while (!condition.getAsBoolean() && System.nanoTime() < deadline) {
            Thread.sleep(20);
        }
        assertTrue(condition.getAsBoolean(), "Worker did not reach expected state before deadline");
    }
}
