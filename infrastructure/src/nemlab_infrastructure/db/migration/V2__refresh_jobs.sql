CREATE TABLE refresh_job (
    id UUID PRIMARY KEY,
    backfill_id UUID NOT NULL UNIQUE REFERENCES price_backfill(id),
    region TEXT NOT NULL,
    market_day DATE NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 3),
    available_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    claim_token UUID,
    lease_until TIMESTAMPTZ,
    diagnostic TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK ((status = 'RUNNING') = (claim_token IS NOT NULL AND lease_until IS NOT NULL)),
    CHECK (status = 'RUNNING' OR (claim_token IS NULL AND lease_until IS NULL))
);

CREATE UNIQUE INDEX refresh_job_active_day ON refresh_job(region, market_day)
    WHERE status IN ('QUEUED', 'RUNNING');
CREATE INDEX refresh_job_ready ON refresh_job(available_at, created_at)
    WHERE status = 'QUEUED';

CREATE TABLE refresh_request (
    request_key TEXT PRIMARY KEY CHECK (length(request_key) BETWEEN 1 AND 120),
    job_id UUID NOT NULL REFERENCES refresh_job(id)
);

CREATE TABLE refresh_job_event (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES refresh_job(id),
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    actor TEXT NOT NULL CHECK (length(actor) BETWEEN 1 AND 80),
    action TEXT NOT NULL,
    diagnostic TEXT
);
