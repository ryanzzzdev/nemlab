package au.nemlab.infrastructure.prices;

import au.nemlab.batterylab.PriceDay;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.*;
import org.postgresql.ds.PGSimpleDataSource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.testcontainers.postgresql.PostgreSQLContainer;
import tools.jackson.databind.json.JsonMapper;
import java.net.*;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.time.*;
import java.math.BigDecimal;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
import static org.junit.jupiter.api.Assertions.*;

class PriceIngestionTest {
    static final LocalDate DAY = LocalDate.of(2023, 9, 11);
    static final Instant AT = Instant.parse("2026-09-17T00:00:00Z");
    static final Clock CLOCK = Clock.fixed(AT, ZoneOffset.UTC);
    static final PriceDay.Region REGION = PriceDay.Region.NSW1;
    static final JsonMapper JSON = new JsonMapper();
    static final PostgreSQLContainer POSTGRES = new PostgreSQLContainer("postgres:18.6-alpine");
    static String body;
    static PGSimpleDataSource ds;
    PriceStore store;
    JdbcTemplate jdbc;

    @BeforeAll
    static void start() throws Exception {
        body = new String(
                Objects.requireNonNull(PriceIngestionTest.class.getResourceAsStream("/historical-price-response.json"))
                        .readAllBytes(),
                StandardCharsets.UTF_8);
        POSTGRES.start();
        ds = new PGSimpleDataSource();
        ds.setURL(POSTGRES.getJdbcUrl());
        ds.setUser(POSTGRES.getUsername());
        ds.setPassword(POSTGRES.getPassword());
        PriceStore.migrate(ds);
        PriceStore.migrate(ds);
    }

    @AfterAll
    static void stop() {
        POSTGRES.stop();
    }

    @BeforeEach
    void reset() {
        jdbc = new JdbcTemplate(ds);
        jdbc.execute("""
                TRUNCATE refresh_job_event, refresh_request, refresh_job,
                    price_snapshot, price_current, price_import_attempt, price_revision, price_backfill
                """);
        store = new PriceStore(ds);
    }

    static PriceSource.Fetch sample() {
        return OePriceSource.parse(REGION, DAY, body, AT);
    }

    static PriceSource.Fetch changed(PriceSource.Fetch base, int slot, PriceBatch.Slot value, Instant at) {
        var slots = new ArrayList<>(base.batch().slots());
        slots.set(slot, value);
        return new PriceSource.Fetch(new PriceBatch(base.batch().region(), base.batch().day(), slots), at,
                PriceBatch.hash("changed" + value), "test-1");
    }

    @Test
    void officialFixtureHasCorrectBoundaryAndExactPrices() {
        var batch = sample().batch();
        assertTrue(batch.complete());
        assertEquals(288, batch.slots().size());
        var prices = batch.toPriceDay();
        assertEquals(DAY.atStartOfDay().toInstant(PriceDay.NEM_OFFSET), prices.intervals().getFirst().start());
        assertEquals(DAY.plusDays(1).atStartOfDay().toInstant(PriceDay.NEM_OFFSET), prices.intervals().getLast().end());
        assertEquals(6, batch.slots().stream().filter(s -> s.price().signum() < 0).count());
        assertEquals(2, batch.slots().stream().filter(s -> s.price().signum() == 0).count());
    }

    @Test
    void importsAreIdempotentAndSnapshotsSurviveCorrections() {
        var first = sample();
        UUID revision = store.save(first), snapshot = store.snapshot(revision);
        assertEquals(revision, store.save(first));
        assertEquals(1, jdbc.queryForObject("SELECT count(*) FROM price_revision", Integer.class));
        var correction = changed(first, 0, new PriceBatch.Slot(PriceBatch.Kind.VALUE, new BigDecimal("123.456789")),
                AT.plusSeconds(1));
        UUID second = store.save(correction);
        assertNotEquals(revision, second);
        assertEquals(second, store.coverage(REGION, DAY).orElseThrow().revision());
        assertEquals(first.batch().toPriceDay(), store.snapshotPrices(snapshot));
        assertEquals(new BigDecimal("123.456789"), store.revision(second).slots().getFirst().price());
        assertEquals(3, store.history(REGION, DAY).size());
        assertTrue(store.history(REGION, DAY).stream().allMatch(a -> a.responseHash() != null));
        assertThrows(Exception.class,
                () -> jdbc.update("UPDATE price_revision SET valid_count=287,missing_count=1 WHERE id=?", revision));
        assertThrows(Exception.class, () -> jdbc.update("DELETE FROM price_snapshot WHERE id=?", snapshot));
    }

    @Test
    void olderFetchCannotOverwriteFresherCurrentAndRevertingContentReusesRevision() {
        var original = sample();
        UUID a = store.save(original);
        var changed = changed(original, 0, new PriceBatch.Slot(PriceBatch.Kind.VALUE, BigDecimal.ZERO),
                AT.plusSeconds(10));
        UUID b = store.save(changed);
        store.save(original);
        assertEquals(b, store.coverage(REGION, DAY).orElseThrow().revision());
        store.save(new PriceSource.Fetch(original.batch(), AT.plusSeconds(20), original.responseHash(),
                original.sourceVersion()));
        assertEquals(a, store.coverage(REGION, DAY).orElseThrow().revision());
        assertEquals(2, jdbc.queryForObject("SELECT count(*) FROM price_revision", Integer.class));
    }

    @Test
    void missingNullAndZeroRemainDistinctAndCannotProduceSnapshot() {
        var missing = changed(sample(), 0, new PriceBatch.Slot(PriceBatch.Kind.MISSING, null), AT);
        var incomplete = changed(missing, 1, new PriceBatch.Slot(PriceBatch.Kind.SOURCE_NULL, null), AT);
        UUID revision = store.save(incomplete);
        var coverage = store.coverage(REGION, DAY).orElseThrow();
        assertEquals(286, coverage.valid());
        assertEquals(1, coverage.missing());
        assertEquals(1, coverage.sourceNull());
        assertThrows(IllegalStateException.class, () -> store.revision(revision).toPriceDay());
        assertThrows(Exception.class, () -> store.snapshot(revision));
        assertTrue(store.coverage(REGION, DAY.plusDays(1)).isEmpty());
    }

    @Test
    void crashRestartResumesFromPersistedNextDay() {
        UUID id = store.createBackfill(REGION, DAY, DAY.plusDays(2), CLOCK);
        AtomicInteger calls = new AtomicInteger();
        PriceSource source = (region, day) -> {
            calls.incrementAndGet();
            if (day.equals(DAY.plusDays(1)))
                throw new java.io.IOException("secret response text must not persist");
            return sample();
        };
        var runner = new PriceBackfill(store, source, CLOCK);
        assertTrue(runner.step(id));
        assertFalse(runner.step(id));
        assertEquals(DAY.plusDays(1), store.backfill(id).next());
        assertEquals("PAUSED", store.backfill(id).status());
        assertFalse(jdbc.queryForObject("SELECT diagnostic FROM price_backfill WHERE id=?", String.class, id)
                .contains("secret"));
        var freshStore = new PriceStore(ds);
        var resumed = new PriceBackfill(freshStore,
                (region, day) -> new PriceSource.Fetch(new PriceBatch(region, day, sample().batch().slots()), AT,
                        PriceBatch.hash("day2"), "test-1"),
                CLOCK);
        assertTrue(resumed.step(id));
        assertFalse(resumed.step(id));
        assertEquals("COMPLETE", freshStore.backfill(id).status());
        assertEquals(2, jdbc.queryForObject("SELECT count(*) FROM price_revision", Integer.class));
    }

    @Test
    void incompleteDayPausesWithoutAdvancing() {
        UUID id = store.createBackfill(REGION, DAY, DAY.plusDays(1), CLOCK);
        var fetch = changed(sample(), 0, new PriceBatch.Slot(PriceBatch.Kind.MISSING, null), AT);
        assertFalse(new PriceBackfill(store, (r, d) -> fetch, CLOCK).step(id));
        assertEquals(DAY, store.backfill(id).next());
        assertEquals("PAUSED", store.backfill(id).status());
        assertTrue(new PriceBackfill(store, (r, d) -> new PriceSource.Fetch(sample().batch(), AT.plusSeconds(1),
                sample().responseHash(), sample().sourceVersion()), CLOCK).step(id));
        assertEquals("COMPLETE", store.backfill(id).status());
    }

    @Test
    void dataAndCheckpointRollbackTogether() {
        UUID id = store.createBackfill(REGION, DAY, DAY.plusDays(1), CLOCK);
        jdbc.execute(
                "CREATE FUNCTION test_fail_checkpoint() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'injected checkpoint failure'; END $$");
        jdbc.execute(
                "CREATE TRIGGER test_checkpoint BEFORE UPDATE ON price_backfill FOR EACH ROW EXECUTE FUNCTION test_fail_checkpoint()");
        try {
            assertThrows(Exception.class, () -> store.commitDay(id, DAY, sample()));
            assertEquals(0, jdbc.queryForObject("SELECT count(*) FROM price_revision", Integer.class));
            assertEquals(0, jdbc.queryForObject("SELECT count(*) FROM price_import_attempt", Integer.class));
            assertEquals(DAY, store.backfill(id).next());
        } finally {
            jdbc.execute("DROP TRIGGER test_checkpoint ON price_backfill");
            jdbc.execute("DROP FUNCTION test_fail_checkpoint()");
        }
    }

    @Test
    void rejectsStaleCheckpointAndUnboundedDates() {
        UUID id = store.createBackfill(REGION, DAY, DAY.plusDays(1), CLOCK);
        store.commitDay(id, DAY, sample());
        assertThrows(IllegalStateException.class, () -> store.commitDay(id, DAY, sample()));
        assertThrows(IllegalArgumentException.class, () -> store.createBackfill(REGION, DAY, DAY.plusDays(32), CLOCK));
        assertThrows(IllegalArgumentException.class,
                () -> store.createBackfill(REGION, LocalDate.of(2021, 9, 30), LocalDate.of(2021, 10, 1), CLOCK));
        assertThrows(IllegalArgumentException.class,
                () -> store.createBackfill(REGION, LocalDate.of(2026, 9, 17), LocalDate.of(2026, 9, 18), CLOCK));
    }

    @SuppressWarnings("unchecked")
    @Test
    void parserRejectsBadMetadataDuplicatesAndMalformedValues() {
        assertThrows(IllegalArgumentException.class, () -> OePriceSource.parse(PriceDay.Region.QLD1, DAY, body, AT));
        assertThrows(IllegalArgumentException.class,
                () -> OePriceSource.parse(REGION, DAY, body.replace("$/MWh", "MW"), AT));
        Map<String, Object> root = JSON.readValue(body, Map.class);
        var series = (List<Map<String, Object>>) root.get("data");
        var results = (List<Map<String, Object>>) series.getFirst().get("results");
        var rows = (List<List<Object>>) results.getFirst().get("data");
        rows.add(rows.get(1));
        assertThrows(IllegalArgumentException.class,
                () -> OePriceSource.parse(REGION, DAY, JSON.writeValueAsString(root), AT));
    }

    @Test
    void httpAdapterBoundsQueryRetriesAndNeverEchoesResponseBody() throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        AtomicInteger requests = new AtomicInteger();
        List<Long> sleeps = new ArrayList<>();
        List<String> queries = new ArrayList<>();
        server.createContext("/prices", exchange -> {
            queries.add(exchange.getRequestURI().getRawQuery());
            int n = requests.incrementAndGet();
            byte[] response = (n == 1 ? "do-not-log-response" : body).getBytes(StandardCharsets.UTF_8);
            if (n == 1)
                exchange.getResponseHeaders().add("Retry-After", "2");
            exchange.sendResponseHeaders(n == 1 ? 429 : 200, response.length);
            exchange.getResponseBody().write(response);
            exchange.close();
        });
        server.start();
        try (var client = HttpClient.newHttpClient()) {
            var source = new OePriceSource(client,
                    URI.create("http://127.0.0.1:" + server.getAddress().getPort() + "/prices"), "test-secret", CLOCK,
                    sleeps::add);
            assertTrue(source.fetch(REGION, DAY).batch().complete());
            assertEquals(2, requests.get());
            assertEquals(List.of(2000L), sleeps);
            assertTrue(URLDecoder.decode(queries.getFirst(), StandardCharsets.UTF_8)
                    .contains("date_end=2023-09-12T00:05:00"));
            assertFalse(queries.getFirst().contains("test-secret"));
        } finally {
            server.stop(0);
        }
    }

    @SuppressWarnings("unchecked")
    @Test
    void parserPreservesMissingAndExplicitNullWithoutInventingZero() {
        Map<String, Object> root = JSON.readValue(body, Map.class);
        var series = (List<Map<String, Object>>) root.get("data");
        var results = (List<Map<String, Object>>) series.getFirst().get("results");
        var rows = (List<List<Object>>) results.getFirst().get("data");
        rows.remove(1);
        rows.get(1).set(1, null);
        var parsed = OePriceSource.parse(REGION, DAY, JSON.writeValueAsString(root), AT).batch();
        assertEquals(PriceBatch.Kind.MISSING, parsed.slots().get(0).kind());
        assertEquals(PriceBatch.Kind.SOURCE_NULL, parsed.slots().get(1).kind());
        assertEquals(286, parsed.count(PriceBatch.Kind.VALUE));
        assertThrows(IllegalArgumentException.class,
                () -> OePriceSource.parse(REGION, DAY, body.replace("00:05:00+10:00", "00:06:00+10:00"), AT));
    }

    @Test
    void repeatedConcurrentImportsRemainIdempotent() throws Exception {
        try (var executor = java.util.concurrent.Executors.newFixedThreadPool(4)) {
            var tasks = new ArrayList<java.util.concurrent.Callable<UUID>>();
            for (int i = 0; i < 4; i++)
                tasks.add(() -> store.save(sample()));
            Set<UUID> revisions = new HashSet<>();
            for (var future : executor.invokeAll(tasks))
                revisions.add(future.get());
            assertEquals(1, revisions.size());
            assertEquals(4, jdbc.queryForObject("SELECT count(*) FROM price_import_attempt", Integer.class));
        }
    }

    @Test
    void httpErrorsAreBoundedAndSanitised() throws Exception {
        for (int status : List.of(401, 503, 429)) {
            HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
            AtomicInteger calls = new AtomicInteger();
            server.createContext("/", exchange -> {
                calls.incrementAndGet();
                byte[] bytes = "secret-body".getBytes(StandardCharsets.UTF_8);
                exchange.sendResponseHeaders(status, bytes.length);
                exchange.getResponseBody().write(bytes);
                exchange.close();
            });
            server.start();
            try (var client = HttpClient.newHttpClient()) {
                var source = new OePriceSource(client,
                        URI.create("http://127.0.0.1:" + server.getAddress().getPort() + "/"), "test-secret", CLOCK,
                        millis -> {
                        });
                var failure = assertThrows(OePriceSource.Failure.class, () -> source.fetch(REGION, DAY));
                assertEquals("HTTP_" + status, failure.code());
                assertFalse(failure.toString().contains("secret"));
                assertEquals(status == 401 ? 1 : 3, calls.get());
            } finally {
                server.stop(0);
            }
        }
    }

    @Test
    void oversizedResponseIsCancelledAndRetryBudgetIsFinite() throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        AtomicInteger calls = new AtomicInteger();
        server.createContext("/", exchange -> {
            calls.incrementAndGet();
            byte[] bytes = new byte[2_000_100];
            try {
                exchange.sendResponseHeaders(200, bytes.length);
                exchange.getResponseBody().write(bytes);
            } catch (java.io.IOException cancelled) {
            } finally {
                exchange.close();
            }
        });
        server.start();
        try (var client = HttpClient.newHttpClient()) {
            var source = new OePriceSource(client,
                    URI.create("http://127.0.0.1:" + server.getAddress().getPort() + "/"), "test-secret", CLOCK,
                    millis -> {
                    });
            assertThrows(java.io.IOException.class, () -> source.fetch(REGION, DAY));
            assertTrue(calls.get() <= 3);
        } finally {
            server.stop(0);
        }
    }

    @Test
    void operatorStatusIncludesSafeFailureCode() {
        UUID id = store.createBackfill(REGION, DAY, DAY.plusDays(1), CLOCK);
        assertFalse(new PriceBackfill(store, (r, d) -> {
            throw new OePriceSource.Failure("HTTP_401");
        }, CLOCK).step(id));
        assertEquals("HTTP_401", store.backfill(id).diagnostic());
        assertEquals("HTTP_401", store.history(REGION, DAY).getFirst().diagnostic());
        assertEquals("FAILED", store.history(REGION, DAY).getFirst().status());
    }

}
