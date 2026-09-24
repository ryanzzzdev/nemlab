package au.nemlab.infrastructure.jobs;

import au.nemlab.batterylab.PriceDay;
import au.nemlab.infrastructure.prices.PriceBatch;
import au.nemlab.infrastructure.prices.PriceSource;
import au.nemlab.infrastructure.prices.PriceStore;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.postgresql.ds.PGSimpleDataSource;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;
import org.springframework.jdbc.core.JdbcTemplate;
import org.testcontainers.postgresql.PostgreSQLContainer;

import javax.sql.DataSource;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Collections;
import java.util.UUID;
import java.util.concurrent.Callable;
import java.util.concurrent.Executors;

import static org.junit.jupiter.api.Assertions.*;

class RefreshJobServiceTest {
    private static final LocalDate DAY = LocalDate.of(2023, 9, 11);
    private static final PriceDay.Region REGION = PriceDay.Region.NSW1;
    private static final PostgreSQLContainer POSTGRES = new PostgreSQLContainer("postgres:18.6-alpine");

    private static AnnotationConfigApplicationContext context;
    private static RefreshJobService jobs;
    private static PriceStore prices;
    private static JdbcTemplate jdbc;

    @BeforeAll
    static void startDatabaseAndSpring() {
        POSTGRES.start();
        PGSimpleDataSource dataSource = new PGSimpleDataSource();
        dataSource.setURL(POSTGRES.getJdbcUrl());
        dataSource.setUser(POSTGRES.getUsername());
        dataSource.setPassword(POSTGRES.getPassword());
        PriceStore.migrate(dataSource);
        PriceStore.migrate(dataSource);

        context = new AnnotationConfigApplicationContext();
        context.registerBean(DataSource.class, () -> dataSource);
        context.register(RefreshJobConfiguration.class);
        context.refresh();
        jobs = context.getBean(RefreshJobService.class);
        prices = context.getBean(PriceStore.class);
        jdbc = new JdbcTemplate(dataSource);
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
                TRUNCATE simulation_result, simulation_job, simulation_input, refresh_job_event, refresh_request, refresh_job,
                    price_snapshot, price_current, price_import_attempt, price_revision, price_backfill
                """);
    }

    @Test
    void deduplicatesConcurrentSubmissionsAndRetainsRequestAliasesAfterCompletion() throws Exception {
        try (var executor = Executors.newFixedThreadPool(4)) {
            var requests = new ArrayList<Callable<UUID>>();
            for (int index = 0; index < 4; index++) {
                String key = "request-" + index;
                requests.add(() -> jobs.submit(key, REGION, DAY, "operator"));
            }
            var results = executor.invokeAll(requests);
            UUID id = results.getFirst().get();
            for (var result : results) {
                assertEquals(id, result.get());
            }
            assertEquals(1, count("refresh_job"));
            assertEquals(1, count("price_backfill"));
            RefreshJob claim = jobs.claim().orElseThrow();
            jobs.complete(id, claim.claimToken(), sample(false));
            assertEquals(id, jobs.submit("request-3", REGION, DAY, "operator"));
            assertNotEquals(id, jobs.submit("new-refresh", REGION, DAY, "operator"));
            assertThrows(IllegalArgumentException.class,
                    () -> jobs.submit("request-3", REGION, DAY.plusDays(1), "operator"));
        }
    }

    @Test
    void onlyOneWorkerCanClaimEvenWhenMultipleDaysAreQueued() throws Exception {
        jobs.submit("day-1", REGION, DAY, "scheduler");
        jobs.submit("day-2", REGION, DAY.plusDays(1), "scheduler");
        try (var executor = Executors.newFixedThreadPool(4)) {
            var requests = Collections.<Callable<Boolean>>nCopies(4, () -> jobs.claim().isPresent());
            int claimed = 0;
            for (var result : executor.invokeAll(requests)) {
                if (result.get()) {
                    claimed++;
                }
            }
            assertEquals(1, claimed);
        }
    }

    @Test
    void expiredClaimCannotWriteAndReplacementHasANewToken() {
        UUID id = jobs.submit("refresh", REGION, DAY, "operator");
        RefreshJob oldClaim = jobs.claim().orElseThrow();
        jdbc.update("UPDATE refresh_job SET lease_until = clock_timestamp() - interval '1 second' WHERE id = ?", id);
        assertThrows(RefreshJobService.StaleClaimException.class,
                () -> jobs.complete(id, oldClaim.claimToken(), sample(false)));
        assertTrue(jobs.claim().isEmpty());
        assertEquals("LEASE_EXPIRED", jobs.find(id).orElseThrow().diagnostic());
        makeReady(id);
        RefreshJob replacement = jobs.claim().orElseThrow();
        assertNotEquals(oldClaim.claimToken(), replacement.claimToken());
        assertThrows(RefreshJobService.StaleClaimException.class,
                () -> jobs.fail(id, oldClaim.claimToken(), "TRANSPORT_FAILURE"));
        assertEquals(0, count("price_import_attempt"));
        jobs.complete(id, replacement.claimToken(), sample(false));
        assertEquals(RefreshJob.Status.SUCCEEDED, jobs.find(id).orElseThrow().status());
        assertEquals("COMPLETE", prices.backfill(replacement.backfillId()).status());
    }

    @Test
    void exhaustedRetriesFailWithDiagnosticsAndDoNotClaimAgain() {
        UUID id = jobs.submit("refresh", REGION, DAY, "operator");
        for (int attempt = 1; attempt <= 3; attempt++) {
            RefreshJob claim = jobs.claim().orElseThrow();
            assertEquals(attempt, claim.attempts());
            jobs.fail(id, claim.claimToken(), "HTTP_503");
            assertTrue(jobs.claim().isEmpty());
            makeReady(id);
        }
        RefreshJob failed = jobs.find(id).orElseThrow();
        assertEquals(RefreshJob.Status.FAILED, failed.status());
        assertEquals("HTTP_503", failed.diagnostic());
        assertEquals(3, prices.history(REGION, DAY).size());
        assertTrue(jobs.claim().isEmpty());
    }

    @Test
    void finalExpiredAttemptFailsWithoutAnUnboundedCrashLoop() {
        UUID id = jobs.submit("refresh", REGION, DAY, "operator");
        for (int attempt = 1; attempt <= 3; attempt++) {
            assertTrue(jobs.claim().isPresent());
            jdbc.update("""
                    UPDATE refresh_job SET lease_until = clock_timestamp() - interval '1 second'
                    WHERE id = ?
                    """, id);
            assertTrue(jobs.claim().isEmpty());
            makeReady(id);
        }
        assertEquals(RefreshJob.Status.FAILED, jobs.find(id).orElseThrow().status());
        assertTrue(jobs.claim().isEmpty());
    }

    @Test
    void cancellationRevokesTheClaimAndRecordsTheActor() {
        UUID id = jobs.submit("refresh", REGION, DAY, "operator-alice");
        RefreshJob claim = jobs.claim().orElseThrow();
        assertTrue(jobs.cancel(id, "operator-bob"));
        assertFalse(jobs.cancel(id, "operator-bob"));
        assertThrows(RefreshJobService.StaleClaimException.class,
                () -> jobs.complete(id, claim.claimToken(), sample(false)));
        assertEquals(0, count("price_revision"));
        assertEquals("operator-bob", jdbc.queryForObject("""
                SELECT actor FROM refresh_job_event WHERE job_id = ? AND action = 'CANCELLED'
                """, String.class, id));
    }

    @Test
    void failedJobTransitionRollsBackPriceAndCheckpointWrites() {
        UUID id = jobs.submit("refresh", REGION, DAY, "operator");
        RefreshJob claim = jobs.claim().orElseThrow();
        jdbc.execute("""
                CREATE FUNCTION reject_job_success() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN
                    IF NEW.status = 'SUCCEEDED' THEN
                        RAISE EXCEPTION 'injected completion failure';
                    END IF;
                    RETURN NEW;
                END;
                $$
                """);
        jdbc.execute("""
                CREATE TRIGGER reject_job_success BEFORE UPDATE ON refresh_job
                FOR EACH ROW EXECUTE FUNCTION reject_job_success()
                """);
        try {
            assertThrows(RuntimeException.class, () -> jobs.complete(id, claim.claimToken(), sample(false)));
            assertEquals(0, count("price_revision"));
            assertEquals(0, count("price_import_attempt"));
            assertEquals(DAY, prices.backfill(claim.backfillId()).next());
            assertEquals(RefreshJob.Status.RUNNING, jobs.find(id).orElseThrow().status());
        } finally {
            jdbc.execute("DROP TRIGGER reject_job_success ON refresh_job");
            jdbc.execute("DROP FUNCTION reject_job_success()");
        }
        jobs.complete(id, claim.claimToken(), sample(false));
        assertEquals(1, count("price_revision"));
    }

    @ParameterizedTest
    @ValueSource(booleans = {false, true})
    void leaseExpiryDuringPriceWritesRollsBackCompleteAndIncompleteResults(boolean incomplete) {
        UUID id = jobs.submit("refresh", REGION, DAY, "operator");
        RefreshJob claim = jobs.claim().orElseThrow();
        jdbc.execute("""
                CREATE FUNCTION expire_job_during_write() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN
                    UPDATE refresh_job
                    SET lease_until = clock_timestamp() - interval '1 second'
                    WHERE status = 'RUNNING';
                    RETURN NEW;
                END;
                $$
                """);
        jdbc.execute("""
                CREATE TRIGGER expire_job_during_write BEFORE INSERT ON price_import_attempt
                FOR EACH ROW EXECUTE FUNCTION expire_job_during_write()
                """);
        try {
            assertThrows(RefreshJobService.StaleClaimException.class,
                    () -> jobs.complete(id, claim.claimToken(), sample(incomplete)));
            assertEquals(0, count("price_revision"));
            assertEquals(0, count("price_import_attempt"));
            assertEquals(DAY, prices.backfill(claim.backfillId()).next());
            assertEquals(RefreshJob.Status.RUNNING, jobs.find(id).orElseThrow().status());
        } finally {
            jdbc.execute("DROP TRIGGER expire_job_during_write ON price_import_attempt");
            jdbc.execute("DROP FUNCTION expire_job_during_write()");
        }
    }

    @Test
    void incompleteDayIsVisibleButNeverReportedAsSuccessful() {
        UUID id = jobs.submit("refresh", REGION, DAY, "operator");
        RefreshJob claim = jobs.claim().orElseThrow();
        jobs.complete(id, claim.claimToken(), sample(true));
        assertEquals(RefreshJob.Status.QUEUED, jobs.find(id).orElseThrow().status());
        assertEquals("INCOMPLETE_PRICE_DAY", jobs.find(id).orElseThrow().diagnostic());
        assertEquals(287, prices.coverage(REGION, DAY).orElseThrow().valid());
        assertEquals(DAY, prices.backfill(claim.backfillId()).next());
        makeReady(id);
        RefreshJob retry = jobs.claim().orElseThrow();
        jobs.complete(id, retry.claimToken(), sample(false));
        assertEquals(RefreshJob.Status.SUCCEEDED, jobs.find(id).orElseThrow().status());
    }

    @Test
    void validatesInputsAndBoundsQueueSize() {
        assertThrows(IllegalArgumentException.class,
                () -> jobs.submit("bad key", REGION, DAY, "operator"));
        assertThrows(IllegalArgumentException.class,
                () -> jobs.submit("future", REGION, LocalDate.of(2200, 1, 1), "operator"));
        for (int index = 0; index < 100; index++) {
            jobs.submit("day-" + index, REGION, DAY.plusDays(index), "scheduler");
        }
        assertThrows(IllegalStateException.class,
                () -> jobs.submit("overflow", REGION, DAY.plusDays(100), "scheduler"));
        assertEquals(100, count("refresh_job"));
        assertEquals(100, count("price_backfill"));
    }

    @Test
    void visitorRequestsDeduplicateOntoAnyActiveJobForTheDay() {
        UUID scheduled = jobs.submit("daily-price-v1:" + REGION + ":" + DAY, REGION, DAY, "scheduler");
        assertEquals(scheduled, jobs.submitVisitor(REGION, DAY));
        assertEquals(scheduled, jobs.submitVisitor(REGION, DAY));
        assertEquals(1, count("refresh_job"));
        // Visitor interest is recorded once against the existing job alongside the scheduler key.
        assertEquals(2, count("refresh_request"));
    }

    @Test
    void visitorRequestsRetryTerminalJobsThenExhaust() {
        UUID first = jobs.submitVisitor(REGION, DAY);
        RefreshJob firstClaim = jobs.claim().orElseThrow();
        jobs.complete(first, firstClaim.claimToken(), sample(false));
        assertEquals(RefreshJob.Status.SUCCEEDED, jobs.find(first).orElseThrow().status());
        // A later request for a day whose coverage vanished starts a fresh job under a new key.
        jdbc.execute("DELETE FROM price_current");
        UUID second = jobs.submitVisitor(REGION, DAY);
        assertNotEquals(first, second);
        RefreshJob secondClaim = jobs.claim().orElseThrow();
        jobs.failPermanently(second, secondClaim.claimToken(), "HTTP_401");
        UUID third = jobs.submitVisitor(REGION, DAY);
        assertNotEquals(second, third);
        RefreshJob thirdClaim = jobs.claim().orElseThrow();
        jobs.failPermanently(third, thirdClaim.claimToken(), "HTTP_401");
        // Three visitor attempts per day bound the re-request path.
        assertThrows(RefreshJobService.RefreshAttemptsExhausted.class,
                () -> jobs.submitVisitor(REGION, DAY));
        assertEquals(3, count("refresh_job"));
    }

    @Test
    void visitorPendingCapIsSeparateFromTheSharedQueue() {
        for (int index = 0; index < 10; index++) {
            jobs.submitVisitor(REGION, DAY.plusDays(index));
        }
        assertThrows(RefreshJobService.VisitorLimited.class,
                () -> jobs.submitVisitor(REGION, DAY.plusDays(10)));
        assertEquals(10, count("refresh_job"));
        // Operator and scheduler submissions still share the wider 100-job bound.
        UUID operator = jobs.submit("operator-day", REGION, DAY.plusDays(11), "operator-alice");
        assertNotNull(operator);
        assertEquals(11, count("refresh_job"));
    }

    private static PriceSource.Fetch sample(boolean incomplete) {
        var slots = new ArrayList<>(Collections.nCopies(288,
                new PriceBatch.Slot(PriceBatch.Kind.VALUE, new BigDecimal("42.5"))));
        if (incomplete) {
            slots.set(0, new PriceBatch.Slot(PriceBatch.Kind.MISSING, null));
        }
        return new PriceSource.Fetch(new PriceBatch(REGION, DAY, slots), Instant.now(),
                PriceBatch.hash("fixture-" + incomplete), "test-1");
    }

    private static int count(String table) {
        return jdbc.queryForObject("SELECT count(*) FROM " + table, Integer.class);
    }

    private static void makeReady(UUID id) {
        jdbc.update("UPDATE refresh_job SET available_at = clock_timestamp() WHERE id = ?", id);
    }
}
