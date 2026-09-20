package au.nemlab.worker.refresh;

import au.nemlab.batterylab.PriceDay;
import au.nemlab.infrastructure.jobs.RefreshJobConfiguration;
import au.nemlab.infrastructure.jobs.RefreshJobService;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.core.env.Environment;

import java.time.Clock;
import java.time.Duration;
import java.util.Arrays;
import java.util.List;

@Configuration(proxyBeanMethods = false)
@ConditionalOnProperty(name = "nemlab.worker.enabled", havingValue = "true")
@Import({RefreshJobConfiguration.class, au.nemlab.worker.WorkerDatabaseConfiguration.class})
public class WorkerRefreshConfiguration {

    @Bean
    public PriceFetchProcess priceFetchProcess(Environment environment) {
        String key = required(environment, "OPEN_ELECTRICITY_API_KEY");
        if (key.contains("\n") || key.contains("\r")) {
            throw new IllegalArgumentException("Invalid OE credential configuration");
        }
        return new PriceFetchProcess(key);
    }

    @Bean
    public RefreshSchedule refreshSchedule(RefreshJobService jobs, Environment environment) {
        List<PriceDay.Region> regions = List.of();
        if (environment.getProperty("nemlab.worker.schedule-enabled", Boolean.class, false)) {
            String configured = required(environment, "nemlab.worker.regions");
            regions = Arrays.stream(configured.split(",", -1))
                    .map(String::trim)
                    .map(PriceDay.Region::valueOf)
                    .distinct()
                    .toList();
        }
        return new RefreshSchedule(jobs, Clock.systemUTC(), regions);
    }

    @Bean
    public RefreshWorker refreshWorker(RefreshJobService jobs, RefreshSchedule schedule,
            PriceFetchProcess fetcher, Environment environment) {
        long pollMillis = environment.getProperty("nemlab.worker.poll-ms", Long.class, 5000L);
        if (pollMillis < 1000 || pollMillis > 60_000) {
            throw new IllegalArgumentException("Worker poll interval must be between 1000 and 60000 ms");
        }
        return new RefreshWorker(jobs, schedule, fetcher, Duration.ofMillis(pollMillis));
    }

    private static String required(Environment environment, String name) {
        String value = environment.getProperty(name);
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(name + " is required when the worker is enabled");
        }
        return value;
    }
}
