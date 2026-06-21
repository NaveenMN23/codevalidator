ALTER TABLE generation_jobs ADD COLUMN IF NOT EXISTS debug_scenarios_per_tier INTEGER NOT NULL DEFAULT 1;
