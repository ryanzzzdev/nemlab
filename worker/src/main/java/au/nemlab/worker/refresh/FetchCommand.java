package au.nemlab.worker.refresh;

import au.nemlab.batterylab.PriceDay;
import au.nemlab.infrastructure.prices.OePriceSource;
import tools.jackson.databind.json.JsonMapper;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;

/** Child mode: no Spring context, database credentials or database writes. */
public final class FetchCommand {
    public static final String MODE = "--fetch-price";
    public static final int TIMEOUT_SECONDS = 240;

    private FetchCommand() {
    }

    public static int run(String[] arguments) {
        if (arguments.length != 4) {
            return 2;
        }
        startWatchdog();
        FetchOutcome result;
        try {
            PriceDay.Region region = PriceDay.Region.valueOf(arguments[1]);
            LocalDate day = LocalDate.parse(arguments[2]);
            var source = new OePriceSource(System.getenv("OPEN_ELECTRICITY_API_KEY"));
            result = FetchOutcome.success(source.fetch(region, day));
        } catch (OePriceSource.Failure failure) {
            String code = failure.code();
            boolean retryable = (!code.startsWith("HTTP_4") || code.equals("HTTP_429"))
                    && !code.equals("RETRY_AFTER_EXCEEDS_BUDGET");
            result = FetchOutcome.failure(code, retryable);
        } catch (IllegalArgumentException failure) {
            result = FetchOutcome.failure("INVALID_SOURCE_DATA_OR_CONFIGURATION", false);
        } catch (InterruptedException failure) {
            Thread.currentThread().interrupt();
            result = FetchOutcome.failure("FETCH_INTERRUPTED", true);
        } catch (Exception failure) {
            result = FetchOutcome.failure("FETCH_FAILED", true);
        }
        try {
            Files.writeString(Path.of(arguments[3]), new JsonMapper().writeValueAsString(result));
            return 0;
        } catch (Exception failure) {
            return 3;
        }
    }

    private static void startWatchdog() {
        Thread.ofPlatform().daemon().name("fetch-deadline").start(() -> {
            try {
                Thread.sleep(TIMEOUT_SECONDS * 1000L);
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            }
            // Also bounds orphaned children if the worker parent crashes.
            Runtime.getRuntime().halt(124);
        });
    }
}
