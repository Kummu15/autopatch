-- AutoPatch database schema
-- Postgres (designed for AWS RDS)

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE repos (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    github_url      VARCHAR(500) NOT NULL,
    default_branch  VARCHAR(100) DEFAULT 'main',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE patch_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo_id         UUID NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    issue_text      TEXT NOT NULL,          -- bug description / failing test input
    status          VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending | running | success | failed
    model_used      VARCHAR(100),           -- e.g. 'llama-3.3-70b' via Groq
    generated_diff  TEXT,                   -- the patch itself
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ
);

CREATE TABLE eval_metrics (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patch_run_id     UUID NOT NULL REFERENCES patch_runs(id) ON DELETE CASCADE,
    quality_score    NUMERIC(5,2),   -- 0-100, your eval scoring logic
    tests_passed     INTEGER,
    tests_total      INTEGER,
    semantic_sim     NUMERIC(5,4),   -- similarity to ground-truth fix, if known
    latency_ms       INTEGER,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_patch_runs_user ON patch_runs(user_id);
CREATE INDEX idx_patch_runs_repo ON patch_runs(repo_id);
CREATE INDEX idx_patch_runs_status ON patch_runs(status);