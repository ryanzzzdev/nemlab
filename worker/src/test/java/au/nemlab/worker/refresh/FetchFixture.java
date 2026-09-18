package au.nemlab.worker.refresh;

import au.nemlab.batterylab.PriceDay;
import au.nemlab.infrastructure.prices.PriceBatch;
import au.nemlab.infrastructure.prices.PriceSource;
import tools.jackson.databind.json.JsonMapper;

import java.math.BigDecimal;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.time.LocalDate;
import java.util.Collections;

/** Real child-process fixture: no live OE traffic. */
public final class FetchFixture {
    public static void main(String[] arguments) throws Exception {
        String scenario = arguments[0];
        Path marker = Path.of(arguments[1]);
        Path output = Path.of(arguments[5]);
        Files.writeString(marker, ProcessHandle.current().pid() + "\n" + output);
        if (System.getenv("NEMLAB_DB_PASSWORD") != null) {
            throw new IllegalStateException("Database secret inherited by child");
        }
        if (scenario.equals("hang")) {
            Thread.sleep(60_000);
            return;
        }
        if (scenario.equals("crash")) {
            System.exit(7);
        }
        if (scenario.equals("malformed")) {
            Files.writeString(output, "not-json");
            return;
        }
        FetchOutcome result;
        if (scenario.equals("unauthorised")) {
            result = FetchOutcome.failure("HTTP_401", false);
        } else {
            var slots = Collections.nCopies(288,
                    new PriceBatch.Slot(PriceBatch.Kind.VALUE, new BigDecimal("42.5")));
            var batch = new PriceBatch(PriceDay.Region.valueOf(arguments[3]),
                    LocalDate.parse(arguments[4]), slots);
            result = FetchOutcome.success(new PriceSource.Fetch(batch, Instant.now(),
                    PriceBatch.hash("worker-fixture"), "fixture-1"));
        }
        Files.writeString(output, new JsonMapper().writeValueAsString(result));
    }
}
