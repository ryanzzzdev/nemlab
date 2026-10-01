package au.nemlab.batterylab;

final class Numbers {
    private Numbers() {
    }

    static double finite(String field, double value) {
        if (!Double.isFinite(value))
            throw new IllegalArgumentException(field + " must be finite");
        return value;
    }

    static double nonnegative(String field, double value) {
        finite(field, value);
        if (value < 0)
            throw new IllegalArgumentException(field + " must be nonnegative");
        return value;
    }

    static double efficiency(String field, double value) {
        finite(field, value);
        if (value <= 0 || value > 1)
            throw new IllegalArgumentException(field + " must be in (0,1]");
        return value;
    }
}
