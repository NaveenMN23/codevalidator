CREATE TABLE execution_sessions (
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    problem_id          UUID NOT NULL REFERENCES problems(id) ON DELETE CASCADE,
    status              VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_activity_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, problem_id)
);
