package au.nemlab.batterylab;

import java.util.Objects;

/** Both strategies plus diagnostics; only OPTIMAL is a publishable comparison. */
public record SimulationComparison(Dispatch fixedDispatch, Accounting fixedAccounting, OrderedHindsight.Outcome hindsight) {
    public static SimulationComparison run(SimulationRequest.Normalised p, PriceDay prices, OrderedHindsight.Limits limits) {
        var fixed = new BatterySimulation().run(p.battery(), p.windows(), p.costs(), prices);
        return new SimulationComparison(fixed.dispatch(), fixed.accounting(),
                new OrderedHindsight().solve(p.battery(), p.windows(), p.costs(), prices, limits));
    }

    public void validate(SimulationRequest.Normalised p, PriceDay prices, OrderedHindsight.Limits limits) {
        Objects.requireNonNull(hindsight);
        Objects.requireNonNull(hindsight.status());
        if (!new FixedSchedule().plan(p.battery(), p.windows()).equals(fixedDispatch))
            throw new IllegalArgumentException("fixed policy mismatch");
        validateStrategy(p, prices, fixedDispatch, fixedAccounting);
        for (Double value : new Double[] { hindsight.solverObjective(), hindsight.upperBound(), hindsight.absoluteGap() })
            if (value != null && !Double.isFinite(value)) throw new IllegalArgumentException("nonfinite solver metadata");
        if (!limits.equals(hindsight.limits()) || hindsight.elapsedNanos() < 0)
            throw new IllegalArgumentException("solver execution metadata mismatch");
        boolean hasDispatch = hindsight.status() == OrderedHindsight.Status.OPTIMAL
                || hindsight.status() == OrderedHindsight.Status.FEASIBLE_NOT_PROVEN;
        if (hasDispatch) {
            validateStrategy(p, prices, hindsight.dispatch(), hindsight.accounting());
        } else if (hindsight.dispatch() != null || hindsight.accounting() != null) {
            throw new IllegalArgumentException("failed solver cannot publish dispatch");
        }
        if (hindsight.status() == OrderedHindsight.Status.OPTIMAL) {
            Double gap = hindsight.absoluteGap(), bound = hindsight.upperBound();
            if (!"OPTIMAL".equals(hindsight.solverState()) || bound == null || !Double.isFinite(bound)
                    || gap == null || !Double.isFinite(gap) || gap < 0 || gap > .01
                    || hindsight.elapsedNanos() >= limits.milliseconds() * 1_000_000L
                    || !Accounting.reconciles(bound - hindsight.accounting().margin(), gap)
                    || hindsight.accounting().margin() + .01 < fixedAccounting.margin()
                        && !Accounting.reconciles(hindsight.accounting().margin(), fixedAccounting.margin()))
                throw new IllegalArgumentException("invalid optimality metadata");
        }
    }

    private static void validateStrategy(SimulationRequest.Normalised p, PriceDay prices, Dispatch dispatch, Accounting actual) {
        DispatchValidator.validate(p.battery(), p.windows(), Objects.requireNonNull(dispatch));
        Objects.requireNonNull(actual);
        Accounting expected = Accounting.calculate(p.battery(), p.costs(), prices, dispatch);
        double[] a = values(actual), e = values(expected);
        for (int i = 0; i < a.length; i++)
            if (!Accounting.reconciles(e[i], a[i])) throw new IllegalArgumentException("accounting mismatch");
    }

    private static double[] values(Accounting a) {
        return new double[] { a.importedMWh(), a.exportedMWh(), a.chargingCost(), a.revenue(),
                a.fees(), a.degradation(), a.margin(), a.lossesMWh() };
    }
}
