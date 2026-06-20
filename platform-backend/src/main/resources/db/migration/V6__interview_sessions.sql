-- Persist user type so workers can read it without the frontend re-sending it each time
ALTER TABLE users ADD COLUMN user_type VARCHAR(50) NOT NULL DEFAULT 'B2C';

-- Interview session: links a candidate, an optional interviewer, and a set of challenges
CREATE TABLE interview_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id UUID NOT NULL REFERENCES users(id),
    interviewer_id UUID REFERENCES users(id),
    challenge_ids JSONB NOT NULL DEFAULT '[]',
    status VARCHAR(50) NOT NULL DEFAULT 'SCHEDULED',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Link each submission to a session (nullable — prep-mode submissions have no session)
ALTER TABLE submissions ADD COLUMN session_id UUID REFERENCES interview_sessions(id);
ALTER TABLE submissions ADD COLUMN attempt_number INTEGER NOT NULL DEFAULT 1;

-- Fast lookups needed for attempt history (progressive feedback) and session reports
CREATE INDEX idx_submissions_user_challenge ON submissions(user_id, challenge_id, created_at DESC);
CREATE INDEX idx_submissions_session ON submissions(session_id);
