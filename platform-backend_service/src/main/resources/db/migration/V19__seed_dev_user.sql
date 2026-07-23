INSERT INTO users (id, email, auth_provider, display_name, created_at, updated_at)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'dev@local',
    'LOCAL',
    'Dev User',
    now(),
    now()
)
ON CONFLICT (id) DO NOTHING;
