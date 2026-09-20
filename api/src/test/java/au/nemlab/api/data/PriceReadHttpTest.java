package au.nemlab.api.data;

import au.nemlab.api.ContractCapture;
import au.nemlab.batterylab.PriceDay;
import au.nemlab.infrastructure.prices.PriceBatch;
import au.nemlab.infrastructure.prices.PriceSource;
import au.nemlab.infrastructure.prices.PriceStore;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
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
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Instant;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Collections;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        properties = {"nemlab.data.enabled=true", "nemlab.admin.enabled=false"})
class PriceReadHttpTest {
    private static final LocalDate DAY = LocalDate.of(2023, 10, 1);
    private static final Instant RETRIEVED = Instant.parse("2026-09-18T00:00:00Z");
    private static final PostgreSQLContainer POSTGRES = startDatabase();
    private static final JsonMapper JSON = new JsonMapper();

    @LocalServerPort
    int port;

    @Autowired
    PriceStore prices;

    @Autowired
    DataSource source;

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry properties) {
        properties.add("NEMLAB_DB_URL", POSTGRES::getJdbcUrl);
        properties.add("NEMLAB_DB_USER", POSTGRES::getUsername);
        properties.add("NEMLAB_DB_PASSWORD", POSTGRES::getPassword);
    }

    private static PostgreSQLContainer startDatabase() {
        var database = new PostgreSQLContainer("postgres:18.6-alpine");
        database.start();
        var source = new PGSimpleDataSource();
        source.setURL(database.getJdbcUrl());
        source.setUser(database.getUsername());
        source.setPassword(database.getPassword());
        PriceStore.migrate(source);
        return database;
    }

    @AfterAll
    static void stop() {
        POSTGRES.stop();
    }

    @BeforeEach
    void reset() {
        new JdbcTemplate(source).execute("""
                TRUNCATE simulation_result, simulation_job, simulation_input, refresh_job_event, refresh_request, refresh_job,
                    price_snapshot, price_current, price_import_attempt, price_revision, price_backfill
                """);
    }

    @Test
    void coverageIncludesCompleteIncompleteAndUnimportedDays() throws Exception {
        save(DAY, false, "42.5", RETRIEVED);
        save(DAY.plusDays(1), true, "42.5", RETRIEVED);
        var response = request("GET", "/api/v1/prices/NSW1/coverage?start=2023-10-01&endExclusive=2023-10-04");
        assertEquals(200, response.statusCode());
        JsonNode days = json(response).get("days");
        assertEquals(3, days.size());
        assertEquals("COMPLETE", days.get(0).get("availability").asString());
        assertEquals(288, days.get(0).get("valid").asInt());
        assertEquals("INCOMPLETE", days.get(1).get("availability").asString());
        assertEquals(286, days.get(1).get("valid").asInt());
        assertEquals(1, days.get(1).get("missing").asInt());
        assertEquals(1, days.get(1).get("sourceNull").asInt());
        assertEquals("NOT_IMPORTED", days.get(2).get("availability").asString());
        assertTrue(days.get(2).get("revision").isNull());
        assertTrue(days.get(2).get("missing").isNull());
    }

    @Test
    void seriesPreservesExactValuesStatesAndFixedNemTimeAcrossDst() throws Exception {
        save(DAY, true, "123.4567890123456789", RETRIEVED);
        var response = request("GET", "/api/v1/prices/NSW1/2023-10-01");
        assertEquals(200, response.statusCode());
        assertTrue(response.headers().firstValue("Cache-Control").orElseThrow().contains("no-store"));
        JsonNode body = json(response);
        assertEquals("AUD/MWh", body.get("unit").asString());
        assertEquals("+10:00", body.get("marketOffset").asString());
        assertEquals("END", body.get("intervalLabel").asString());
        assertEquals(300, body.get("intervalSeconds").asInt());
        JsonNode intervals = body.get("intervals");
        assertEquals(288, intervals.size());
        assertEquals("2023-09-30T14:00:00Z", intervals.get(0).get("start").asString());
        assertEquals("2023-10-01T14:00:00Z", intervals.get(287).get("end").asString());
        assertEquals("123.4567890123456789", intervals.get(0).get("price").asString());
        assertTrue(intervals.get(0).get("price").isString());
        assertEquals("-25", intervals.get(1).get("price").asString());
        assertEquals("0", intervals.get(2).get("price").asString());
        assertEquals("MISSING", intervals.get(3).get("state").asString());
        assertEquals("SOURCE_NULL", intervals.get(4).get("state").asString());
        assertTrue(intervals.get(3).get("price").isNull());
        assertTrue(intervals.get(4).get("price").isNull());
    }

    @Test
    void correctionsAdvanceCurrentRevisionButLeaveOldSnapshotIntact() throws Exception {
        save(DAY, false, "10", RETRIEVED);
        var old = prices.coverage(PriceDay.Region.NSW1, DAY).orElseThrow();
        var snapshot = prices.snapshot(old.revision());
        save(DAY, false, "99", RETRIEVED.plusSeconds(1));
        JsonNode result = json(request("GET", "/api/v1/prices/NSW1/2023-10-01"));
        assertNotEquals(old.revision().toString(), result.get("coverage").get("revision").asString());
        assertEquals("99", result.get("intervals").get(0).get("price").asString());
        assertEquals(0, new BigDecimal("10").compareTo(prices.snapshotPrices(snapshot).intervals().getFirst().price()));
    }

    @Test
    void missingSeriesReturns404AndDoesNotCreateAnyJobs() throws Exception {
        var response = request("GET", "/api/v1/prices/NSW1/2023-10-01");
        assertEquals(404, response.statusCode());
        assertEquals("PRICE_DAY_NOT_IMPORTED", json(response).get("code").asString());
        var jdbc = new JdbcTemplate(source);
        assertEquals(0, jdbc.queryForObject("SELECT count(*) FROM refresh_job", Integer.class));
        assertEquals(0, jdbc.queryForObject("SELECT count(*) FROM price_import_attempt", Integer.class));
        assertEquals(404, request("POST", "/api/v1/prices/NSW1/2023-10-01").statusCode());
        assertEquals(404, request("GET", "/api/admin/v1/price-refreshes").statusCode());
    }

    @Test
    void validatesRegionDatesAndRangeLimits() throws Exception {
        for (String path : new String[] {
                "/api/v1/prices/BOGUS/2023-10-01",
                "/api/v1/prices/NSW1/not-a-day",
                "/api/v1/prices/NSW1/2200-01-01",
                "/api/v1/prices/NSW1/2020-01-01",
                "/api/v1/prices/NSW1/coverage?start=2023-10-01",
                "/api/v1/prices/NSW1/coverage?start=2023-10-01&endExclusive=2023-10-01",
                "/api/v1/prices/NSW1/coverage?start=2023-10-01&endExclusive=2023-11-02"}) {
            var response = request("GET", path);
            assertEquals(400, response.statusCode(), path);
            assertEquals("INVALID_REQUEST", json(response).get("code").asString());
        }
        var maximum = request("GET", "/api/v1/prices/NSW1/coverage?start=2023-10-01&endExclusive=2023-11-01");
        assertEquals(31, json(maximum).get("days").size());
    }

    @Test
    void databaseFailureReturnsSafe503() throws Exception {
        var dataSource = (PGSimpleDataSource) source;
        dataSource.setURL("jdbc:postgresql://127.0.0.1:1/unavailable");
        try {
            var response = request("GET", "/api/v1/prices/NSW1/2023-10-01");
            assertEquals(503, response.statusCode());
            assertEquals("STORAGE_UNAVAILABLE", json(response).get("code").asString());
            assertFalse(response.body().contains("jdbc:"));
        } finally {
            dataSource.setURL(POSTGRES.getJdbcUrl());
        }
    }

    private void save(LocalDate day, boolean incomplete, String first, Instant retrieved) {
        var slots = new ArrayList<>(Collections.nCopies(288,
                new PriceBatch.Slot(PriceBatch.Kind.VALUE, new BigDecimal(first))));
        slots.set(1, new PriceBatch.Slot(PriceBatch.Kind.VALUE, new BigDecimal("-25")));
        slots.set(2, new PriceBatch.Slot(PriceBatch.Kind.VALUE, BigDecimal.ZERO));
        if (incomplete) {
            slots.set(3, new PriceBatch.Slot(PriceBatch.Kind.MISSING, null));
            slots.set(4, new PriceBatch.Slot(PriceBatch.Kind.SOURCE_NULL, null));
        }
        prices.save(new PriceSource.Fetch(new PriceBatch(PriceDay.Region.NSW1, day, slots), retrieved,
                PriceBatch.hash("fixture-" + first), "test-1"));
    }

    private HttpResponse<String> request(String method, String path) throws Exception {
        try (var client = HttpClient.newHttpClient()) {
            var request = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + path))
                    .method(method, HttpRequest.BodyPublishers.noBody()).build();
            var response = client.send(request, HttpResponse.BodyHandlers.ofString());
            if (method.equals("GET") && path.startsWith("/api/v1/prices/")) {
                ContractCapture.record(method, path, response);
            }
            return response;
        }
    }

    private static JsonNode json(HttpResponse<String> response) {
        return JSON.readTree(response.body());
    }
}
