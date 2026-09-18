package au.nemlab.infrastructure.prices;

import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.List;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.*;

class PriceImportCommandTest {
    @Test
    void retiredCommandsCannotReachDatabaseOrOe() throws Exception {
        String java = Path.of(System.getProperty("java.home"), "bin", "java").toString();
        for (String command : List.of("start", "resume")) {
            ProcessBuilder builder = new ProcessBuilder(java, "-cp",
                    System.getProperty("infrastructure.test.classpath"), PriceImportCommand.class.getName(), command);
            builder.environment().clear();
            builder.redirectErrorStream(true);
            Process process = builder.start();
            try {
                assertTrue(process.waitFor(5, TimeUnit.SECONDS));
                assertEquals(2, process.exitValue());
                String output = new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
                assertTrue(output.contains("Direct ingestion is retired"));
                assertFalse(output.contains("NEMLAB_DB"));
            } finally {
                if (process.isAlive()) {
                    process.destroyForcibly();
                    assertTrue(process.waitFor(5, TimeUnit.SECONDS));
                }
            }
        }
    }
}
