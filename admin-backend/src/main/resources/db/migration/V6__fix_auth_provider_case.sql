-- Fix auth_provider values seeded as 'local' (lowercase) by V3 migration.
-- platform-backend_service's AuthProvider enum requires uppercase (LOCAL, GOOGLE, GITHUB).
UPDATE users
SET auth_provider = UPPER(auth_provider)
WHERE auth_provider != UPPER(auth_provider);
