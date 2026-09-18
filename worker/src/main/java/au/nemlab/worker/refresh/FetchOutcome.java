package au.nemlab.worker.refresh;

import au.nemlab.infrastructure.prices.PriceSource;

/** Small, credential-free result exchanged with the isolated fetch process. */
public record FetchOutcome(PriceSource.Fetch fetch, String failure, boolean retryable) {
    public FetchOutcome {
        if ((fetch == null) == (failure == null)) {
            throw new IllegalArgumentException("Exactly one result or failure is required");
        }
        if (failure != null && !failure.matches("[A-Z][A-Z0-9_]{0,79}")) {
            throw new IllegalArgumentException("Invalid failure code");
        }
    }

    public static FetchOutcome success(PriceSource.Fetch fetch) {
        return new FetchOutcome(fetch, null, false);
    }

    public static FetchOutcome failure(String code, boolean retryable) {
        return new FetchOutcome(null, code, retryable);
    }
}
