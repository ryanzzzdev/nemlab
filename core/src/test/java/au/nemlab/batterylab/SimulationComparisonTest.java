package au.nemlab.batterylab;

import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import java.time.*;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class SimulationComparisonTest {
    final SimulationRequest.Normalised parameters = SimulationRequestTest.request().normalise(SimulationRequestTest.CLOCK);
    final OrderedHindsight.Limits limits = OrderedHindsight.Limits.standard();

    PriceDay prices() {
        LocalDate day = parameters.values().day();
        Instant start = day.atStartOfDay().toInstant(PriceDay.NEM_OFFSET);
        var intervals = new ArrayList<PriceDay.Interval>();
        for (int i = 0; i < 288; i++) intervals.add(PriceDay.Interval.fromEnd(PriceDay.Region.NSW1,
                start.plusSeconds((i + 1L) * 300), BigDecimal.valueOf(parameters.windows().canCharge(i) ? -30 : 200)));
        return new PriceDay(PriceDay.Region.NSW1, day, intervals);
    }

    @Test
    void validatesBothStrategiesAndRejectsTamperedPhysicalOutputs() {
        var prices = prices();
        var result = SimulationComparison.run(parameters, prices, limits);
        assertEquals(OrderedHindsight.Status.OPTIMAL, result.hindsight().status());
        assertDoesNotThrow(() -> result.validate(parameters, prices, limits));
        var steps = new ArrayList<>(result.hindsight().dispatch().intervals());
        steps.set(0, new Dispatch.Interval(1, 1, 0));
        var h = result.hindsight();
        var broken = new OrderedHindsight.Outcome(h.status(), h.solverState(), h.certificateState(),
                new Dispatch(steps, h.dispatch().limitingReason()), h.accounting(), h.solverObjective(),
                h.upperBound(), h.absoluteGap(), h.elapsedNanos(), h.limits(), h.diagnostic());
        assertThrows(IllegalArgumentException.class, () -> new SimulationComparison(result.fixedDispatch(),
                result.fixedAccounting(), broken).validate(parameters, prices, limits));
    }

    @Test
    void rejectsUnprovenExpiredAndNonfiniteOptimalityClaims() {
        var prices = prices();
        var result = SimulationComparison.run(parameters, prices, limits);
        var h = result.hindsight();
        var invalid = List.of(
                new OrderedHindsight.Outcome(h.status(), "FEASIBLE", h.certificateState(), h.dispatch(), h.accounting(),
                        h.solverObjective(), h.upperBound(), h.absoluteGap(), h.elapsedNanos(), h.limits(), null),
                new OrderedHindsight.Outcome(h.status(), h.solverState(), h.certificateState(), h.dispatch(), h.accounting(),
                        h.solverObjective(), h.upperBound(), .02, h.elapsedNanos(), h.limits(), null),
                new OrderedHindsight.Outcome(h.status(), h.solverState(), h.certificateState(), h.dispatch(), h.accounting(),
                        h.solverObjective(), h.upperBound(), h.absoluteGap(), 5_000_000_000L, h.limits(), null),
                new OrderedHindsight.Outcome(h.status(), h.solverState(), h.certificateState(), h.dispatch(), h.accounting(),
                        Double.POSITIVE_INFINITY, h.upperBound(), h.absoluteGap(), h.elapsedNanos(), h.limits(), null));
        for (var outcome : invalid) assertThrows(IllegalArgumentException.class,
                () -> new SimulationComparison(result.fixedDispatch(), result.fixedAccounting(), outcome).validate(parameters, prices, limits));
    }

    @Test
    void preservesFailedSolverDiagnosticsWithoutDispatch() {
        var prices = prices();
        var result = SimulationComparison.run(parameters, prices, limits);
        var failed = new OrderedHindsight.Outcome(OrderedHindsight.Status.NO_SOLUTION, "NOT_RUN", "NOT_RUN",
                null, null, null, null, null, 0, limits, "No feasible point");
        assertDoesNotThrow(() -> new SimulationComparison(result.fixedDispatch(), result.fixedAccounting(), failed)
                .validate(parameters, prices, limits));
        var falseFailure = new OrderedHindsight.Outcome(OrderedHindsight.Status.ERROR, "ERROR", "NOT_RUN",
                result.hindsight().dispatch(), result.hindsight().accounting(), null, null, null, 0, limits, null);
        assertThrows(IllegalArgumentException.class, () -> new SimulationComparison(result.fixedDispatch(), result.fixedAccounting(), falseFailure)
                .validate(parameters, prices, limits));
    }
}
