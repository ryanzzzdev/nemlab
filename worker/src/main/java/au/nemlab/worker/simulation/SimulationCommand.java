package au.nemlab.worker.simulation;

import au.nemlab.batterylab.SimulationComparison;
import au.nemlab.infrastructure.batterylab.SimulationJobs;
import tools.jackson.databind.json.JsonMapper;
import java.nio.file.Files;
import java.nio.file.Path;

/** Database-free child mode, also protected if its parent exits unexpectedly. */
public final class SimulationCommand {
    public static final String MODE = "--simulate";
    public static final int DEADLINE_SECONDS = 15;
    public record Output(String key, SimulationComparison comparison) { }

    private SimulationCommand() { }

    public static int run(String[] args) {
        if (args.length != 3) return 2;
        Thread.ofPlatform().daemon().name("simulation-deadline").start(() -> {
            try { Thread.sleep(DEADLINE_SECONDS * 1000L); }
            catch (InterruptedException ignored) { Thread.currentThread().interrupt(); }
            Runtime.getRuntime().halt(124);
        });
        try {
            Path inputFile = Path.of(args[1]);
            if (Files.size(inputFile) > 512_000) return 2;
            var json = new JsonMapper();
            var input = json.readValue(Files.readString(inputFile), SimulationJobs.Input.class);
            var result = SimulationComparison.run(input.parameters(), input.prices(), input.versions().limits());
            Files.writeString(Path.of(args[2]), json.writeValueAsString(new Output(input.key(), result)));
            return 0;
        } catch (Exception failure) {
            return 3;
        }
    }
}
