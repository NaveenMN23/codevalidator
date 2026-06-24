-- problem_link now stores the S3 object key relative to the configured challenges bucket
-- (app.aws.s3.challenges-bucket), not a full URL — bucket/region live in config, not per-row.
UPDATE problems
SET problem_link = 'java/vending-machine-easy-dispense-product.zip'
WHERE slug = 'vending-machine-dispense-product';
