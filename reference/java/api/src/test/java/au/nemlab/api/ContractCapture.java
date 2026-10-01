package au.nemlab.api;

import tools.jackson.databind.json.JsonMapper;

import java.io.IOException;
import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import java.util.UUID;

/** Captures test responses only: never request bodies, credentials or query strings. */
public final class ContractCapture {
    private static final JsonMapper JSON = new JsonMapper();

    private ContractCapture() {
    }

    public static void record(String method, String path, HttpResponse<String> response) throws IOException {
        String directory = System.getProperty("nemlab.contract.captures");
        if (directory == null) {
            return; // IDE tests do not require the Node toolchain.
        }
        var target = Path.of(directory);
        Files.createDirectories(target);
        var capture = Map.of(
                "method", method.toLowerCase(),
                "path", path.split("\\?", 2)[0],
                "status", response.statusCode(),
                "headers", response.headers().map(),
                "body", response.body());
        Files.writeString(target.resolve(UUID.randomUUID() + ".json"), JSON.writeValueAsString(capture));
    }
}
