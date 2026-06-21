-- Identifies which gold-master tier/scenario a problem maps to (e.g. "beginner-divide-by-zero"),
-- used by Submit to fetch the matching hidden test from the gold-masters S3 bucket
-- ({language}/{slug}-{tier}.zip). Nullable: Submit fails clearly for a problem with no tier set
-- rather than guessing.
ALTER TABLE problems ADD COLUMN tier VARCHAR(64);
