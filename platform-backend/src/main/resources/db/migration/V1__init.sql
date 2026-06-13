CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE challenges (
    id VARCHAR(255) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    difficulty VARCHAR(50) NOT NULL,
    language VARCHAR(50) NOT NULL,
    zip_url VARCHAR(1024),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE challenge_drafts (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    challenge_id VARCHAR(255) REFERENCES challenges(id),
    files JSONB NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, challenge_id)
);

CREATE TABLE submissions (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    challenge_id VARCHAR(255) REFERENCES challenges(id),
    status VARCHAR(50) NOT NULL,
    score INTEGER,
    logs TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
