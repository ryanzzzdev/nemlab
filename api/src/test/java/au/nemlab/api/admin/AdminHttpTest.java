package au.nemlab.api.admin;

import au.nemlab.api.ContractCapture;
import au.nemlab.batterylab.PriceDay;
import au.nemlab.infrastructure.jobs.RefreshJobService;
import au.nemlab.infrastructure.prices.PriceStore;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.postgresql.ds.PGSimpleDataSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.mock.env.MockEnvironment;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.postgresql.PostgreSQLContainer;
import tools.jackson.databind.json.JsonMapper;

import javax.sql.DataSource;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.LocalDate;
import java.util.Map;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        properties = {"nemlab.admin.enabled=true", "nemlab.data.enabled=true", "NEMLAB_ADMIN_OPERATOR=alice",
                "NEMLAB_ADMIN_TOKEN=abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG"})
class AdminHttpTest {
    private static final String TOKEN = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG";
    private static final String BASE = "/api/admin/v1/price-refreshes";
    private static final String BODY = "{\"region\":\"NSW1\",\"day\":\"2023-09-11\"}";
    private static final JsonMapper JSON = new JsonMapper();
    private static final PostgreSQLContainer POSTGRES = startDatabase();

    @LocalServerPort
    int port;

    @Autowired
    DataSource dataSource;

    @Autowired
    RefreshJobService jobs;

    JdbcTemplate jdbc;

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
    static void stopDatabase() {
        POSTGRES.stop();
    }

    @BeforeEach
    void reset() {
        jdbc = new JdbcTemplate(dataSource);
        jdbc.execute("""
                TRUNCATE refresh_job_event, refresh_request, refresh_job,
                    price_snapshot, price_current, price_import_attempt, price_revision, price_backfill
                """);
    }

    @Test
    void unauthorisedRequestsCannotReadOrMutateJobs() throws Exception {
        assertEquals(401, send("POST", BASE, null, "request", BODY).statusCode());
        assertEquals(401, send("POST", BASE, "Bearer wrong", "request", BODY).statusCode());
        assertEquals(401, send("GET", BASE, "Basic dXNlcjpwYXNz", null, null).statusCode());
        assertEquals(401, send("GET", BASE + "?access_token=" + TOKEN, null, null, null).statusCode());
        assertEquals(401, send("POST", BASE + "/" + UUID.randomUUID() + "/cancel",
                null, null, "").statusCode());
        assertEquals(0, jdbc.queryForObject("SELECT count(*) FROM refresh_job", Integer.class));
        assertEquals(0, jdbc.queryForObject("SELECT count(*) FROM refresh_job_event", Integer.class));
    }

    @Test
    void submissionIsIdempotentAndAuditActorComesFromAuthentication() throws Exception {
        var first = send("POST", BASE, "Bearer " + TOKEN, "request-1", BODY);
        assertEquals(202, first.statusCode());
        assertTrue(first.headers().firstValue("Set-Cookie").isEmpty());
        String id = payload(first).get("id").toString();
        assertEquals(BASE + "/" + id, first.headers().firstValue("Location").orElseThrow());
        assertEquals("QUEUED", payload(first).get("status"));
        assertEquals(id, payload(send("POST", BASE, "Bearer " + TOKEN, "request-1", BODY)).get("id"));
        assertEquals(id, payload(send("POST", BASE, "Bearer " + TOKEN, "request-2", BODY)).get("id"));
        var status = send("GET", BASE + "/" + id, "Bearer " + TOKEN, null, null);
        assertEquals(200, status.statusCode());
        assertFalse(status.body().contains("claimToken"));
        assertFalse(status.body().contains("backfillId"));
        assertFalse(status.body().contains(TOKEN));
        assertEquals(1, jdbc.queryForObject("SELECT count(*) FROM refresh_job", Integer.class));
        assertEquals(3, jdbc.queryForObject(
                "SELECT count(*) FROM refresh_job_event WHERE actor = 'operator:alice'", Integer.class));
        assertEquals(0, jdbc.queryForObject(
                "SELECT count(*) FROM refresh_job_event WHERE actor = 'spoofed'", Integer.class));
        assertTrue(send("GET", BASE + "/" + id + "/events", "Bearer " + TOKEN, null, null)
                .body().contains("operator:alice"));
        assertEquals(200, send("GET", BASE + "?limit=1", "Bearer " + TOKEN, null, null).statusCode());
    }

    @Test
    void rejectsInvalidBodiesAndConflictingRequestKeysWithoutLeakingInputs() throws Exception {
        assertEquals(400, send("POST", BASE, "Bearer " + TOKEN, null, BODY).statusCode());
        for (String invalid : new String[] {
                "{}", "{", BODY.replace("NSW1", "BOGUS"), BODY.replace("2023-09-11", "2200-01-01"),
                BODY.replace("2023-09-11", "2020-01-01"),
                "{\"region\":\"NSW1\",\"day\":\"2023-09-11\",\"actor\":\"spoofed\"}"}) {
            var response = send("POST", BASE, "Bearer " + TOKEN, "invalid", invalid);
            assertEquals(400, response.statusCode(), response.body());
            assertFalse(response.body().contains("spoofed"));
        }
        assertEquals(0, jdbc.queryForObject("SELECT count(*) FROM refresh_job", Integer.class));
        assertEquals(202, send("POST", BASE, "Bearer " + TOKEN, "fixed", BODY).statusCode());
        var conflict = send("POST", BASE, "Bearer " + TOKEN, "fixed", BODY.replace("2023-09-11", "2023-09-12"));
        assertEquals(409, conflict.statusCode());
        assertEquals("IDEMPOTENCY_CONFLICT", payload(conflict).get("code"));
    }

    @Test
    void cancellationIsAuditedIdempotentAndRevokesRunningClaim() throws Exception {
        UUID id = UUID.fromString(payload(send("POST", BASE, "Bearer " + TOKEN, "request", BODY))
                .get("id").toString());
        var claim = jobs.claim().orElseThrow();
        var cancelled = send("POST", BASE + "/" + id + "/cancel", "Bearer " + TOKEN, null, "");
        assertEquals(200, cancelled.statusCode());
        assertEquals("CANCELLED", payload(cancelled).get("status"));
        assertEquals(200, send("POST", BASE + "/" + id + "/cancel", "Bearer " + TOKEN, null, "").statusCode());
        assertThrows(RefreshJobService.StaleClaimException.class,
                () -> jobs.fail(id, claim.claimToken(), "STALE_WORKER"));
        var events = send("GET", BASE + "/" + id + "/events", "Bearer " + TOKEN, null, null);
        assertTrue(events.body().contains("CANCELLED"));
        assertTrue(events.body().contains("CANCEL_NOOP"));
        assertEquals(2, jdbc.queryForObject("""
                SELECT count(*) FROM refresh_job_event
                WHERE job_id = ? AND actor = 'operator:alice' AND action LIKE 'CANCEL%'
                """, Integer.class, id));
        long finalEvent = jdbc.queryForObject("SELECT max(id) FROM refresh_job_event", Long.class);
        assertEquals("[]", send("GET", BASE + "/" + id + "/events?after=" + finalEvent,
                "Bearer " + TOKEN, null, null).body());
    }

    @Test
    void invalidIdsAndBoundsHaveExplicitResponses() throws Exception {
        assertEquals(400, send("GET", BASE + "/not-a-uuid", "Bearer " + TOKEN, null, null).statusCode());
        assertEquals(404, send("GET", BASE + "/" + UUID.randomUUID(), "Bearer " + TOKEN, null, null).statusCode());
        assertEquals(404, send("POST", BASE + "/" + UUID.randomUUID() + "/cancel",
                "Bearer " + TOKEN, null, "").statusCode());
        assertEquals(400, send("GET", BASE + "?limit=101", "Bearer " + TOKEN, null, null).statusCode());
        assertEquals(400, send("GET", BASE + "?limit=0", "Bearer " + TOKEN, null, null).statusCode());
    }

    @Test
    void queueCapacityProducesBackpressure() throws Exception {
        for (int day = 0; day < 100; day++) {
            jobs.submit("fill-" + day, PriceDay.Region.NSW1, LocalDate.of(2023, 1, 1).plusDays(day), "test");
        }
        var response = send("POST", BASE, "Bearer " + TOKEN, "overflow", BODY);
        assertEquals(429, response.statusCode());
        assertEquals("30", response.headers().firstValue("Retry-After").orElseThrow());
        assertEquals("QUEUE_FULL", payload(response).get("code"));
    }

    @Test
    void storageFailureReturnsSafeErrorWithoutSqlOrCredentials() throws Exception {
        jdbc.execute("ALTER TABLE refresh_job RENAME TO temporarily_missing_refresh_job");
        try {
            var response = send("GET", BASE, "Bearer " + TOKEN, null, null);
            assertEquals(503, response.statusCode());
            assertEquals("STORAGE_UNAVAILABLE", payload(response).get("code"));
            assertFalse(response.body().contains("SELECT"));
            assertFalse(response.body().contains(POSTGRES.getJdbcUrl()));
        } finally {
            jdbc.execute("ALTER TABLE temporarily_missing_refresh_job RENAME TO refresh_job");
        }
        var source = (PGSimpleDataSource) dataSource;
        source.setURL("jdbc:postgresql://127.0.0.1:1/unavailable");
        try {
            var response = send("GET", BASE, "Bearer " + TOKEN, null, null);
            assertEquals(503, response.statusCode());
            assertEquals("STORAGE_UNAVAILABLE", payload(response).get("code"));
        } finally {
            source.setURL(POSTGRES.getJdbcUrl());
        }
    }

    @Test
    void tokenConfigurationFailsClosed() {
        var configuration = new AdminConfiguration();
        assertThrows(IllegalArgumentException.class,
                () -> configuration.operatorTokens(new MockEnvironment()));
        assertThrows(IllegalArgumentException.class, () -> configuration.operatorTokens(new MockEnvironment()
                .withProperty("NEMLAB_ADMIN_OPERATOR", "alice").withProperty("NEMLAB_ADMIN_TOKEN", "short")));
        new ApplicationContextRunner().withUserConfiguration(AdminConfiguration.class)
                .withPropertyValues("nemlab.admin.enabled=true")
                .run(application -> assertNotNull(application.getStartupFailure()));
    }

    private HttpResponse<String> send(String method, String path, String authorization, String key, String body)
            throws Exception {
        var builder = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + path))
                .header("X-Actor", "spoofed")
                .header("Content-Type", "application/json");
        if (authorization != null) {
            builder.header("Authorization", authorization);
        }
        if (key != null) {
            builder.header("Idempotency-Key", key);
        }
        builder.method(method, body == null ? HttpRequest.BodyPublishers.noBody()
                : HttpRequest.BodyPublishers.ofString(body));
        try (var client = HttpClient.newHttpClient()) {
            var response = client.send(builder.build(), HttpResponse.BodyHandlers.ofString());
            if (path.startsWith("/api/admin/v1/")) {
                ContractCapture.record(method, path, response);
            }
            return response;
        }
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> payload(HttpResponse<String> response) {
        return JSON.readValue(response.body(), Map.class);
    }
}
