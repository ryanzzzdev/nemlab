-- V6: GridReplay detection output — immutable event versions, materialised
-- replay manifests, atomic catalogue publications and an audit run record.
-- Event identity is (region, type, detector_version, start_at); a source
-- correction creates a new row with the next `version` and a `supersedes`
-- link — earlier versions stay reproducible (no deletion exists).

CREATE TABLE grid_event (
    id uuid PRIMARY KEY,
    region text NOT NULL CHECK (region IN ('NSW1','QLD1','SA1','TAS1','VIC1')),
    type text NOT NULL
        CHECK (type IN ('negative_price_run','price_spike','demand_ramp')),
    detector_version text NOT NULL,
    detector_params jsonb NOT NULL,
    market_day date NOT NULL,          -- owner day of the event start
    start_at timestamptz NOT NULL,     -- interval-end instant of the first member
    end_at timestamptz NOT NULL,       -- interval-end instant of the last member
    interval_count integer NOT NULL CHECK (interval_count > 0),
    value numeric NOT NULL,
    edge_incomplete boolean NOT NULL,
    source_revisions jsonb NOT NULL,   -- pinned source revision id per input series
    coverage jsonb NOT NULL,           -- {evaluated, missing}
    version integer NOT NULL CHECK (version > 0),
    -- A row is superseded iff another row's `supersedes` points at it.
    supersedes uuid REFERENCES grid_event(id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(region, type, detector_version, start_at, version)
);
CREATE INDEX grid_event_identity
    ON grid_event(region, type, detector_version, start_at, version DESC);

-- Replay snapshot: materialises the exact observed values for the event's
-- bounded day window (<= 7 market days) so replays do not depend on source
-- retention; manifest records the provenance revisions.
CREATE TABLE grid_replay (
    id uuid PRIMARY KEY,
    event_id uuid NOT NULL UNIQUE REFERENCES grid_event(id),
    start_day date NOT NULL,
    end_exclusive date NOT NULL,
    CHECK (end_exclusive > start_day AND end_exclusive <= start_day + 7),
    manifest jsonb NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

-- One publication per detection run of a window; the pointer row makes the
-- catalogue swap atomic — readers only ever see a complete publication.
CREATE TABLE grid_publication (
    id uuid PRIMARY KEY,
    region text NOT NULL CHECK (region IN ('NSW1','QLD1','SA1','TAS1','VIC1')),
    start_day date NOT NULL,
    end_exclusive date NOT NULL,
    detector_version text NOT NULL,
    coverage jsonb NOT NULL,           -- per-day summary incl. skipped days
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE grid_publication_event (
    publication_id uuid NOT NULL REFERENCES grid_publication(id),
    event_id uuid NOT NULL REFERENCES grid_event(id),
    PRIMARY KEY (publication_id, event_id)
);
CREATE TABLE grid_catalogue_current (
    region text NOT NULL,
    start_day date NOT NULL,
    end_exclusive date NOT NULL,
    publication_id uuid NOT NULL REFERENCES grid_publication(id),
    published_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (region, start_day, end_exclusive)
);

-- Audit row per detection run; a FAILED row survives the rollback of the
-- attempted publication so operator runs stay auditable.
CREATE TABLE grid_detection_run (
    id uuid PRIMARY KEY,
    region text NOT NULL,
    start_day date NOT NULL,
    end_exclusive date NOT NULL,
    detector_version text NOT NULL,
    status text NOT NULL CHECK (status IN ('COMPLETE','FAILED')),
    publication_id uuid REFERENCES grid_publication(id),
    diagnostic text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TRIGGER immutable_grid_event BEFORE UPDATE OR DELETE ON grid_event
    FOR EACH ROW EXECUTE FUNCTION reject_immutable_grid_change();
CREATE TRIGGER immutable_grid_replay BEFORE UPDATE OR DELETE ON grid_replay
    FOR EACH ROW EXECUTE FUNCTION reject_immutable_grid_change();
CREATE TRIGGER immutable_grid_publication BEFORE UPDATE OR DELETE ON grid_publication
    FOR EACH ROW EXECUTE FUNCTION reject_immutable_grid_change();
