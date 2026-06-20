CREATE TABLE blueprints (
    challenge_id VARCHAR(255) PRIMARY KEY REFERENCES challenges(id) ON DELETE CASCADE,
    blueprint_json JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Store structured AI evaluation feedback
ALTER TABLE submissions ADD COLUMN feedback JSONB;
