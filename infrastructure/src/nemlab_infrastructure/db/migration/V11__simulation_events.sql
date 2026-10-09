-- V11: Append-only simulation lifecycle evidence. Each authoritative state
-- transition in SimulationJobs writes one event in the same transaction:
-- queued, claimed, retry scheduled, lease recovery, succeeded, failed.
-- ``attempt`` is the attempt the event belongs to (NULL for QUEUED);
-- ``diagnostic`` carries the safe code; ``available_at`` records the next
-- eligible time on rescheduled attempts. Historical jobs predate the table
-- and honestly have no rows — readers label that, never fabricate it.
CREATE TABLE simulation_event (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    simulation_id UUID NOT NULL REFERENCES simulation_input(id),
    kind TEXT NOT NULL CHECK (kind IN (
        'QUEUED','CLAIMED','RETRY_SCHEDULED','LEASE_RECOVERED',
        'SUCCEEDED','FAILED'
    )),
    attempt INTEGER CHECK (attempt IS NULL OR attempt BETWEEN 1 AND 3),
    diagnostic TEXT,
    available_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX simulation_event_by_simulation
    ON simulation_event(simulation_id, id);
CREATE TRIGGER immutable_simulation_event BEFORE UPDATE OR DELETE
    ON simulation_event
    FOR EACH ROW EXECUTE FUNCTION reject_immutable_simulation_change();
