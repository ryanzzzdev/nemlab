-- V10: Load operations — resumable bounded owner import dispatch (NEM-102).
-- A lightweight record linking an owner-declared region/range to the
-- <=31-day chunk submissions it fans out across the existing grid-import
-- and price-refresh queues. No second scheduler: children reference the
-- durable job rows those queues already own.
CREATE TABLE load_operation (
    id uuid PRIMARY KEY,
    region text NOT NULL,
    start_day date NOT NULL,
    end_exclusive date NOT NULL,
    actor text NOT NULL,
    status text NOT NULL
        CHECK (status IN ('dispatching', 'paused', 'dispatched')),
    phase text NOT NULL CHECK (phase IN ('grid', 'price')),
    next_day date NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (start_day < end_exclusive),
    CHECK (end_exclusive <= start_day + interval '366 days')
);

-- One row per bounded chunk submission. request_key is deterministic
-- (load:{operation}:{phase}:{start}) so a crash between queue submission
-- and link recording reconciles through the queues' own idempotency.
CREATE TABLE load_operation_child (
    operation_id uuid NOT NULL REFERENCES load_operation(id)
        ON DELETE CASCADE,
    phase text NOT NULL CHECK (phase IN ('grid', 'price')),
    request_key text NOT NULL,
    start_day date NOT NULL,
    end_exclusive date NOT NULL,
    job_ids uuid[] NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (operation_id, request_key)
);

CREATE INDEX load_operation_child_operation
    ON load_operation_child (operation_id, phase, start_day);
