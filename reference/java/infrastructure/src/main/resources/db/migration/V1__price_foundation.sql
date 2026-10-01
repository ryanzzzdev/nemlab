CREATE TABLE price_revision (
    id uuid PRIMARY KEY,
    region text NOT NULL CHECK (region IN ('NSW1','QLD1','SA1','TAS1','VIC1')),
    market_day date NOT NULL,
    content_hash char(64) NOT NULL,
    slots jsonb NOT NULL CHECK (jsonb_typeof(slots) = 'array' AND jsonb_array_length(slots) = 288),
    valid_count integer NOT NULL CHECK (valid_count BETWEEN 0 AND 288),
    missing_count integer NOT NULL CHECK (missing_count BETWEEN 0 AND 288),
    null_count integer NOT NULL CHECK (null_count BETWEEN 0 AND 288),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (valid_count + missing_count + null_count = 288),
    UNIQUE(region, market_day, content_hash),
    UNIQUE(id, region, market_day)
);
CREATE TABLE price_current (
    region text NOT NULL,
    market_day date NOT NULL,
    revision_id uuid NOT NULL,
    retrieved_at timestamptz NOT NULL,
    PRIMARY KEY(region, market_day),
    FOREIGN KEY(revision_id, region, market_day) REFERENCES price_revision(id, region, market_day)
);
CREATE TABLE price_import_attempt (
    id uuid PRIMARY KEY,
    region text NOT NULL,
    market_day date NOT NULL,
    retrieved_at timestamptz NOT NULL,
    status text NOT NULL CHECK (status IN ('COMPLETE','INCOMPLETE','FAILED')),
    revision_id uuid REFERENCES price_revision(id),
    response_hash char(64),
    source_version text,
    diagnostic text,
    CHECK ((status = 'FAILED') = (revision_id IS NULL))
);
CREATE TABLE price_snapshot (
    id uuid PRIMARY KEY,
    revision_id uuid NOT NULL REFERENCES price_revision(id),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE price_backfill (
    id uuid PRIMARY KEY,
    region text NOT NULL CHECK (region IN ('NSW1','QLD1','SA1','TAS1','VIC1')),
    start_day date NOT NULL,
    end_exclusive date NOT NULL,
    next_day date NOT NULL,
    status text NOT NULL CHECK (status IN ('ACTIVE','PAUSED','COMPLETE')),
    diagnostic text,
    CHECK (start_day < end_exclusive AND end_exclusive - start_day <= 31),
    CHECK (next_day BETWEEN start_day AND end_exclusive)
);
CREATE FUNCTION reject_immutable_price_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'immutable price record'; END;
$$;
CREATE TRIGGER immutable_revision BEFORE UPDATE OR DELETE ON price_revision
    FOR EACH ROW EXECUTE FUNCTION reject_immutable_price_change();
CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON price_snapshot
    FOR EACH ROW EXECUTE FUNCTION reject_immutable_price_change();
CREATE FUNCTION require_complete_price_snapshot() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM price_revision WHERE id=NEW.revision_id AND valid_count=288) THEN
        RAISE EXCEPTION 'snapshot requires complete prices';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER complete_snapshot BEFORE INSERT ON price_snapshot
    FOR EACH ROW EXECUTE FUNCTION require_complete_price_snapshot();
CREATE INDEX price_attempt_history ON price_import_attempt(region,market_day,retrieved_at);
