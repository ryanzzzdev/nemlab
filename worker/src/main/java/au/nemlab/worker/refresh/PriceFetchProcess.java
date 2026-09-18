package au.nemlab.worker.refresh;

import au.nemlab.infrastructure.jobs.RefreshJob;
import tools.jackson.databind.json.JsonMapper;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/** One owned child at a time; termination precedes result publication or retry. */
public final class PriceFetchProcess implements AutoCloseable {
    private final List<String> command;
    private final Map<String, String> environment;
    private final Duration timeout;
    private Process active;
    private boolean closed;

    public PriceFetchProcess(String apiKey) {
        this(defaultCommand(), Map.of("OPEN_ELECTRICITY_API_KEY", apiKey),
                Duration.ofSeconds(FetchCommand.TIMEOUT_SECONDS));
    }

    PriceFetchProcess(List<String> command, Map<String, String> environment, Duration timeout) {
        this.command = List.copyOf(command);
        this.environment = Map.copyOf(environment);
        this.timeout = timeout;
    }

    public FetchOutcome fetch(RefreshJob job) throws InterruptedException {
        Path output = null;
        Process process = null;
        try {
            output = Files.createTempFile("nemlab-fetch-", ".json");
            List<String> arguments = new ArrayList<>(command);
            arguments.addAll(List.of(FetchCommand.MODE, job.region().name(), job.day().toString(), output.toString()));
            ProcessBuilder builder = new ProcessBuilder(arguments);
            builder.environment().clear();
            builder.environment().putAll(environment);
            builder.redirectOutput(ProcessBuilder.Redirect.DISCARD);
            builder.redirectError(ProcessBuilder.Redirect.DISCARD);
            synchronized (this) {
                if (closed) {
                    throw new InterruptedException("Worker is stopping");
                }
                if (active != null) {
                    throw new IllegalStateException("A fetch is already running");
                }
                process = builder.start();
                active = process;
            }
            if (!process.waitFor(timeout.toMillis(), TimeUnit.MILLISECONDS)) {
                return FetchOutcome.failure("FETCH_DEADLINE_EXCEEDED", true);
            }
            if (process.exitValue() != 0) {
                return FetchOutcome.failure("FETCH_PROCESS_FAILED", true);
            }
            if (Files.size(output) > 256_000) {
                return FetchOutcome.failure("INVALID_CHILD_RESULT", false);
            }
            return new JsonMapper().readValue(Files.readString(output), FetchOutcome.class);
        } catch (IOException | RuntimeException failure) {
            return FetchOutcome.failure("FETCH_PROCESS_FAILED", true);
        } finally {
            if (process != null) {
                terminate(process);
                synchronized (this) {
                    if (active == process) {
                        active = null;
                    }
                }
            }
            if (output != null) {
                try {
                    Files.deleteIfExists(output);
                } catch (IOException ignored) {
                    // No credentials or raw responses are written to this temporary file.
                }
            }
        }
    }

    @Override
    public void close() {
        Process process;
        synchronized (this) {
            closed = true;
            process = active;
        }
        if (process != null) {
            terminate(process);
        }
    }

    private static void terminate(Process process) {
        if (!process.isAlive()) {
            return;
        }
        process.destroyForcibly();
        boolean interrupted = Thread.interrupted();
        long deadline = System.nanoTime() + Duration.ofSeconds(5).toNanos();
        try {
            while (process.isAlive() && System.nanoTime() < deadline) {
                try {
                    long remaining = Math.max(1, deadline - System.nanoTime());
                    process.waitFor(remaining, TimeUnit.NANOSECONDS);
                } catch (InterruptedException failure) {
                    interrupted = true;
                    process.destroyForcibly();
                }
            }
            if (process.isAlive()) {
                throw new TerminationFailure();
            }
        } finally {
            if (interrupted) {
                Thread.currentThread().interrupt();
            }
        }
    }

    static final class TerminationFailure extends IllegalStateException {
        TerminationFailure() {
            super("Fetch process did not terminate; worker polling must stop");
        }
    }

    private static List<String> defaultCommand() {
        String mainClass = "au.nemlab.worker.WorkerApplication";
        try {
            Class.forName("org.springframework.boot.loader.launch.JarLauncher");
            mainClass = "org.springframework.boot.loader.launch.JarLauncher";
        } catch (ClassNotFoundException ignored) {
            // IDE/Gradle classpaths run the ordinary application entry point.
        }
        String java = Path.of(System.getProperty("java.home"), "bin", "java").toString();
        return List.of(java, "-Xmx128m", "-cp", System.getProperty("java.class.path"), mainClass);
    }
}
