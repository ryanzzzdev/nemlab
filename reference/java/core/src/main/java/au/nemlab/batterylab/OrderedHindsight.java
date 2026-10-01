package au.nemlab.batterylab;

import org.ojalgo.optimisation.*;
import org.ojalgo.type.context.NumberContext;
import java.util.*;

/**
 * Exact ordered-window LP; overlapping or unrestricted windows are deliberately
 * unsupported.
 */
public final class OrderedHindsight {
    public static final String VERSION = "ordered-hindsight-v1";
    public static final String SOLVER = "ojAlgo 57.3.0";

    public enum Status {
        OPTIMAL, FEASIBLE_NOT_PROVEN, NO_SOLUTION, INFEASIBLE, FAILED_VALIDATION, ERROR
    }

    public record Limits(long milliseconds, int iterations) {
        public Limits {
            if (milliseconds < 0 || milliseconds > 60_000 || iterations < 0)
                throw new IllegalArgumentException("limits require 0..60000 milliseconds and nonnegative iterations");
        }

        public static Limits standard() {
            return new Limits(5_000, 100_000);
        }
    }

    /**
     * Dispatch/accounting are null when no independently validated solution exists;
     * bound/gap may be unavailable.
     */
    public record Outcome(Status status, String solverState, String certificateState,
            Dispatch dispatch, Accounting accounting, Double solverObjective,
            Double upperBound, Double absoluteGap, long elapsedNanos, Limits limits, String diagnostic) {
    }

    public Outcome solve(Battery battery, ScheduleWindows windows, TradingCosts costs, PriceDay prices, Limits limits) {
        Objects.requireNonNull(battery);
        Objects.requireNonNull(windows);
        Objects.requireNonNull(costs);
        Objects.requireNonNull(prices);
        Objects.requireNonNull(limits);
        long started = System.nanoTime();
        if (limits.milliseconds() == 0 || limits.iterations() == 0)
            return failure(Status.NO_SOLUTION, "NOT_RUN", "Budget exhausted before solve", started, limits);
        var model = new ExpressionsBasedModel();
        try {
            // Stored-energy variables make balance coefficients exactly +1/-1.
            double chargeUnit = Numbers.finite("stored charge limit",
                    battery.effectiveChargeMW() / 12 * battery.efficiency().charge());
            double dischargeUnit = Numbers.finite("stored discharge limit",
                    battery.effectiveDischargeMW() / 12 / battery.efficiency().discharge());
            double headroom = battery.maximumMWh() - battery.initialMWh();
            Variable[] imports = new Variable[288], exports = new Variable[288];
            double[] buy = new double[288], sell = new double[288];
            var balance = model.newExpression("equal stored charge and discharge").level(0);
            var capacity = model.newExpression("cycle headroom").upper(headroom);
            for (int i = 0; i < 288; i++) {
                double price = prices.intervals().get(i).price().doubleValue();
                if (windows.canCharge(i)) {
                    buy[i] = Numbers.finite("stored import cost",
                            (price + costs.importFee()) / battery.efficiency().charge());
                    imports[i] = model.newVariable("charge_" + i).lower(0).upper(chargeUnit).weight(-buy[i]);
                    balance.set(imports[i], 1);
                    capacity.set(imports[i], 1);
                }
                if (windows.canDischarge(i)) {
                    sell[i] = Numbers.finite("stored export revenue",
                            (price - costs.exportFee() - costs.degradationPerExportedMWh())
                                    * battery.efficiency().discharge());
                    exports[i] = model.newVariable("discharge_" + i).lower(0).upper(dischargeUnit).weight(sell[i]);
                    balance.set(exports[i], -1);
                }
            }
            configure(model, limits, started);
            if (expired(started, limits))
                return failure(Status.NO_SOLUTION, "NOT_RUN", "Budget exhausted building model", started, limits);
            var solution = model.maximise();
            var state = solution.getState();
            if (state == Optimisation.State.INFEASIBLE)
                return failure(Status.INFEASIBLE, state.name(), "Idle is feasible: investigate solver/model numerics",
                        started, limits);
            if (!state.isSuccess() || !state.isFeasible())
                return failure(state.isFailure() ? Status.ERROR : Status.NO_SOLUTION, state.name(),
                        "No solver-certified feasible point", started, limits);
            var intervals = new ArrayList<Dispatch.Interval>(288);
            double energy = battery.initialMWh();
            for (int i = 0; i < 288; i++) {
                double c = imports[i] == null ? 0
                        : solution.doubleValue(model.indexOf(imports[i])) / battery.efficiency().charge();
                double d = exports[i] == null ? 0
                        : solution.doubleValue(model.indexOf(exports[i])) * battery.efficiency().discharge();
                energy += battery.efficiency().charge() * c - d / battery.efficiency().discharge();
                intervals.add(new Dispatch.Interval(c, d, energy));
            }
            var dispatch = new Dispatch(intervals, Dispatch.Limit.NOT_EVALUATED);
            DispatchValidator.validate(battery, windows, dispatch);
            var accounting = Accounting.calculate(battery, costs, prices, dispatch);
            if (!Accounting.reconciles(solution.getValue(), accounting.margin()))
                return failure(Status.FAILED_VALIDATION, state.name(), "Objective differs from independent accounting",
                        started, limits);
            Double upper = null, gap = null;
            String certificateState = "NOT_RUN";
            if (!expired(started, limits)) {
                var certificate = certificate(windows, buy, sell, chargeUnit, dischargeUnit, headroom, limits, started);
                certificateState = certificate.state();
                upper = certificate.upper();
                if (upper != null) {
                    gap = upper - accounting.margin();
                    if (!Double.isFinite(gap) || gap < 0)
                        return failure(Status.FAILED_VALIDATION, state.name(), "Invalid primal/dual bound", started,
                                limits);
                }
            }
            boolean proven = canClaimOptimal(state.isOptimal(), gap, expired(started, limits));
            return new Outcome(proven ? Status.OPTIMAL : Status.FEASIBLE_NOT_PROVEN, state.name(), certificateState,
                    dispatch, accounting, solution.getValue(), upper, gap, System.nanoTime() - started, limits,
                    proven ? "Validated with independently evaluated dual upper bound"
                            : "Feasible point; proof or budget incomplete");
        } catch (IllegalArgumentException ex) {
            return failure(Status.FAILED_VALIDATION, "VALIDATION_ERROR", ex.getMessage(), started, limits);
        } catch (RuntimeException ex) {
            return failure(Status.ERROR, "ERROR", ex.getClass().getSimpleName() + ": " + ex.getMessage(), started,
                    limits);
        } finally {
            model.dispose();
        }
    }

    static boolean canClaimOptimal(boolean solverOptimal, Double gap, boolean budgetExpired) {
        return solverOptimal && gap != null && Double.isFinite(gap) && gap >= 0 && gap <= .01 && !budgetExpired;
    }

    private record Certificate(String state, Double upper) {
    }

    private static Certificate certificate(ScheduleWindows windows, double[] buy, double[] sell,
            double chargeUnit, double dischargeUnit, double headroom,
            Limits limits, long started) {
        var dual = new ExpressionsBasedModel();
        try {
            var lambda = dual.newVariable("balance price");
            var mu = dual.newVariable("capacity price").lower(0).weight(headroom);
            for (int i = 0; i < 288; i++) {
                if (windows.canCharge(i)) {
                    var slack = dual.newVariable("charge slack_" + i).lower(0).weight(chargeUnit);
                    dual.newExpression("charge bound_" + i).set(slack, 1).set(lambda, 1).set(mu, 1).lower(-buy[i]);
                }
                if (windows.canDischarge(i)) {
                    var slack = dual.newVariable("discharge slack_" + i).lower(0).weight(dischargeUnit);
                    dual.newExpression("discharge bound_" + i).set(slack, 1).set(lambda, -1).lower(sell[i]);
                }
            }
            configure(dual, limits, started);
            if (expired(started, limits))
                return new Certificate("BUDGET_EXHAUSTED", null);
            var result = dual.minimise();
            if (!result.getState().isSuccess() || !result.getState().isFeasible())
                return new Certificate(result.getState().name(), null);
            double l = Numbers.finite("dual lambda", result.doubleValue(dual.indexOf(lambda)));
            // Any lambda and nonnegative mu give an upper bound; rebuild slacks instead of
            // trusting dual feasibility.
            double m = Math.max(0, Numbers.finite("dual mu", result.doubleValue(dual.indexOf(mu))));
            double upper = dualUpperBound(windows, buy, sell, chargeUnit, dischargeUnit, headroom, l, m);
            return new Certificate(result.getState().name(), upper);
        } finally {
            dual.dispose();
        }
    }

    /**
     * Evaluate the Lagrangian upper bound with a conservative numerical allowance.
     */
    static double dualUpperBound(ScheduleWindows windows, double[] buy, double[] sell,
            double chargeUnit, double dischargeUnit, double headroom, double lambda, double mu) {
        // BigDecimal operations on exact double representations avoid cancellation in
        // the certificate calculation.
        java.math.BigDecimal l = new java.math.BigDecimal(lambda), m = new java.math.BigDecimal(mu);
        java.math.BigDecimal bound = new java.math.BigDecimal(headroom).multiply(m);
        double coefficientScale = 0;
        for (int i = 0; i < 288; i++) {
            if (windows.canCharge(i))
                coefficientScale += Math.abs(buy[i]) * chargeUnit;
            if (windows.canDischarge(i))
                coefficientScale += Math.abs(sell[i]) * dischargeUnit;
            if (windows.canCharge(i))
                bound = bound.add(new java.math.BigDecimal(chargeUnit).multiply(
                        new java.math.BigDecimal(-buy[i]).subtract(l).subtract(m).max(java.math.BigDecimal.ZERO)));
            if (windows.canDischarge(i))
                bound = bound.add(new java.math.BigDecimal(dischargeUnit).multiply(
                        new java.math.BigDecimal(sell[i]).add(l).max(java.math.BigDecimal.ZERO)));
        }
        double value = Numbers.finite("dual upper bound", bound.doubleValue());
        return Numbers.finite("dual bound with allowance",
                Math.nextUp(value + 1e-6 + 1e-9 * Math.max(Math.abs(value), coefficientScale)));
    }

    private static void configure(ExpressionsBasedModel model, Limits limits, long started) {
        model.options.time_abort = Math.max(1, limits.milliseconds() - (System.nanoTime() - started) / 1_000_000);
        model.options.iterations_abort = limits.iterations();
        model.options.feasibility = NumberContext.of(14, 10);
    }

    private static boolean expired(long started, Limits limits) {
        return System.nanoTime() - started >= limits.milliseconds() * 1_000_000;
    }

    private static Outcome failure(Status status, String state, String message, long started, Limits limits) {
        return new Outcome(status, state, "NOT_AVAILABLE", null, null, null, null, null, System.nanoTime() - started,
                limits, message);
    }
}
