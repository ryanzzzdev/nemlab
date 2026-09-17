package au.nemlab.batterylab;

/** Validated complete-day fixed schedule result, ready for a future application boundary. */
public final class BatterySimulation {
    public static final String MODEL_VERSION = "battery-v1";
    public record Result(String modelVersion, String strategyVersion, Battery battery,
                         ScheduleWindows windows, TradingCosts costs, PriceDay prices,
                         Dispatch dispatch, Accounting accounting) {}
    public Result run(Battery battery, ScheduleWindows windows, TradingCosts costs, PriceDay prices) {
        java.util.Objects.requireNonNull(costs, "costs");
        java.util.Objects.requireNonNull(prices, "prices");
        Dispatch dispatch = new FixedSchedule().plan(battery, windows);
        return new Result(MODEL_VERSION, FixedSchedule.VERSION, battery, windows, costs, prices,
                dispatch, Accounting.calculate(battery, costs, prices, dispatch));
    }
}
