-- V8: Admin identity — browser accounts for the M6 Admin console
-- (features/admin.md, decision 024). Users hold the two human roles;
-- access requests, viewer grants, one-use tokens, sessions, the email
-- outbox, access audit and persisted rate limits are separate tables so
-- lifecycle data stays inspectable and retention-cleanable. No market or
-- job data is touched.

CREATE TABLE admin_user (
    id uuid PRIMARY KEY,
    role text NOT NULL CHECK (role IN ('owner', 'viewer')),
    display_name text NOT NULL CHECK (length(btrim(display_name)) BETWEEN 1 AND 100),
    email text NOT NULL CHECK (length(email) <= 254 AND email ~ '^[^@[:space:]]+@[^@[:space:]]+$'),
    disabled_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Email uniqueness is case-insensitive; provider dots/plus aliases are
-- preserved, never normalised away.
CREATE UNIQUE INDEX admin_user_email ON admin_user (lower(email));

-- Exactly one enabled owner; recovery disables the previous row first.
CREATE UNIQUE INDEX admin_user_single_owner
    ON admin_user (role) WHERE role = 'owner' AND disabled_at IS NULL;

CREATE TABLE admin_access_request (
    id uuid PRIMARY KEY,
    display_name text NOT NULL CHECK (length(btrim(display_name)) BETWEEN 1 AND 100),
    email text NOT NULL CHECK (length(email) <= 254 AND email ~ '^[^@[:space:]]+@[^@[:space:]]+$'),
    message text CHECK (message IS NULL OR length(message) <= 1000),
    status text NOT NULL CHECK (status IN ('unverified', 'pending', 'approved', 'rejected')),
    submitted_at timestamptz NOT NULL DEFAULT now(),
    verified_at timestamptz,
    decided_at timestamptz,
    decided_by uuid REFERENCES admin_user (id),
    version integer NOT NULL DEFAULT 0,
    CHECK ((status = 'unverified') = (verified_at IS NULL)),
    CHECK ((status IN ('approved', 'rejected')) = (decided_at IS NOT NULL)),
    CHECK ((decided_at IS NULL) = (decided_by IS NULL))
);

-- A normalised email holds at most one undecided request at a time;
-- reapplication after a decision submits a fresh row.
CREATE UNIQUE INDEX admin_access_request_active
    ON admin_access_request (lower(email)) WHERE status IN ('unverified', 'pending');
CREATE INDEX admin_access_request_queue
    ON admin_access_request (status, submitted_at);

CREATE TABLE admin_viewer_grant (
    id uuid PRIMARY KEY,
    request_id uuid NOT NULL UNIQUE REFERENCES admin_access_request (id),
    user_id uuid NOT NULL REFERENCES admin_user (id),
    granted_by uuid NOT NULL REFERENCES admin_user (id),
    granted_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    revoked_by uuid REFERENCES admin_user (id),
    CHECK (expires_at > granted_at),
    CHECK ((revoked_at IS NULL) = (revoked_by IS NULL))
);
CREATE INDEX admin_viewer_grant_user ON admin_viewer_grant (user_id);

-- One-use tokens: sign-in links for users and email verification for
-- access requests. Only the SHA-256 hash is stored.
CREATE TABLE admin_token (
    id uuid PRIMARY KEY,
    purpose text NOT NULL CHECK (purpose IN ('sign_in', 'request_verification')),
    user_id uuid REFERENCES admin_user (id),
    request_id uuid REFERENCES admin_access_request (id),
    token_hash char(64) NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    consumed_at timestamptz,
    CHECK (expires_at > created_at),
    CHECK (num_nonnulls(user_id, request_id) = 1),
    CHECK ((purpose = 'sign_in') = (user_id IS NOT NULL))
);

-- Server-side opaque sessions for owner/viewer (user_id) and applicants
-- (request_id). The cookie carries the unhashed token; only its SHA-256
-- hash is stored. Idle expiry is derived from last_seen_at, absolute
-- expiry from expires_at.
CREATE TABLE admin_session (
    id uuid PRIMARY KEY,
    user_id uuid REFERENCES admin_user (id),
    request_id uuid REFERENCES admin_access_request (id),
    token_hash char(64) NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    CHECK (expires_at > created_at),
    CHECK (num_nonnulls(user_id, request_id) = 1)
);
CREATE INDEX admin_session_owner
    ON admin_session (user_id) WHERE revoked_at IS NULL;

-- Transactional email: durable, deduplicated, bounded retry. The worker
-- drains pending rows on its poll cycle; no separate scheduler exists.
CREATE TABLE admin_email_outbox (
    id uuid PRIMARY KEY,
    recipient text NOT NULL CHECK (length(recipient) <= 254),
    kind text NOT NULL CHECK (kind IN ('sign_in', 'request_verification', 'request_decision')),
    subject text NOT NULL,
    body text NOT NULL,
    dedupe_key text,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed')),
    attempts integer NOT NULL DEFAULT 0,
    available_at timestamptz NOT NULL DEFAULT now(),
    sent_at timestamptz,
    diagnostic text,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX admin_email_outbox_dedupe
    ON admin_email_outbox (dedupe_key) WHERE dedupe_key IS NOT NULL;
CREATE INDEX admin_email_outbox_pending
    ON admin_email_outbox (available_at) WHERE status = 'pending';

-- Access audit: actor identity plus a role label safe to show viewers.
-- Append-only by convention; retention cleanup deletes old rows.
CREATE TABLE admin_access_audit (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    actor_user_id uuid REFERENCES admin_user (id),
    actor_label text NOT NULL,
    action text NOT NULL,
    subject text,
    result text NOT NULL,
    detail jsonb
);
CREATE INDEX admin_access_audit_time ON admin_access_audit (occurred_at);

-- Persisted fixed-window counters shared by every API/worker process.
CREATE TABLE admin_rate_limit (
    bucket text NOT NULL,
    subject text NOT NULL,
    window_start timestamptz NOT NULL,
    count integer NOT NULL CHECK (count >= 0),
    PRIMARY KEY (bucket, subject, window_start)
);
