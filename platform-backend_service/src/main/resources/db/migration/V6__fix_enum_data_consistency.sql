-- Fix auth_provider seeded as 'local' (lowercase) by admin-backend V3 migration.
-- platform-backend_service AuthProvider enum uses uppercase (LOCAL, GOOGLE, GITHUB).
UPDATE users
SET auth_provider = UPPER(auth_provider)
WHERE auth_provider != UPPER(auth_provider);

-- Normalise difficulty values not in the Difficulty enum {EASY, MEDIUM, HARD}.
-- admin-backend produced 'MIXED' for multi-tier jobs; default those to EASY.
UPDATE problems
SET difficulty = 'EASY'
WHERE difficulty NOT IN ('EASY', 'MEDIUM', 'HARD');
