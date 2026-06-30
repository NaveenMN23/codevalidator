-- Problem.java already maps an isPublished field to this column, but no prior migration
-- ever added it — a pre-existing gap, not something introduced by this change.
ALTER TABLE problems ADD COLUMN IF NOT EXISTS is_published BOOLEAN NOT NULL DEFAULT false;

-- Existing rows predate this column and are already real, in-use challenges — mark them
-- published rather than silently hiding them from anything that later filters on this.
UPDATE problems SET is_published = true;
