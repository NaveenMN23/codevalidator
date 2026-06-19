CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE users (
    id              UUID PRIMARY KEY,
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   VARCHAR(255),
    auth_provider   VARCHAR(32) NOT NULL DEFAULT 'LOCAL',
    provider_id     VARCHAR(255),
    display_name    VARCHAR(255),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE problems (
    id              UUID PRIMARY KEY,
    slug            VARCHAR(255) NOT NULL UNIQUE,
    title           VARCHAR(255) NOT NULL,
    description     TEXT,
    difficulty      VARCHAR(16) NOT NULL,
    problem_link    VARCHAR(1024) NOT NULL,
    tags            TEXT[] NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_problems_tags ON problems USING GIN (tags);

CREATE TABLE user_problem (
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    problem_id          UUID NOT NULL REFERENCES problems(id) ON DELETE CASCADE,
    status              VARCHAR(16) NOT NULL DEFAULT 'NOT_STARTED',
    best_score          NUMERIC,
    attempt_count       INTEGER NOT NULL DEFAULT 0,
    last_attempted_at   TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, problem_id)
);

CREATE TABLE submissions (
    id                  UUID PRIMARY KEY,
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    problem_id          UUID NOT NULL REFERENCES problems(id) ON DELETE CASCADE,
    submission_link     VARCHAR(1024) NOT NULL,
    score               NUMERIC,
    submitted_at        TIMESTAMPTZ NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_submissions_user_problem ON submissions (user_id, problem_id);

CREATE TABLE drafts (
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    problem_id      UUID NOT NULL REFERENCES problems(id) ON DELETE CASCADE,
    draft_link      VARCHAR(1024) NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, problem_id)
);
