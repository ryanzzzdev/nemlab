package au.nemlab.infrastructure.prices;

import au.nemlab.batterylab.PriceDay;
import java.time.*;

@FunctionalInterface
public interface PriceSource {
    record Fetch(PriceBatch batch, Instant retrievedAt, String responseHash, String sourceVersion) {
        public Fetch {
            java.util.Objects.requireNonNull(batch);
            java.util.Objects.requireNonNull(retrievedAt);
            if (responseHash == null || !responseHash.matches("[0-9a-f]{64}"))
                throw new IllegalArgumentException("response hash required");
            if (sourceVersion == null || !sourceVersion.matches("[A-Za-z0-9._+-]{1,80}"))
                throw new IllegalArgumentException("invalid source version");
        }
    }

    Fetch fetch(PriceDay.Region region, LocalDate day) throws Exception;
}
