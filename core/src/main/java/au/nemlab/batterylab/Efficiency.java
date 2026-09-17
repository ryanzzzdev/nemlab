package au.nemlab.batterylab;

/** Normalised efficiency legs. Input adapters choose one factory, never both forms. */
public record Efficiency(double charge, double discharge) {
    public Efficiency {
        Numbers.efficiency("charge efficiency", charge);
        Numbers.efficiency("discharge efficiency", discharge);
    }
    public static Efficiency roundTrip(double value) {
        double leg = Math.sqrt(Numbers.efficiency("round-trip efficiency", value));
        return new Efficiency(leg, leg);
    }
}
