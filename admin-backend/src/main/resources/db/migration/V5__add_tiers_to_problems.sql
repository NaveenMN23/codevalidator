ALTER TABLE problems ADD COLUMN tiers TEXT[] DEFAULT '{}';

-- Backfill tiers from the linked generation job for existing rows
UPDATE problems p
SET tiers = gj.tiers
FROM generation_jobs gj
WHERE gj.problem_id = p.id;
