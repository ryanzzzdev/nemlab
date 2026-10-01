package au.nemlab.worker.simulation;

import au.nemlab.batterylab.*;
import au.nemlab.infrastructure.batterylab.SimulationJobs;
import au.nemlab.infrastructure.prices.*;
import au.nemlab.worker.refresh.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import org.postgresql.ds.PGSimpleDataSource;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.jdbc.core.JdbcTemplate;
import org.testcontainers.postgresql.PostgreSQLContainer;
import java.nio.file.*;
import java.time.*;
import java.util.*;
import java.util.function.BooleanSupplier;
import static org.junit.jupiter.api.Assertions.*;

class SimulationWorkerTest {
    static final PostgreSQLContainer POSTGRES = new PostgreSQLContainer("postgres:18.6-alpine");
    static PGSimpleDataSource source;
    SimulationJobs jobs;
    JdbcTemplate jdbc;
    @TempDir Path temporary;

    @BeforeAll
    static void start() {
        POSTGRES.start();
        source = new PGSimpleDataSource();
        source.setURL(POSTGRES.getJdbcUrl());
        source.setUser(POSTGRES.getUsername());
        source.setPassword(POSTGRES.getPassword());
        PriceStore.migrate(source);
    }

    @AfterAll
    static void stop() { POSTGRES.stop(); }

    @BeforeEach
    void reset() {
        jobs = new SimulationJobs(source);
        jdbc = new JdbcTemplate(source);
        jdbc.execute("TRUNCATE simulation_result,simulation_job,simulation_input,refresh_job_event,refresh_request,refresh_job,price_snapshot,price_current,price_import_attempt,price_revision,price_backfill");
        var input = SimulationProcessTest.input();
        var slots = input.prices().intervals().stream().map(i -> new PriceBatch.Slot(PriceBatch.Kind.VALUE, i.price())).toList();
        new PriceStore(source).save(new PriceSource.Fetch(new PriceBatch(input.prices().region(), input.prices().date(), slots),
                Instant.now(), PriceBatch.hash("fixture"), "test"));
    }

    @Test
    void workerRestartRecoversClaimAndPersistsActualChildResults() throws Exception {
        UUID id = jobs.submit(SimulationProcessTest.input().request());
        var old = jobs.claim().orElseThrow();
        jdbc.update("UPDATE simulation_job SET lease_until=clock_timestamp()-interval '1 second' WHERE id=?", id);
        var process = SimulationProcessTest.fixture("success", temporary.resolve("success"), Duration.ofSeconds(15));
        var worker = new SimulationWorker(new SimulationJobs(source), process, Duration.ofMillis(20));
        try {
            worker.start();
            await(() -> jobs.find(id).orElseThrow().status() == SimulationJobs.Status.QUEUED);
            jdbc.update("UPDATE simulation_job SET available_at=clock_timestamp()-interval '1 second' WHERE id=?", id);
            await(() -> jobs.find(id).orElseThrow().status() == SimulationJobs.Status.SUCCEEDED);
            assertEquals(2, jobs.find(id).orElseThrow().attempts());
            assertEquals(230, jobs.result(id).orElseThrow().fixedAccounting().margin(), 1e-9);
            assertThrows(SimulationJobs.StaleClaim.class, () -> jobs.fail(id, old.token(), "LATE", true));
        } finally { worker.stop(); }
    }

    @Test
    void workerShutdownLeavesRecoverableWorkAndNoLiveChild() throws Exception {
        UUID id = jobs.submit(SimulationProcessTest.input().request());
        Path marker = temporary.resolve("stop");
        var worker = new SimulationWorker(jobs, SimulationProcessTest.fixture("hang", marker, Duration.ofSeconds(15)), Duration.ofMillis(20));
        try {
            worker.start();
            SimulationProcessTest.awaitMarker(marker);
        } finally { worker.stop(); }
        assertFalse(worker.isRunning());
        assertEquals(SimulationJobs.Status.QUEUED, jobs.find(id).orElseThrow().status());
        assertEquals("WORKER_STOPPED", jobs.find(id).orElseThrow().diagnostic());
        SimulationProcessTest.assertCleaned(marker);
    }

    @Test
    void deadlineFailuresReachTerminalStateAfterBoundedRetries() throws Exception {
        UUID id = jobs.submit(SimulationProcessTest.input().request());
        var worker = new SimulationWorker(jobs, SimulationProcessTest.fixture("hang", temporary.resolve("timeout"), Duration.ofSeconds(1)), Duration.ofMillis(20));
        try {
            worker.start();
            for (int attempt = 1; attempt <= 2; attempt++) {
                final int expected = attempt;
                await(() -> {
                    var job = jobs.find(id).orElseThrow();
                    return job.status() == SimulationJobs.Status.QUEUED && job.attempts() == expected;
                });
                jdbc.update("UPDATE simulation_job SET available_at=clock_timestamp()-interval '1 second' WHERE id=?", id);
            }
            await(() -> jobs.find(id).orElseThrow().status() == SimulationJobs.Status.FAILED);
            assertEquals(3, jobs.find(id).orElseThrow().attempts());
            assertEquals("SIMULATION_DEADLINE_EXCEEDED", jobs.find(id).orElseThrow().diagnostic());
            assertTrue(jobs.result(id).isEmpty());
        } finally { worker.stop(); }
    }

    @Test
    void independentOptInNeedsNoOeCredentialAndSharesDatabaseWhenBothEnabled() {
        configured().withPropertyValues("nemlab.simulation.enabled=true").run(context -> {
            assertNull(context.getStartupFailure());
            assertTrue(context.getBean(SimulationWorker.class).isRunning());
            assertEquals(0, context.getBeansOfType(RefreshWorker.class).size());
        });
        configured().withPropertyValues("nemlab.simulation.enabled=true", "nemlab.worker.enabled=true", "OPEN_ELECTRICITY_API_KEY=test-only")
                .run(context -> {
                    assertNull(context.getStartupFailure());
                    assertEquals(1, context.getBeansOfType(javax.sql.DataSource.class).size());
                    assertTrue(context.getBean(SimulationWorker.class).isRunning());
                    assertTrue(context.getBean(RefreshWorker.class).isRunning());
                });
        new ApplicationContextRunner().withUserConfiguration(SimulationConfiguration.class).run(context -> {
            assertNull(context.getStartupFailure());
            assertEquals(0, context.getBeansOfType(SimulationWorker.class).size());
        });
        configured().withPropertyValues("nemlab.simulation.enabled=true", "nemlab.simulation.poll-ms=0")
                .run(context -> assertNotNull(context.getStartupFailure()));
    }

    @Test
    void packagedWorkerPollsAndRunsItsOwnChild() throws Exception {
        UUID id = jobs.submit(SimulationProcessTest.input().request());
        var builder = new ProcessBuilder(SimulationProcessTest.java(), "-jar", System.getProperty("worker.test.jar"),
                "--nemlab.worker.enabled=false", "--nemlab.simulation.enabled=true", "--nemlab.simulation.poll-ms=1000");
        builder.environment().clear();
        builder.environment().putAll(Map.of("NEMLAB_DB_URL", POSTGRES.getJdbcUrl(), "NEMLAB_DB_USER", POSTGRES.getUsername(), "NEMLAB_DB_PASSWORD", POSTGRES.getPassword()));
        builder.redirectOutput(ProcessBuilder.Redirect.DISCARD).redirectError(ProcessBuilder.Redirect.DISCARD);
        Process worker = builder.start();
        try {
            await(() -> jobs.find(id).orElseThrow().status() == SimulationJobs.Status.SUCCEEDED);
            assertTrue(worker.isAlive());
            assertEquals(230, jobs.result(id).orElseThrow().hindsight().accounting().margin(), 1e-9);
        } finally {
            worker.destroy();
            if (!worker.waitFor(10, java.util.concurrent.TimeUnit.SECONDS)) {
                worker.destroyForcibly();
                worker.waitFor();
            }
        }
    }

    ApplicationContextRunner configured() {
        return new ApplicationContextRunner().withUserConfiguration(SimulationConfiguration.class, WorkerRefreshConfiguration.class)
                .withPropertyValues("NEMLAB_DB_URL=" + POSTGRES.getJdbcUrl(), "NEMLAB_DB_USER=" + POSTGRES.getUsername(),
                        "NEMLAB_DB_PASSWORD=" + POSTGRES.getPassword());
    }

    static void await(BooleanSupplier condition) throws Exception {
        long end = System.nanoTime() + Duration.ofSeconds(20).toNanos();
        while (!condition.getAsBoolean()) {
            if (System.nanoTime() >= end) fail("Condition did not become true within 20 seconds");
            Thread.sleep(30);
        }
    }
}
