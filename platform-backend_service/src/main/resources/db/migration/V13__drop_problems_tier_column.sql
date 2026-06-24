-- Removed at request: Submit's hidden-test lookup (SubmitService) loses its tier value as a
-- result and will fail until replaced by another mechanism (e.g. the metadata column).
ALTER TABLE problems DROP COLUMN tier;
