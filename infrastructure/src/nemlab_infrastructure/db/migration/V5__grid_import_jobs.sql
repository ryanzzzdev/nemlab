-- V5: bounded GridReplay import jobs — leased operator submissions with a
-- per-day resume checkpoint (next_day). Mirrors the refresh_job fencing
-- model; a claimed job may run many market days inside one lease that the
-- worker renews as each day commits. optional_failures counts days whose
-- optional (power) series fetch failed while core market data succeeded.

CREATE TABLE grid_import_job (
    id uuid PRIMARY KEY,
    region text NOT NULL CHECK (region IN ('NSW1','QLD1','SA1','TAS1','VIC1')),
    start_day date NOT NULL,
    end_exclusive date NOT NULL,
    next_day date NOT NULL,
    status text NOT NULL
        CHECK (status IN ('QUEUED','RUNNING','PAUSED','SUCCEEDED','FAILED','CANCELLED')),
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 5),
    optional_failures integer NOT NULL DEFAULT 0,
    available_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    claim_token uuid,
    lease_until timestamptz,
    diagnostic text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (end_exclusive > start_day AND end_exclusive <= start_day + 31),
    CHECK (next_day >= start_day AND next_day <= end_exclusive),
    CHECK ((status = 'RUNNING') = (claim_token IS NOT NULL AND lease_until IS NOT NULL)),
    CHECK (status = 'RUNNING' OR (claim_token IS NULL AND lease_until IS NULL))
);
CREATE UNIQUE INDEX grid_import_active_window
    ON grid_import_job(region, start_day, end_exclusive)
    WHERE status IN ('QUEUED','RUNNING','PAUSED');
CREATE INDEX grid_import_ready
    ON grid_import_job(available_at, created_at) WHERE status = 'QUEUED';

CREATE TABLE grid_import_request (
    request_key text PRIMARY KEY CHECK (length(request_key) BETWEEN 1 AND 120),
    job_id uuid NOT NULL REFERENCES grid_import_job(id)
);

CREATE TABLE grid_import_job_event (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_id uuid NOT NULL REFERENCES grid_import_job(id),
    occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    actor text NOT NULL CHECK (length(actor) BETWEEN 1 AND 80),
    action text NOT NULL,
    diagnostic text
);
