-- Carries the actual stdout/stderr from the Execution Service so SubmissionController can
-- return real output instead of a hardcoded null (the wiring plan's GradingResult shape
-- always included `logs`, but nothing ever populated it).
ALTER TABLE submissions ADD COLUMN logs TEXT;
