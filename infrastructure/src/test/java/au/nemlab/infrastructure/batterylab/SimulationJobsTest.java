package au.nemlab.infrastructure.batterylab;

import au.nemlab.batterylab.*;
import au.nemlab.infrastructure.prices.*;
import org.junit.jupiter.api.*;
import org.postgresql.ds.PGSimpleDataSource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.testcontainers.postgresql.PostgreSQLContainer;
import java.math.BigDecimal;
import java.time.*;
import java.util.*;
import java.util.concurrent.*;
import static org.junit.jupiter.api.Assertions.*;

class SimulationJobsTest {
    static final PostgreSQLContainer POSTGRES = new PostgreSQLContainer("postgres:18.6-alpine");
    static PGSimpleDataSource source;
    SimulationJobs jobs;
    PriceStore prices;
    JdbcTemplate jdbc;

    @BeforeAll
    static void start() {
        POSTGRES.start();
        source = new PGSimpleDataSource();
        source.setURL(POSTGRES.getJdbcUrl());
        source.setUser(POSTGRES.getUsername());
        source.setPassword(POSTGRES.getPassword());
        PriceStore.migrate(source);
        PriceStore.migrate(source);
    }

    @AfterAll
    static void stop() { POSTGRES.stop(); }

    @BeforeEach
    void reset() {
        jobs = new SimulationJobs(source);
        prices = new PriceStore(source);
        jdbc = new JdbcTemplate(source);
        jdbc.execute("TRUNCATE simulation_result,simulation_job,simulation_input,refresh_job_event,refresh_request,refresh_job,price_snapshot,price_current,price_import_attempt,price_revision,price_backfill");
        prices.save(fetch("-30", Instant.now()));
    }

    static SimulationRequest request(int fee) {
        BigDecimal zero = BigDecimal.ZERO, one = BigDecimal.ONE, power = BigDecimal.valueOf(12);
        return new SimulationRequest(PriceDay.Region.NSW1, LocalDate.of(2023, 9, 11),
                new SimulationRequest.Site(one, zero, one, zero, power, power, power, power),
                new SimulationRequest.EfficiencyInput(one, one, null),
                new SimulationRequest.Costs(BigDecimal.valueOf(fee), zero, zero),
                new SimulationRequest.Windows(0, 5, 5, 10));
    }

    static PriceSource.Fetch fetch(String first, Instant at) {
        var slots = new ArrayList<>(Collections.nCopies(288, new PriceBatch.Slot(PriceBatch.Kind.VALUE, BigDecimal.ZERO)));
        slots.set(0, new PriceBatch.Slot(PriceBatch.Kind.VALUE, new BigDecimal(first)));
        slots.set(1, new PriceBatch.Slot(PriceBatch.Kind.VALUE, BigDecimal.valueOf(200)));
        return new PriceSource.Fetch(new PriceBatch(PriceDay.Region.NSW1, LocalDate.of(2023, 9, 11), slots), at, PriceBatch.hash(first), "fixture");
    }

    SimulationComparison compute(UUID id) {
        var input = jobs.input(id);
        return SimulationComparison.run(input.parameters(), input.prices(), input.versions().limits());
    }

    @Test
    void concurrentSubmissionAndClaimsDeduplicateGlobally() throws Exception {
        try (var executor = Executors.newFixedThreadPool(4)) {
            var submits = new ArrayList<Callable<UUID>>();
            for (int i = 0; i < 4; i++) submits.add(() -> new SimulationJobs(source).submit(request(0)));
            UUID id = null;
            for (var result : executor.invokeAll(submits)) {
                UUID next = result.get();
                if (id == null) id = next;
                assertEquals(id, next);
            }
            jobs.submit(request(1));
            var claims = new ArrayList<Callable<Optional<SimulationJobs.Job>>>();
            for (int i = 0; i < 4; i++) claims.add(() -> new SimulationJobs(source).claim());
            int running = 0;
            for (var result : executor.invokeAll(claims)) if (result.get().isPresent()) running++;
            assertEquals(1, running);
            assertEquals(2, count("simulation_input"));
            assertEquals(2, count("simulation_job"));
        }
    }

    @Test
    void savesBothStrategiesAndPreservesResultAndInputsAcrossCorrections() {
        UUID id = jobs.submit(request(0));
        var claim = jobs.claim().orElseThrow();
        var input = jobs.input(id);
        var result = compute(id);
        assertEquals(230, result.fixedAccounting().margin(), 1e-9);
        assertEquals(230, result.hindsight().accounting().margin(), 1e-9);
        jobs.complete(id, claim.token(), result);
        assertEquals(SimulationJobs.Status.SUCCEEDED, jobs.find(id).orElseThrow().status());
        assertEquals(result, jobs.result(id).orElseThrow());
        assertEquals(id, jobs.submit(request(0)));
        prices.save(fetch("-50", Instant.now().plusSeconds(10)));
        assertNotEquals(id, jobs.submit(request(0)));
        assertEquals(input, jobs.input(id));
        assertEquals(result, new SimulationJobs(source).result(id).orElseThrow());
        assertThrows(RuntimeException.class, () -> jdbc.update("UPDATE simulation_input SET request='{}' WHERE id=?", id));
        assertThrows(RuntimeException.class, () -> jdbc.update("DELETE FROM simulation_input WHERE id=?", id));
        assertThrows(RuntimeException.class, () -> jdbc.update("UPDATE simulation_result SET result='{}' WHERE id=?", id));
        assertThrows(RuntimeException.class, () -> jdbc.update("DELETE FROM simulation_result WHERE id=?", id));
    }

    @Test
    void expiredClaimsRecoverWithNewTokensAndStopAfterThreeAttempts() {
        UUID id = jobs.submit(request(0));
        var abandoned = jobs.claim().orElseThrow();
        for (int attempt = 1; attempt <= 3; attempt++) {
            jdbc.update("UPDATE simulation_job SET lease_until=clock_timestamp()-interval '1 second' WHERE id=?", id);
            jobs = new SimulationJobs(source);
            assertTrue(jobs.claim().isEmpty());
            assertThrows(SimulationJobs.StaleClaim.class, () -> jobs.complete(id, abandoned.token(), compute(id)));
            assertThrows(SimulationJobs.StaleClaim.class, () -> jobs.fail(id, abandoned.token(), "LATE", true));
            if (attempt < 3) {
                assertEquals(SimulationJobs.Status.QUEUED, jobs.find(id).orElseThrow().status());
                assertTrue(jobs.claim().isEmpty());
                ready(id);
                var replacement = jobs.claim().orElseThrow();
                assertNotEquals(abandoned.token(), replacement.token());
                assertEquals(attempt + 1, replacement.attempts());
            }
        }
        assertEquals(SimulationJobs.Status.FAILED, jobs.find(id).orElseThrow().status());
        assertEquals("LEASE_EXPIRED", jobs.find(id).orElseThrow().diagnostic());
        assertTrue(jobs.result(id).isEmpty());
    }

    @Test
    void retriesProcessFailureButNotPermanentFailure() {
        UUID id = jobs.submit(request(0));
        var claim = jobs.claim().orElseThrow();
        jobs.fail(id, claim.token(), "SIMULATION_DEADLINE_EXCEEDED", true);
        assertTrue(jobs.claim().isEmpty());
        ready(id);
        var second = jobs.claim().orElseThrow();
        jobs.fail(id, second.token(), "INVALID_CHILD_RESULT", false);
        assertEquals(SimulationJobs.Status.FAILED, jobs.find(id).orElseThrow().status());
        assertEquals(2, jobs.find(id).orElseThrow().attempts());
        assertEquals(id, jobs.submit(request(0)));
    }

    @Test
    void incompleteSolverResultIsRetainedWithoutClaimingSuccess() {
        UUID id = jobs.submit(request(0));
        var claim = jobs.claim().orElseThrow();
        var result = compute(id);
        var h = result.hindsight();
        var incomplete = new OrderedHindsight.Outcome(OrderedHindsight.Status.FEASIBLE_NOT_PROVEN,
                "FEASIBLE", "NOT_RUN", h.dispatch(), h.accounting(), h.solverObjective(), null, null,
                h.elapsedNanos(), h.limits(), "Proof incomplete");
        jobs.complete(id, claim.token(), new SimulationComparison(result.fixedDispatch(), result.fixedAccounting(), incomplete));
        assertEquals(SimulationJobs.Status.FAILED, jobs.find(id).orElseThrow().status());
        assertEquals("SOLVER_FEASIBLE_NOT_PROVEN", jobs.find(id).orElseThrow().diagnostic());
        assertEquals(incomplete, jobs.result(id).orElseThrow().hindsight());
    }

    @Test
    void rejectsTamperedAccountingWithoutWritingAResult() {
        UUID id = jobs.submit(request(0));
        var claim = jobs.claim().orElseThrow();
        var result = compute(id);
        var a = result.fixedAccounting();
        var invalid = new Accounting(a.importedMWh(), a.exportedMWh(), a.chargingCost(), a.revenue(),
                a.fees(), a.degradation(), a.margin() + 1, a.lossesMWh());
        assertThrows(IllegalArgumentException.class, () -> jobs.complete(id, claim.token(),
                new SimulationComparison(result.fixedDispatch(), invalid, result.hindsight())));
        assertTrue(jobs.result(id).isEmpty());
        assertEquals(SimulationJobs.Status.RUNNING, jobs.find(id).orElseThrow().status());
    }

    @Test
    void publicationFailureRollsBackResultAndTerminalState() {
        UUID id = jobs.submit(request(0));
        var claim = jobs.claim().orElseThrow();
        var result = compute(id);
        jdbc.execute("CREATE FUNCTION fail_simulation_finish() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'injected failure'; END; $$");
        jdbc.execute("CREATE TRIGGER fail_simulation_finish BEFORE UPDATE ON simulation_job FOR EACH ROW EXECUTE FUNCTION fail_simulation_finish()");
        try {
            assertThrows(RuntimeException.class, () -> jobs.complete(id, claim.token(), result));
            assertEquals(0, count("simulation_result"));
            assertEquals(SimulationJobs.Status.RUNNING, jobs.find(id).orElseThrow().status());
        } finally {
            jdbc.execute("DROP TRIGGER fail_simulation_finish ON simulation_job");
            jdbc.execute("DROP FUNCTION fail_simulation_finish()");
        }
        jobs.complete(id, claim.token(), result);
    }

    @Test
    void expiryDuringPublicationRollsBackResult() {
        UUID id = jobs.submit(request(0));
        var claim = jobs.claim().orElseThrow();
        var result = compute(id);
        jdbc.execute("CREATE FUNCTION expire_simulation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN UPDATE simulation_job SET lease_until=clock_timestamp()-interval '1 second' WHERE id=NEW.id; RETURN NEW; END; $$");
        jdbc.execute("CREATE TRIGGER expire_simulation BEFORE INSERT ON simulation_result FOR EACH ROW EXECUTE FUNCTION expire_simulation()");
        try {
            assertThrows(SimulationJobs.StaleClaim.class, () -> jobs.complete(id, claim.token(), result));
            assertTrue(jobs.result(id).isEmpty());
        } finally {
            jdbc.execute("DROP TRIGGER expire_simulation ON simulation_result");
            jdbc.execute("DROP FUNCTION expire_simulation()");
        }
    }

    @Test
    void queueCapacityAndSubmissionRollbackLeaveNoOrphanInputs() {
        jdbc.execute("CREATE FUNCTION fail_simulation_submit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'injected failure'; END; $$");
        jdbc.execute("CREATE TRIGGER fail_simulation_submit BEFORE INSERT ON simulation_job FOR EACH ROW EXECUTE FUNCTION fail_simulation_submit()");
        try {
            assertThrows(RuntimeException.class, () -> jobs.submit(request(0)));
            assertEquals(0, count("simulation_input"));
        } finally {
            jdbc.execute("DROP TRIGGER fail_simulation_submit ON simulation_job");
            jdbc.execute("DROP FUNCTION fail_simulation_submit()");
        }
        UUID first = jobs.submit(request(0));
        for (int i = 1; i < 100; i++) jobs.submit(request(i));
        assertThrows(SimulationJobs.QueueFull.class, () -> jobs.submit(request(100)));
        assertEquals(first, jobs.submit(request(0)));
        assertEquals(100, count("simulation_input"));
    }

    @Test
    void runningRefreshDoesNotBlockSimulationClaims() {
        UUID backfill = prices.createBackfill(PriceDay.Region.NSW1, LocalDate.of(2023, 9, 11), LocalDate.of(2023, 9, 12), Clock.systemUTC());
        jdbc.update("INSERT INTO refresh_job(id,backfill_id,region,market_day,status,attempts,claim_token,lease_until) VALUES (?,?,'NSW1','2023-09-11','RUNNING',1,?,clock_timestamp()+interval '5 minutes')",
                UUID.randomUUID(), backfill, UUID.randomUUID());
        UUID id = jobs.submit(request(0));
        assertEquals(id, jobs.claim().orElseThrow().id());
    }

    private int count(String table) { return jdbc.queryForObject("SELECT count(*) FROM " + table, Integer.class); }
    private void ready(UUID id) { jdbc.update("UPDATE simulation_job SET available_at=clock_timestamp()-interval '1 second' WHERE id=?", id); }
}
