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
        try {
            FetchOutcome outcome = fetcher.fetch(job);
            if (outcome.fetch() != null) {
                jobs.complete(job.id(), job.claimToken(), outcome.fetch());
            } else if (outcome.retryable()) {
                jobs.fail(job.id(), job.claimToken(), outcome.failure());
            } else {
                jobs.failPermanently(job.id(), job.claimToken(), outcome.failure());
            }
            LOG.info("Refresh attempt finished: job={}", job.id());
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
