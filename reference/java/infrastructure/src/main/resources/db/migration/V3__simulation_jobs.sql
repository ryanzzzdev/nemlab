CREATE TABLE simulation_input (
    id UUID PRIMARY KEY,
    scenario_key CHAR(64) NOT NULL UNIQUE,
    revision_id UUID NOT NULL REFERENCES price_revision(id),
    request JSONB NOT NULL CHECK (jsonb_typeof(request) = 'object'),
    versions JSONB NOT NULL CHECK (jsonb_typeof(versions) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE TRIGGER complete_simulation_input BEFORE INSERT ON simulation_input
    FOR EACH ROW EXECUTE FUNCTION require_complete_price_snapshot();

CREATE TABLE simulation_job (
    id UUID PRIMARY KEY REFERENCES simulation_input(id),
    status TEXT NOT NULL CHECK (status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 3),
    available_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    claim_token UUID,
    lease_until TIMESTAMPTZ,
    diagnostic TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK ((status = 'RUNNING') = (claim_token IS NOT NULL AND lease_until IS NOT NULL)),
    CHECK (status = 'RUNNING' OR (claim_token IS NULL AND lease_until IS NULL))
);
CREATE INDEX simulation_job_ready ON simulation_job(available_at, created_at) WHERE status = 'QUEUED';
CREATE UNIQUE INDEX simulation_one_running ON simulation_job((status)) WHERE status = 'RUNNING';
CREATE TABLE simulation_result (
    id UUID PRIMARY KEY REFERENCES simulation_job(id),
    result JSONB NOT NULL CHECK (jsonb_typeof(result) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE FUNCTION reject_immutable_simulation_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'immutable simulation record'; END;
$$;
CREATE TRIGGER immutable_simulation_input BEFORE UPDATE OR DELETE ON simulation_input
    FOR EACH ROW EXECUTE FUNCTION reject_immutable_simulation_change();
CREATE TRIGGER immutable_simulation_result BEFORE UPDATE OR DELETE ON simulation_result
    FOR EACH ROW EXECUTE FUNCTION reject_immutable_simulation_change();
