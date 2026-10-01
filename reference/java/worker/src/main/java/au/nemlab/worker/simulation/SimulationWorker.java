package au.nemlab.worker.simulation;

import au.nemlab.infrastructure.batterylab.SimulationJobs;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.SmartLifecycle;
import java.time.Duration;
import java.util.concurrent.*;

public final class SimulationWorker implements SmartLifecycle {
    private static final Logger LOG = LoggerFactory.getLogger(SimulationWorker.class);
    private final SimulationJobs jobs;
    private final SimulationProcess process;
    private final Duration interval;
    private final ScheduledExecutorService executor = Executors.newSingleThreadScheduledExecutor(
            Thread.ofPlatform().name("simulation-worker").factory());
    private volatile boolean running;

    public SimulationWorker(SimulationJobs jobs, SimulationProcess process, Duration interval) {
        this.jobs = jobs;
        this.process = process;
        this.interval = interval;
    }

    @Override
    public synchronized void start() {
        if (running) return;
        running = true;
        LOG.info("Simulation polling started ({} ms interval)", interval.toMillis());
        executor.scheduleWithFixedDelay(this::tick, 0, interval.toMillis(), TimeUnit.MILLISECONDS);
    }

    private void tick() {
        if (!running) return;
        try {
            jobs.claim().ifPresent(this::execute);
        } catch (SimulationProcess.TerminationFailure fatal) {
            running = false;
            executor.shutdownNow();
            LOG.error("Simulation process could not terminate; polling stopped");
        } catch (RuntimeException failure) {
            LOG.warn("Simulation queue operation failed; lease recovery remains available (details omitted)");
        }
    }

    private void execute(SimulationJobs.Job job) {
        LOG.info("Claimed simulation job {}; running comparison in child process", job.id());
        try {
            var outcome = process.execute(jobs.input(job.id()));
            if (outcome.result() != null) {
                jobs.complete(job.id(), job.token(), outcome.result());
                LOG.info("Simulation job {} succeeded; comparison stored", job.id());
            } else {
                jobs.fail(job.id(), job.token(), outcome.failure(), outcome.retryable());
                LOG.info("Simulation job {} failed: {} (retryable={})",
                        job.id(), outcome.failure(), outcome.retryable());
            }
        } catch (SimulationJobs.StaleClaim ignored) {
            LOG.info("Discarded stale simulation result: job={}", job.id());
        } catch (InterruptedException stopped) {
            Thread.interrupted();
            try { jobs.fail(job.id(), job.token(), "WORKER_STOPPED", true); }
            finally { Thread.currentThread().interrupt(); }
        }
    }

    @Override
    public void stop() {
        running = false;
        executor.shutdownNow();
        process.close();
        try {
            if (!executor.awaitTermination(15, TimeUnit.SECONDS))
                LOG.warn("Simulation shutdown timed out; claim will expire");
        } catch (InterruptedException interrupted) { Thread.currentThread().interrupt(); }
    }

    @Override
    public boolean isRunning() { return running; }
}
