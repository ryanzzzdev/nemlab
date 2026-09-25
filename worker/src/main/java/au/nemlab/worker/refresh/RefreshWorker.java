package au.nemlab.worker.refresh;

import au.nemlab.infrastructure.jobs.RefreshJob;
import au.nemlab.infrastructure.jobs.RefreshJobService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.SmartLifecycle;

import java.time.Duration;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

public final class RefreshWorker implements SmartLifecycle {
    private static final Logger LOG = LoggerFactory.getLogger(RefreshWorker.class);

    private final RefreshJobService jobs;
    private final RefreshSchedule schedule;
    private final PriceFetchProcess fetcher;
    private final Duration pollInterval;
    private final ScheduledExecutorService executor;
    private volatile boolean running;

    public RefreshWorker(RefreshJobService jobs, RefreshSchedule schedule,
            PriceFetchProcess fetcher, Duration pollInterval) {
        this.jobs = jobs;
        this.schedule = schedule;
        this.fetcher = fetcher;
        this.pollInterval = pollInterval;
        this.executor = Executors.newSingleThreadScheduledExecutor(
                Thread.ofPlatform().name("price-refresh-worker").factory());
    }

    @Override
    public synchronized void start() {
        if (running) {
            return;
        }
        running = true;
        LOG.info("Price refresh polling started ({} ms interval)", pollInterval.toMillis());
        executor.scheduleWithFixedDelay(this::tick, 0, pollInterval.toMillis(), TimeUnit.MILLISECONDS);
    }

    void tick() {
        if (!running) {
            return;
        }
        try {
            schedule.submitDue();
        } catch (RuntimeException failure) {
            LOG.warn("Scheduled submission failed; retrying on next poll (details omitted)");
        }
        if (!running) {
            return;
        }
        try {
            jobs.claim().ifPresent(this::execute);
        } catch (PriceFetchProcess.TerminationFailure failure) {
            running = false;
            executor.shutdownNow();
            LOG.error("Worker stopped: fetch process could not be terminated; operator intervention required");
        } catch (RuntimeException failure) {
            LOG.warn("Queue operation failed; lease recovery remains available (details omitted)");
        }
    }

    private void execute(RefreshJob job) {
        LOG.info("Claimed refresh job {} ({} {}, attempt {}); fetching OE prices",
                job.id(), job.region(), job.day(), job.attempts());
        long started = System.nanoTime();
        try {
            FetchOutcome outcome = fetcher.fetch(job);
            long elapsed = (System.nanoTime() - started) / 1_000_000;
            if (outcome.fetch() != null) {
                jobs.complete(job.id(), job.claimToken(), outcome.fetch());
                LOG.info("Refresh job {} committed stored prices for {} {} ({} ms)",
                        job.id(), job.region(), job.day(), elapsed);
            } else if (outcome.retryable()) {
                jobs.fail(job.id(), job.claimToken(), outcome.failure());
                LOG.info("Refresh job {} failed: {}; bounded retry scheduled ({} ms)",
                        job.id(), outcome.failure(), elapsed);
            } else {
                jobs.failPermanently(job.id(), job.claimToken(), outcome.failure());
                LOG.info("Refresh job {} failed permanently: {} ({} ms)",
                        job.id(), outcome.failure(), elapsed);
            }
        } catch (RefreshJobService.StaleClaimException ignored) {
            LOG.info("Discarded stale refresh result: job={}", job.id());
        } catch (InterruptedException stopped) {
            // Clear interruption briefly so the transaction can release the claim.
            Thread.interrupted();
            try {
                jobs.fail(job.id(), job.claimToken(), "WORKER_STOPPED");
            } finally {
                Thread.currentThread().interrupt();
            }
        }
    }

    @Override
    public void stop() {
        running = false;
        executor.shutdownNow();
        fetcher.close();
        try {
            if (!executor.awaitTermination(15, TimeUnit.SECONDS)) {
                LOG.warn("Worker shutdown timed out; unfinished claim will expire");
            }
        } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
        }
    }

    @Override
    public boolean isRunning() {
        return running;
    }
}
