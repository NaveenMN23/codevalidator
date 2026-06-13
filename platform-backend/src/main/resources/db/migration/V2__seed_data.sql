INSERT INTO users (id, email, name) VALUES ('550e8400-e29b-41d4-a716-446655440000', 'test@example.com', 'Test User') ON CONFLICT (email) DO NOTHING;

INSERT INTO challenges (id, title, difficulty, language, zip_url) VALUES 
('book-my-show-beginner', 'Book My Show: Broken Refund', 'BEGINNER', 'node', '/challenges/node/beginner-broken-refund.zip'),
('book-my-show-intermediate', 'Book My Show: Webhook Idempotency', 'INTERMEDIATE', 'node', '/challenges/node/intermediate-webhook-idempotency.zip'),
('book-my-show-advanced', 'Book My Show: Cache Stampede', 'ADVANCED', 'node', '/challenges/node/advanced-cache-stampede.zip')
ON CONFLICT (id) DO NOTHING;
