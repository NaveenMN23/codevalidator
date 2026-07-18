-- Drop untracked column added outside Flyway (no migration ever created it; holds no real data)
ALTER TABLE problems DROP COLUMN IF EXISTS tiers;

-- Mandatory JSONB metadata column, empty object for now until S3 metadata is wired up
ALTER TABLE problems ADD COLUMN metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

INSERT INTO problems (id, slug, title, description, difficulty, problem_link, tags, language, is_published, metadata)
VALUES (
    gen_random_uuid(),
    'vending-machine-dispense-product',
    'Vending Machine: Dispense Product',
    NULL,
    'EASY',
    'https://challenges-repo.s3.ap-southeast-2.amazonaws.com/java/vending-machine-easy-dispense-product.zip',
    '{java}',
    'java',
    false,
    '{}'::jsonb
);
