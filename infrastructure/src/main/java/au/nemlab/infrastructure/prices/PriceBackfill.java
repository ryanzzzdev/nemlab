package au.nemlab.infrastructure.prices;

import java.time.Clock;
import java.util.UUID;

/**
 * One-day synchronous steps. Scheduling, authentication and distributed leases
 * belong to the worker layer.
 */
public final class PriceBackfill {
    private final PriceStore store;
    private final PriceSource source;
    private final Clock clock;

    public PriceBackfill(PriceStore store, PriceSource source, Clock clock) {
        this.store = store;
        this.source = source;
        this.clock = clock;
    }

    public boolean step(UUID id) {
        var task = store.backfill(id);
        if (task.status().equals("COMPLETE"))
            return false;
        try {
            return store.commitDay(id, task.next(), source.fetch(task.region(), task.next()));
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            store.recordFailure(task, clock.instant(), "INTERRUPTED");
            return false;
        } catch (OePriceSource.Failure ex) {
            store.recordFailure(task, clock.instant(), ex.code());
            return false;
        } catch (Exception ex) {
            store.recordFailure(task, clock.instant(), "FETCH_OR_STORAGE_FAILED:" + ex.getClass().getSimpleName());
            return false;
        }
    }
}
