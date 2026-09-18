package au.nemlab.infrastructure.prices;

import au.nemlab.batterylab.PriceDay;
import org.postgresql.ds.PGSimpleDataSource;
import java.time.*;
import java.util.*;

/**
 * Explicit local operator tool; never loads .env implicitly or prints
 * credentials.
 */
public final class PriceImportCommand {
    public static void main(String[] args) {
        try {
            run(args);
        } catch (Exception ex) {
            System.err.println("Price command failed: " + ex.getClass().getSimpleName()
                    + " (details omitted; check inputs, database and OE access)");
            System.exit(1);
        }
    }

    private static void run(String[] args) {
        if (args.length == 0)
            throw new IllegalArgumentException();
        var ds = new PGSimpleDataSource();
        ds.setURL(required("NEMLAB_DB_URL"));
        ds.setUser(required("NEMLAB_DB_USER"));
        ds.setPassword(required("NEMLAB_DB_PASSWORD"));
        ds.setConnectTimeout(10);
        ds.setSocketTimeout(30);
        var store = new PriceStore(ds);
        switch (args[0]) {
            case "migrate" -> {
                PriceStore.migrate(ds);
                System.out.println("Price schema migrated");
            }
            case "start" -> {
                UUID id = store.createBackfill(PriceDay.Region.valueOf(args[1]), LocalDate.parse(args[2]),
                        LocalDate.parse(args[3]), Clock.systemUTC());
                System.out.println("Created backfill " + id);
            }
            case "resume" -> {
                UUID id = UUID.fromString(args[1]);
                var runner = new PriceBackfill(store, new OePriceSource(required("OPEN_ELECTRICITY_API_KEY")),
                        Clock.systemUTC());
                for (int i = 0; i < 31 && runner.step(id); i++) {
                }
                var b = store.backfill(id);
                System.out.println("Backfill " + id + " status=" + b.status() + " next=" + b.next() + " diagnostic="
                        + b.diagnostic());
                if (!b.status().equals("COMPLETE"))
                    throw new IllegalStateException();
            }
            case "status" -> System.out.println(store.backfill(UUID.fromString(args[1])));
            case "history" ->
                store.history(PriceDay.Region.valueOf(args[1]), LocalDate.parse(args[2])).forEach(System.out::println);
            case "coverage" ->
                System.out.println(store.coverage(PriceDay.Region.valueOf(args[1]), LocalDate.parse(args[2])));
            default -> throw new IllegalArgumentException();
        }
    }

    private static String required(String name) {
        String value = System.getenv(name);
        if (value == null || value.isBlank())
            throw new IllegalArgumentException(name + " required");
        return value;
    }
}
