package au.nemlab.api;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import java.net.URI;
import java.net.http.*;
import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class ApiApplicationTest {
    @LocalServerPort
    int port;

    @Test
    void simulationRoutesAreDisabledByDefault() throws Exception {
        try (var client = HttpClient.newHttpClient()) {
            String base = "http://127.0.0.1:" + port + "/api/v1/simulations";
            var post = client.send(HttpRequest.newBuilder(URI.create(base))
                    .header("Content-Type", "application/json").POST(HttpRequest.BodyPublishers.ofString("{}")).build(),
                    HttpResponse.BodyHandlers.ofString());
            assertEquals(404, post.statusCode());
            for (String suffix : new String[] { "/00000000-0000-0000-0000-000000000000", "/00000000-0000-0000-0000-000000000000/result" }) {
                var get = client.send(HttpRequest.newBuilder(URI.create(base + suffix)).build(), HttpResponse.BodyHandlers.ofString());
                assertEquals(404, get.statusCode());
            }
        }
    }

    @Test
    void healthIsAvailableButInternalConfigurationIsNotExposed() throws Exception {
        try (var client = HttpClient.newHttpClient()) {
            var health = client.send(
                    HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + "/actuator/health")).build(),
                    HttpResponse.BodyHandlers.ofString());
            assertEquals(200, health.statusCode());
            var payload = new tools.jackson.databind.json.JsonMapper().readValue(health.body(), java.util.Map.class);
            assertEquals("UP", payload.get("status"));
            assertFalse(payload.containsKey("components"));
            assertFalse(payload.containsKey("details"));
            var environment = client.send(
                    HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + "/actuator/env")).build(),
                    HttpResponse.BodyHandlers.ofString());
            assertEquals(404, environment.statusCode());
            var admin = client.send(
                    HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port
                            + "/api/admin/v1/price-refreshes")).build(),
                    HttpResponse.BodyHandlers.ofString());
            assertEquals(404, admin.statusCode());
            var prices = client.send(
                    HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port
                            + "/api/v1/prices/NSW1/2023-10-01")).build(),
                    HttpResponse.BodyHandlers.ofString());
            assertEquals(404, prices.statusCode());
        }
    }
}
