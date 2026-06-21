ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE problems ADD COLUMN IF NOT EXISTS is_published BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS generation_jobs (
    id                 UUID PRIMARY KEY,
    prompt             TEXT NOT NULL,
    languages          TEXT[] NOT NULL,
    tiers              TEXT[] NOT NULL,
    scenarios_per_tier INTEGER NOT NULL DEFAULT 3,
    status             VARCHAR(30) NOT NULL DEFAULT 'DESIGNING',
    design_json        JSONB,
    design_feedback    TEXT,
    result_json        JSONB,
    problem_id         UUID REFERENCES problems(id),
    error              TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_generation_jobs_status ON generation_jobs(status);
CREATE INDEX IF NOT EXISTS idx_generation_jobs_created ON generation_jobs(created_at DESC);
