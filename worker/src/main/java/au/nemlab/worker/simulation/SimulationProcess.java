package au.nemlab.worker.simulation;

import au.nemlab.infrastructure.batterylab.SimulationJobs;
import au.nemlab.batterylab.SimulationComparison;
import tools.jackson.databind.json.JsonMapper;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;

/** One owned child at a time; termination precedes result publication or retry. */
public final class SimulationProcess implements AutoCloseable {
    private final List<String> command;
    private final Duration timeout;
    private Process active;
    private boolean closed;

    public record Outcome(SimulationComparison result, String failure, boolean retryable) {
        static Outcome failure(String code, boolean retryable) { return new Outcome(null, code, retryable); }
    }

    public SimulationProcess() {
        this(defaultCommand(), Duration.ofSeconds(SimulationCommand.DEADLINE_SECONDS));
    }

    SimulationProcess(List<String> command, Duration timeout) {
        this.command = List.copyOf(command);
        this.timeout = timeout;
    }

    public Outcome execute(SimulationJobs.Input input) throws InterruptedException {
        Path inputFile = null;
        Path output = null;
        Process process = null;
        try {
            input.parameters();
            inputFile = Files.createTempFile("nemlab-simulation-input-", ".json");
            Files.writeString(inputFile, new JsonMapper().writeValueAsString(input));
            output = Files.createTempFile("nemlab-simulation-result-", ".json");
            List<String> arguments = new ArrayList<>(command);
            arguments.addAll(List.of(SimulationCommand.MODE, inputFile.toString(), output.toString()));
            ProcessBuilder builder = new ProcessBuilder(arguments);
            builder.environment().clear();
            builder.redirectOutput(ProcessBuilder.Redirect.DISCARD);
            builder.redirectError(ProcessBuilder.Redirect.DISCARD);
            synchronized (this) {
                if (closed) {
                    throw new InterruptedException("Worker is stopping");
                }
                if (active != null) {
                    throw new IllegalStateException("A simulation is already running");
                }
                process = builder.start();
                active = process;
            }
            if (!process.waitFor(timeout.toMillis(), TimeUnit.MILLISECONDS)) {
                return Outcome.failure("SIMULATION_DEADLINE_EXCEEDED", true);
            }
            if (process.exitValue() == 124) {
                return Outcome.failure("SIMULATION_DEADLINE_EXCEEDED", true);
            }
            if (process.exitValue() != 0) {
                return Outcome.failure("SIMULATION_PROCESS_FAILED", true);
            }
            if (Files.size(output) > 1_000_000) {
                return Outcome.failure("INVALID_CHILD_RESULT", false);
            }
            try {
                var result = new JsonMapper().readValue(Files.readString(output), SimulationCommand.Output.class);
                if (!input.key().equals(result.key()) || result.comparison() == null)
                    return Outcome.failure("INVALID_CHILD_RESULT", false);
                result.comparison().validate(input.parameters(), input.prices(), input.versions().limits());
                return new Outcome(result.comparison(), null, false);
            } catch (RuntimeException invalid) {
                return Outcome.failure("INVALID_CHILD_RESULT", false);
            }
        } catch (SimulationJobs.UnsupportedVersion failure) {
            return Outcome.failure("UNSUPPORTED_SIMULATION_VERSION", false);
        } catch (IOException | RuntimeException failure) {
            return Outcome.failure("SIMULATION_PROCESS_FAILED", true);
        } finally {
            if (process != null) {
                terminate(process);
                synchronized (this) {
                    if (active == process) {
                        active = null;
                    }
                }
            }
            if (inputFile != null) {
                try { Files.deleteIfExists(inputFile); } catch (IOException ignored) { }
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
            super("Simulation process did not terminate; worker polling must stop");
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
        return List.of(java, "-Xmx512m", "-XX:ActiveProcessorCount=2", "-cp", System.getProperty("java.class.path"), mainClass);
    }
}
