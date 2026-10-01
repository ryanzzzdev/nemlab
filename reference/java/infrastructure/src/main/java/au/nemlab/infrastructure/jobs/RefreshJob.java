package au.nemlab.infrastructure.jobs;

import au.nemlab.batterylab.PriceDay;

import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;

/** A persisted operational job, separate from battery-domain models. */
public record RefreshJob(
        UUID id,
        UUID backfillId,
        PriceDay.Region region,
        LocalDate day,
        Status status,
        int attempts,
        UUID claimToken,
        Instant leaseUntil,
        Instant availableAt,
        String diagnostic) {

    public enum Status {
        QUEUED, RUNNING, SUCCEEDED, FAILED, CANCELLED
    }
}
