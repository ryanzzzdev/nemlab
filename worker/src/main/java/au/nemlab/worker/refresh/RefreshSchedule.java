package au.nemlab.worker.refresh;

import au.nemlab.batterylab.PriceDay;
import au.nemlab.infrastructure.jobs.RefreshJobService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Clock;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/** Once per region/day, with persistent keys protecting restarts and multiple workers. */
public final class RefreshSchedule {
    private static final Logger LOG = LoggerFactory.getLogger(RefreshSchedule.class);

    private final RefreshJobService jobs;
    private final Clock clock;
    private final List<PriceDay.Region> regions;
    private final Map<PriceDay.Region, LocalDate> submitted = new EnumMap<>(PriceDay.Region.class);

    public RefreshSchedule(RefreshJobService jobs, Clock clock, List<PriceDay.Region> regions) {
        this.jobs = jobs;
        this.clock = clock;
        this.regions = List.copyOf(regions);
    }

    public void submitDue() {
        LocalDate day = LocalDateTime.now(clock.withZone(PriceDay.NEM_OFFSET))
                .minusMinutes(15).toLocalDate().minusDays(1);
        for (PriceDay.Region region : regions) {
            if (!day.equals(submitted.get(region))) {
                UUID job = jobs.submit("daily-price-v1:" + region + ":" + day, region, day, "scheduler");
                LOG.info("Scheduled daily price refresh {} {} -> job {}", region, day, job);
                submitted.put(region, day);
            }
        }
    }
}
