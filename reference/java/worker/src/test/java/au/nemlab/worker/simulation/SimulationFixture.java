package au.nemlab.worker.simulation;

import java.nio.file.*;
import java.util.Arrays;

public final class SimulationFixture {
    public static void main(String[] args) throws Exception {
        if (!System.getenv().isEmpty()) System.exit(9);
        Files.writeString(Path.of(args[1]), ProcessHandle.current().pid() + "\n" + args[3] + "\n" + args[4]);
        switch (args[0]) {
            case "hang" -> Thread.sleep(60_000);
            case "crash" -> System.exit(8);
            case "watchdog" -> {
                SimulationCommand.run(Arrays.copyOfRange(args, 2, args.length));
                Thread.sleep(60_000);
            }
            case "malformed" -> Files.writeString(Path.of(args[4]), "not JSON");
            case "oversized" -> Files.writeString(Path.of(args[4]), "x".repeat(1_000_001));
            default -> System.exit(SimulationCommand.run(Arrays.copyOfRange(args, 2, args.length)));
        }
    }
}
