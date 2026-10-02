-- V4: GridReplay observations — versioned per-series grid context.
-- Mirrors the price foundation (immutable revisions + mutable current
-- pointer + attempt audit), extended with metric/series identity.
-- `series` is the empty string for single-series metrics and the provider
-- fueltech label for power. Slots follow the provider source-label grid
-- [00:00,24:00), 288 five-minute positions.

CREATE TABLE grid_revision (
    id uuid PRIMARY KEY,
    region text NOT NULL CHECK (region IN ('NSW1','QLD1','SA1','TAS1','VIC1')),
    metric text NOT NULL CHECK (metric IN ('demand','flow_imports','flow_exports','power')),
    series text NOT NULL,
    market_day date NOT NULL,
    content_hash char(64) NOT NULL,
    slots jsonb NOT NULL CHECK (jsonb_typeof(slots) = 'array' AND jsonb_array_length(slots) = 288),
    valid_count integer NOT NULL CHECK (valid_count BETWEEN 0 AND 288),
    missing_count integer NOT NULL CHECK (missing_count BETWEEN 0 AND 288),
    null_count integer NOT NULL CHECK (null_count BETWEEN 0 AND 288),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (valid_count + missing_count + null_count = 288),
    UNIQUE(region, metric, series, market_day, content_hash),
    UNIQUE(id, region, metric, series, market_day)
);

CREATE TABLE grid_current (
    region text NOT NULL,
    metric text NOT NULL,
    series text NOT NULL,
    market_day date NOT NULL,
    revision_id uuid NOT NULL,
    retrieved_at timestamptz NOT NULL,
    PRIMARY KEY(region, metric, series, market_day),
    FOREIGN KEY(revision_id, region, metric, series, market_day)
        REFERENCES grid_revision(id, region, metric, series, market_day)
);

-- One row per provider request; a power fetch writes many series revisions.
CREATE TABLE grid_import_attempt (
    id uuid PRIMARY KEY,
    region text NOT NULL,
    market_day date NOT NULL,
    metrics text[] NOT NULL,
    retrieved_at timestamptz NOT NULL,
    status text NOT NULL CHECK (status IN ('COMPLETE','INCOMPLETE','FAILED')),
    revision_count integer NOT NULL DEFAULT 0,
    response_hash char(64),
    source_version text,
    diagnostic text,
    CHECK ((status = 'FAILED') = (revision_count = 0))
);
CREATE INDEX grid_attempt_history
    ON grid_import_attempt(region, market_day, retrieved_at);

CREATE FUNCTION reject_immutable_grid_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'immutable grid record'; END;
$$;
CREATE TRIGGER immutable_grid_revision BEFORE UPDATE OR DELETE ON grid_revision
    FOR EACH ROW EXECUTE FUNCTION reject_immutable_grid_change();
