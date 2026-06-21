-- Seeds a default admin user. Password: Admin123!
-- The bcrypt hash below is for "Admin123!" with cost factor 10.
-- Change the email/password via the app after first login.
INSERT INTO users (id, email, password_hash, display_name, auth_provider, is_admin, created_at, updated_at)
VALUES (
    gen_random_uuid(),
    'admin@test.com',
    '$2a$10$aKzw2q9LRWdHQkSgqhnp5ew3C9aCWPvL7/jA3FjStHl1y38GXu2QW',
    'Admin',
    'local',
    true,
    NOW(),
    NOW()
)
ON CONFLICT (email) DO UPDATE
    SET is_admin = true;
