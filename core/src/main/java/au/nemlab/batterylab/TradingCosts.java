package au.nemlab.batterylab;

/** AUD per grid-side imported/exported MWh. */
public record TradingCosts(double importFee, double exportFee, double degradationPerExportedMWh) {
    public TradingCosts {
        Numbers.nonnegative("import fee", importFee);
        Numbers.nonnegative("export fee", exportFee);
        Numbers.nonnegative("degradation", degradationPerExportedMWh);
    }
}
