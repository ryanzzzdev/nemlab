package au.nemlab.api.simulation;

import au.nemlab.api.ContractCapture;
import au.nemlab.batterylab.*;
import au.nemlab.infrastructure.batterylab.SimulationJobs;
import au.nemlab.infrastructure.jobs.RefreshJob;
import au.nemlab.infrastructure.jobs.RefreshJobService;
import au.nemlab.infrastructure.prices.*;
import org.junit.jupiter.api.*;
import org.postgresql.ds.PGSimpleDataSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.postgresql.PostgreSQLContainer;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;
import javax.sql.DataSource;
import java.math.BigDecimal;
import java.net.*;
import java.net.http.*;
import java.time.*;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        properties = {"nemlab.simulation-api.enabled=true", "nemlab.admin.enabled=false", "nemlab.data.enabled=false"})
class SimulationHttpTest {
    static final String PATH = "/api/v1/simulations";
    static final LocalDate DAY = LocalDate.of(2023, 10, 1);
    static final Instant AT = Instant.parse("2026-09-20T00:00:00Z");
    static final JsonMapper JSON = new JsonMapper();
    static final PostgreSQLContainer POSTGRES = start();
    @LocalServerPort int port;
    @Autowired SimulationJobs jobs;
    @Autowired RefreshJobService refreshes;
    @Autowired PriceStore prices;
    @Autowired DataSource source;

    static PostgreSQLContainer start() {
        var database = new PostgreSQLContainer("postgres:18.6-alpine");
        database.start();
        var ds = new PGSimpleDataSource();
        ds.setURL(database.getJdbcUrl()); ds.setUser(database.getUsername()); ds.setPassword(database.getPassword());
        PriceStore.migrate(ds);
        return database;
    }

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry p) {
        p.add("NEMLAB_DB_URL", POSTGRES::getJdbcUrl);
        p.add("NEMLAB_DB_USER", POSTGRES::getUsername);
        p.add("NEMLAB_DB_PASSWORD", POSTGRES::getPassword);
    }

    @AfterAll static void stop() { POSTGRES.stop(); }

    @BeforeEach void reset() {
        new JdbcTemplate(source).execute("TRUNCATE simulation_result,simulation_job,simulation_input,refresh_job_event,refresh_request,refresh_job,price_snapshot,price_current,price_import_attempt,price_revision,price_backfill");
    }

    static String body() {
        return """
                {"region":"NSW1","day":"2023-10-01",
                 "site":{"capacityMWh":"1.00","minimumMWh":"0","maximumMWh":"1","initialMWh":"0",
                         "chargeMW":"12","dischargeMW":"12","importLimitMW":"12","exportLimitMW":"12"},
                 "efficiency":{"roundTrip":"1"},
                 "costs":{"importFee":"0","exportFee":"0","degradationPerExportedMWh":"0"},
                 "windows":{"chargeStart":0,"chargeEnd":5,"dischargeStart":5,"dischargeEnd":10}}
                """;
    }

    @Test
    void submitPollCompleteAndReopenPreservesExactInputsAfterCorrections() throws Exception {
        save("-30.000000000000000001", null, AT);
        var submitted = call("POST", PATH, body());
        assertEquals(202, submitted.statusCode());
        UUID id = UUID.fromString(json(submitted).get("id").asString());
        assertEquals(PATH + "/" + id, submitted.headers().firstValue("Location").orElseThrow());
        assertEquals("2", submitted.headers().firstValue("Retry-After").orElseThrow());
        assertEquals("QUEUED", json(call("GET", PATH + "/" + id, null)).get("status").asString());
        assertEquals("RESULT_NOT_READY", json(call("GET", PATH + "/" + id + "/result", null)).get("code").asString());
        var claim = jobs.claim().orElseThrow();
        var running = call("GET", PATH + "/" + id, null);
        assertEquals("RUNNING", json(running).get("status").asString());
        assertFalse(running.body().contains(claim.token().toString()));
        complete(claim);
        var result = call("GET", PATH + "/" + id + "/result", null);
        assertEquals(200, result.statusCode());
        var data = json(result);
        assertEquals(230, data.get("fixed").get("accounting").get("margin").asDouble(), 1e-9);
        assertEquals(288, data.get("hindsight").get("dispatch").get("intervals").size());
        assertEquals("OPTIMAL", data.get("solver").get("status").asString());
        assertEquals("-30.000000000000000001", data.get("prices").get(0).get("price").asString());
        assertEquals("1", data.get("inputs").get("site").get("capacityMWh").asString());
        assertEquals("1", data.get("inputs").get("efficiency").get("charge").asString());
        assertFalse(data.get("inputs").get("efficiency").has("roundTrip"));
        assertEquals("2023-09-30T14:00:00Z", data.get("prices").get(0).get("start").asString());
        assertEquals("2023-10-01T14:00:00Z", data.get("prices").get(287).get("end").asString());
        for (String privateField : List.of("claim_token", "claimToken", "leaseUntil", "diagnostic", "solverState", "certificateState"))
            assertFalse(result.body().contains(privateField), privateField);
        var duplicate = call("POST", PATH, body().replace("1.00", "1.0"));
        assertEquals(200, duplicate.statusCode());
        assertEquals(id.toString(), json(duplicate).get("id").asString());
        save("-50", null, AT.plusSeconds(1));
        assertEquals(data, json(call("GET", PATH + "/" + id + "/result", null)));
        assertNotEquals(id.toString(), json(call("POST", PATH, body())).get("id").asString());
        assertEquals(0, new JdbcTemplate(source).queryForObject("SELECT count(*) FROM refresh_job", Integer.class));
    }

    @Test
    void thresholdRequestsRoundTripThroughTheStoredResult() throws Exception {
        save("-30", null, AT);
        var withThresholds = body().replace("\"windows\":{\"chargeStart\":0,\"chargeEnd\":5,\"dischargeStart\":5,\"dischargeEnd\":10}",
                "\"windows\":{\"chargeStart\":0,\"chargeEnd\":5,\"dischargeStart\":5,\"dischargeEnd\":10},\"thresholds\":{\"chargeBelow\":\"-10.0\",\"dischargeAbove\":\"150\"}");
        var submitted = call("POST", PATH, withThresholds);
        assertEquals(202, submitted.statusCode());
        UUID id = UUID.fromString(json(submitted).get("id").asString());
        complete(jobs.claim().orElseThrow());
        var data = json(call("GET", PATH + "/" + id + "/result", null));
        var threshold = data.get("threshold");
        assertEquals("price-threshold-v1", threshold.get("version").asString());
        assertEquals("-10", threshold.get("thresholds").get("chargeBelow").asText());
        assertEquals(288, threshold.get("dispatch").get("intervals").size());
        assertTrue(threshold.get("accounting").has("margin"));
        assertEquals("-10", data.get("inputs").get("thresholds").get("chargeBelow").asString());
        // The plain scenario is a different scenario, and its result carries no experiment.
        var plain = call("POST", PATH, body());
        UUID plainId = UUID.fromString(json(plain).get("id").asString());
        assertNotEquals(id, plainId);
        complete(jobs.claim().orElseThrow());
        var plainData = json(call("GET", PATH + "/" + plainId + "/result", null));
        assertTrue(plainData.get("threshold").isNull());
        assertFalse(plainData.get("inputs").has("thresholds"));
    }

    @Test
    void duplicatePendingRequestsReuseJobAndNormalisedLegs() throws Exception {
        save("-30", null, AT);
        var first = call("POST", PATH, body());
        var second = call("POST", PATH, body().replace("\"roundTrip\":\"1\"", "\"charge\":\"1.00\",\"discharge\":\"1\""));
        assertEquals(202, second.statusCode());
        assertEquals(json(first).get("id"), json(second).get("id"));
        assertEquals(1, new JdbcTemplate(source).queryForObject("SELECT count(*) FROM simulation_job", Integer.class));
    }

    @Test
    void strictJsonAndDomainErrorsRejectBeforeCreatingJobs() throws Exception {
        save("-30", null, AT);
        for (String value : List.of("null", "[]", "{}", "{", body() + " {}",
                body().replace("\"capacityMWh\":\"1.00\"", "\"capacityMWh\":1"),
                body().replace("\"region\":\"NSW1\"", "\"region\":\"NSW1\",\"region\":\"QLD1\""),
                body().replace("\"minimumMWh\":\"0\"", "\"unknown\":0,\"minimumMWh\":\"0\""),
                body().replace("\"region\":\"NSW1\"", "\"region\":\"BOGUS\""),
                body().replace("2023-10-01", "2200-01-01"), body().replace("2023-10-01", "2023-02-30"),
                body().replace("\"roundTrip\":\"1\"", "\"roundTrip\":\"1\",\"charge\":\"1\""),
                body().replace("\"capacityMWh\":\"1.00\"", "\"capacityMWh\":\"NaN\""),
                body().replace("\"chargeMW\":\"12\"", "\"chargeMW\":\"-1\""),
                body().replace("\"chargeEnd\":5", "\"chargeEnd\":6"),
                body().replace("\"chargeEnd\":5", "\"chargeEnd\":5.0"),
                body().replace("\"importFee\":\"0\"", "\"importFee\":\"1e100000\""),
                body().replace("\"dischargeEnd\":10}}", "\"dischargeEnd\":10},\"thresholds\":{\"chargeBelow\":\"30\"}}"),
                body().replace("\"dischargeEnd\":10}}", "\"dischargeEnd\":10},\"thresholds\":{\"chargeBelow\":\"150\",\"dischargeAbove\":\"30\"}}"),
                body().replace("\"dischargeEnd\":10}}", "\"dischargeEnd\":10},\"thresholds\":{\"chargeBelow\":30,\"dischargeAbove\":\"150\"}}"),
                body().replace("\"dischargeEnd\":10}}", "\"dischargeEnd\":10},\"thresholds\":{\"chargeBelow\":\"30\",\"dischargeAbove\":\"150\",\"extra\":\"1\"}}"))) {
            var response = call("POST", PATH, value);
            assertEquals(400, response.statusCode(), value);
            assertEquals("INVALID_REQUEST", json(response).get("code").asString());
            assertTrue(json(response).has("field"));
        }
        assertEquals(0, new JdbcTemplate(source).queryForObject("SELECT count(*) FROM simulation_input", Integer.class));
        assertEquals(400, call("GET", PATH + "/not-uuid", null).statusCode());
        assertEquals(400, call("GET", PATH + "/1-1-1-1-1/result", null).statusCode());
    }

    @Test
    void eligibleDaysWithoutStoredPricesEnqueueOneVisitorRefresh() throws Exception {
        var pending = call("POST", PATH, body());
        assertEquals(409, pending.statusCode());
        assertEquals("PRICE_REFRESH_PENDING", json(pending).get("code").asString());
        assertEquals("30", pending.headers().firstValue("Retry-After").orElseThrow());
        assertEquals(1, new JdbcTemplate(source).queryForObject("SELECT count(*) FROM refresh_job", Integer.class));
        assertEquals("visitor-price-v1:NSW1:2023-10-01", new JdbcTemplate(source)
                .queryForObject("SELECT request_key FROM refresh_request", String.class));
        // Repeated submissions deduplicate onto the same active job.
        assertEquals("PRICE_REFRESH_PENDING", json(call("POST", PATH, body())).get("code").asString());
        assertEquals(1, new JdbcTemplate(source).queryForObject("SELECT count(*) FROM refresh_job", Integer.class));
        assertEquals(0, new JdbcTemplate(source).queryForObject("SELECT count(*) FROM simulation_job", Integer.class));
        // Once the fetch commits a complete revision the submission proceeds normally.
        RefreshJob claim = refreshes.claim().orElseThrow();
        refreshes.complete(claim.id(), claim.claimToken(), fetch(DAY));
        var submitted = call("POST", PATH, body());
        assertEquals(202, submitted.statusCode());
        assertEquals(1, new JdbcTemplate(source).queryForObject("SELECT count(*) FROM simulation_job", Integer.class));
    }

    @Test
    void incompleteDaysAlsoTriggerRefreshButIneligibleDaysNeverDo() throws Exception {
        save("-30", PriceBatch.Kind.MISSING, AT);
        var pending = call("POST", PATH, body());
        assertEquals(409, pending.statusCode());
        assertEquals("PRICE_REFRESH_PENDING", json(pending).get("code").asString());
        assertEquals(1, new JdbcTemplate(source).queryForObject("SELECT count(*) FROM refresh_job", Integer.class));
        for (String bad : List.of("2020-01-01", "2200-01-01")) {
            var response = call("POST", PATH, body().replace("2023-10-01", bad));
            assertEquals(400, response.statusCode());
            assertEquals("INVALID_REQUEST", json(response).get("code").asString());
        }
        assertEquals(1, new JdbcTemplate(source).queryForObject("SELECT count(*) FROM refresh_job", Integer.class));
    }

    @Test
    void visitorRefreshesRetryAfterFailureThenReportExhaustion() throws Exception {
        for (int attempt = 1; attempt <= 3; attempt++) {
            assertEquals("PRICE_REFRESH_PENDING", json(call("POST", PATH, body())).get("code").asString());
            RefreshJob claim = refreshes.claim().orElseThrow();
            refreshes.failPermanently(claim.id(), claim.claimToken(), "HTTP_401");
            assertEquals(attempt, new JdbcTemplate(source).queryForObject("SELECT count(*) FROM refresh_job", Integer.class));
        }
        var exhausted = call("POST", PATH, body());
        assertEquals(409, exhausted.statusCode());
        assertEquals("PRICE_REFRESH_FAILED", json(exhausted).get("code").asString());
        assertEquals(3, new JdbcTemplate(source).queryForObject("SELECT count(*) FROM refresh_job", Integer.class));
        assertEquals(0, new JdbcTemplate(source).queryForObject("SELECT count(*) FROM simulation_job", Integer.class));
    }

    @Test
    void visitorFetchesCannotSaturateTheSharedQueue() throws Exception {
        for (int i = 1; i <= 10; i++) {
            var response = call("POST", PATH, body().replace("2023-10-01", "2023-10-" + String.format("%02d", i)));
            assertEquals("PRICE_REFRESH_PENDING", json(response).get("code").asString());
        }
        assertEquals(10, new JdbcTemplate(source).queryForObject("SELECT count(*) FROM refresh_job", Integer.class));
        var limited = call("POST", PATH, body().replace("2023-10-01", "2023-10-15"));
        assertEquals(429, limited.statusCode());
        assertEquals("VISITOR_REFRESH_LIMIT", json(limited).get("code").asString());
        assertEquals("60", limited.headers().firstValue("Retry-After").orElseThrow());
        assertEquals(10, new JdbcTemplate(source).queryForObject("SELECT count(*) FROM refresh_job", Integer.class));
    }

    @Test
    void failedAndUnprovenJobsNeverExposeAProvenResultOrResetOnResubmission() throws Exception {
        save("-30", null, AT);
        UUID id = UUID.fromString(json(call("POST", PATH, body())).get("id").asString());
        var claim = jobs.claim().orElseThrow();
        jobs.fail(id, claim.token(), "SIMULATION_DEADLINE_EXCEEDED", false);
        assertEquals("SIMULATION_DEADLINE_EXCEEDED", json(call("GET", PATH + "/" + id, null)).get("failureCode").asString());
        assertEquals("SIMULATION_FAILED", json(call("GET", PATH + "/" + id + "/result", null)).get("code").asString());
        assertEquals(200, call("POST", PATH, body()).statusCode());
        assertEquals(1, jobs.find(id).orElseThrow().attempts());
        var other = call("POST", PATH, body().replace("\"importFee\":\"0\"", "\"importFee\":\"1\""));
        UUID otherId = UUID.fromString(json(other).get("id").asString());
        var second = jobs.claim().orElseThrow();
        var input = jobs.input(otherId);
        var result = SimulationComparison.run(input.parameters(), input.prices(), input.versions().limits());
        var h = result.hindsight();
        var incomplete = new OrderedHindsight.Outcome(OrderedHindsight.Status.FEASIBLE_NOT_PROVEN, "FEASIBLE", "NOT_RUN",
                h.dispatch(), h.accounting(), h.solverObjective(), null, null, h.elapsedNanos(), h.limits(), "internal diagnostic must stay private");
        jobs.complete(otherId, second.token(), new SimulationComparison(result.fixedDispatch(), result.fixedAccounting(), incomplete));
        var status = call("GET", PATH + "/" + otherId, null);
        assertEquals("SOLVER_FEASIBLE_NOT_PROVEN", json(status).get("failureCode").asString());
        assertFalse(status.body().contains("internal diagnostic"));
        assertEquals(409, call("GET", PATH + "/" + otherId + "/result", null).statusCode());
    }

    @Test
    void unknownIdsBodyLimitAndContentTypeHaveExplicitResponses() throws Exception {
        String id = UUID.randomUUID().toString();
        assertEquals(404, call("GET", PATH + "/" + id, null).statusCode());
        assertEquals(404, call("GET", PATH + "/" + id + "/result", null).statusCode());
        assertEquals(413, call("POST", PATH, " ".repeat(16_385)).statusCode());
        assertEquals(415, request("POST", PATH, body(), "text/plain", true).statusCode());
        assertEquals(404, request("POST", "/api/admin/v1/price-refreshes", "{}", "application/json", false).statusCode());
    }

    @Test
    void queueSaturationReturnsRetryAfterWhileDuplicatesStillWork() throws Exception {
        save("-30", null, AT);
        for (int i = 0; i < 100; i++) jobs.submit(SimulationJson.parse(body().replace("\"importFee\":\"0\"", "\"importFee\":\"" + i + "\"").getBytes(java.nio.charset.StandardCharsets.UTF_8)));
        var full = call("POST", PATH, body().replace("\"importFee\":\"0\"", "\"importFee\":\"100\""));
        assertEquals(429, full.statusCode());
        assertEquals("5", full.headers().firstValue("Retry-After").orElseThrow());
        assertEquals(202, call("POST", PATH, body()).statusCode());
    }

    @Test
    void databaseFailuresAreSafeAcrossAllOperations() throws Exception {
        var ds = (PGSimpleDataSource) source;
        ds.setURL("jdbc:postgresql://127.0.0.1:1/unavailable");
        try {
            String id = UUID.randomUUID().toString();
            for (var response : List.of(call("POST", PATH, body()), call("GET", PATH + "/" + id, null), call("GET", PATH + "/" + id + "/result", null))) {
                assertEquals(503, response.statusCode());
                assertEquals("STORAGE_UNAVAILABLE", json(response).get("code").asString());
                assertFalse(response.body().contains("jdbc:"));
            }
        } finally { ds.setURL(POSTGRES.getJdbcUrl()); }
    }

    void complete(SimulationJobs.Job claim) {
        var input = jobs.input(claim.id());
        jobs.complete(claim.id(), claim.token(), SimulationComparison.run(input.parameters(), input.prices(), input.versions().limits()));
    }

    static PriceSource.Fetch fetch(LocalDate day) {
        var slots = new ArrayList<>(Collections.nCopies(288,
                new PriceBatch.Slot(PriceBatch.Kind.VALUE, BigDecimal.ONE)));
        return new PriceSource.Fetch(new PriceBatch(PriceDay.Region.NSW1, day, slots),
                AT, PriceBatch.hash("visitor-fetch"), "test");
    }

    void save(String first, PriceBatch.Kind gap, Instant at) {
        var slots = new ArrayList<>(Collections.nCopies(288, new PriceBatch.Slot(PriceBatch.Kind.VALUE, BigDecimal.ZERO)));
        slots.set(0, new PriceBatch.Slot(PriceBatch.Kind.VALUE, new BigDecimal(first)));
        slots.set(1, new PriceBatch.Slot(PriceBatch.Kind.VALUE, BigDecimal.valueOf(200)));
        if (gap != null) slots.set(3, new PriceBatch.Slot(gap, null));
        prices.save(new PriceSource.Fetch(new PriceBatch(PriceDay.Region.NSW1, DAY, slots), at, PriceBatch.hash(first), "test"));
    }

    HttpResponse<String> call(String method, String path, String body) throws Exception {
        return request(method, path, body, "application/json", true);
    }

    HttpResponse<String> request(String method, String path, String body, String contentType, boolean capture) throws Exception {
        try (var client = HttpClient.newHttpClient()) {
            var builder = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + path)).header("Content-Type", contentType);
            var response = client.send(builder.method(method, body == null ? HttpRequest.BodyPublishers.noBody() : HttpRequest.BodyPublishers.ofString(body)).build(), HttpResponse.BodyHandlers.ofString());
            if (capture) {
                ContractCapture.record(method, path, response);
                assertEquals("no-store", response.headers().firstValue("Cache-Control").orElseThrow());
                assertTrue(response.headers().allValues("Set-Cookie").isEmpty());
            }
            return response;
        }
    }

    static JsonNode json(HttpResponse<String> response) { return JSON.readTree(response.body()); }
}
