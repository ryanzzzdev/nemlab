package au.nemlab.batterylab;

import java.util.stream.DoubleStream;

/**
 * Recompute unrounded amounts from dispatch; no schedule logic or display
 * rounding.
 */
public record Accounting(double importedMWh, double exportedMWh, double chargingCost,
        double revenue, double fees, double degradation, double margin, double lossesMWh) {
    public Accounting {
        for (double value : new double[] { importedMWh, exportedMWh, chargingCost, revenue,
                fees, degradation, margin, lossesMWh })
            Numbers.finite("accounting total", value);
    }

    public static Accounting calculate(Battery battery, TradingCosts costs, PriceDay day, Dispatch dispatch) {
        if (dispatch.intervals().size() != PriceDay.INTERVALS)
            throw new IllegalArgumentException("dispatch and price day lengths differ");
        double[] purchases = new double[PriceDay.INTERVALS], sales = new double[PriceDay.INTERVALS];
        for (int i = 0; i < PriceDay.INTERVALS; i++) {
            double price = day.intervals().get(i).price().doubleValue();
            purchases[i] = Numbers.finite("interval charging cost", price * dispatch.intervals().get(i).importedMWh());
            sales[i] = Numbers.finite("interval revenue", price * dispatch.intervals().get(i).exportedMWh());
        }
        double imported = dispatch.intervals().stream().mapToDouble(Dispatch.Interval::importedMWh).sum();
        double exported = dispatch.intervals().stream().mapToDouble(Dispatch.Interval::exportedMWh).sum();
        double chargingCost = DoubleStream.of(purchases).sum(), revenue = DoubleStream.of(sales).sum();
        double fees = costs.importFee() * imported + costs.exportFee() * exported;
        double degradation = costs.degradationPerExportedMWh() * exported;
        double losses = (1 - battery.efficiency().charge()) * imported
                + (1 / battery.efficiency().discharge() - 1) * exported;
        return new Accounting(imported, exported, chargingCost, revenue, fees, degradation,
                revenue - chargingCost - fees - degradation, losses);
    }

    public static boolean reconciles(double expected, double actual) {
        return Double.isFinite(expected) && Double.isFinite(actual)
                && Math.abs(expected - actual) <= 1e-6 + 1e-9 * Math.max(Math.abs(expected), Math.abs(actual));
    }
}
