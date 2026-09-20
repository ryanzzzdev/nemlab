package au.nemlab.infrastructure.batterylab;

import au.nemlab.batterylab.*;
import au.nemlab.infrastructure.prices.PriceBatch;
import au.nemlab.infrastructure.prices.PriceStore;
import java.time.Clock;
import java.util.Objects;
import java.util.UUID;

/** Read-only input capture. Durable job submission and snapshot linkage follow separately. */
public final class ScenarioPreparation {
    private final PriceStore prices;
    private final Clock clock;

    public ScenarioPreparation(PriceStore prices, Clock clock) {
        this.prices = Objects.requireNonNull(prices);
        this.clock = Objects.requireNonNull(clock);
    }

    public record Versions(String request, String model, String fixed, String hindsight, String solver,
            String executionProfile, OrderedHindsight.Limits limits) {
        public static Versions current() {
            return new Versions("simulation-request-v1", BatterySimulation.MODEL_VERSION, FixedSchedule.VERSION,
                    OrderedHindsight.VERSION, OrderedHindsight.SOLVER, "ordered-comparison-v1",
                    OrderedHindsight.Limits.standard());
        }

        public String canonical() {
            return String.join("\n", request, model, fixed, hindsight, solver, executionProfile,
                    Long.toString(limits.milliseconds()), Integer.toString(limits.iterations()));
        }
    }

    public record Prepared(String key, SimulationRequest.Normalised parameters, UUID priceRevision,
            PriceDay prices, Versions versions) {
    }

    public Prepared prepare(SimulationRequest request) {
        if (request == null) throw new SimulationRequest.Invalid("request", "REQUIRED");
        var parameters = request.normalise(clock);
        var coverage = prices.coverage(request.region(), request.day())
                .orElseThrow(() -> new SimulationRequest.Invalid("day", "PRICE_DAY_UNAVAILABLE"));
        // Never reread price_current: a concurrent correction must not change this captured input.
        var revision = prices.revision(coverage.revision());
        if (!revision.complete()) throw new SimulationRequest.Invalid("day", "PRICE_DAY_INCOMPLETE");
        var versions = Versions.current();
        String key = PriceBatch.hash(parameters.canonical() + "\n" + coverage.revision() + "\n" + versions.canonical());
        return new Prepared(key, parameters, coverage.revision(), revision.toPriceDay(), versions);
    }
}
