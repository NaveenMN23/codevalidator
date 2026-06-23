ALTER TABLE generation_jobs DROP CONSTRAINT generation_jobs_problem_id_fkey;
ALTER TABLE generation_jobs
    ADD CONSTRAINT generation_jobs_problem_id_fkey
    FOREIGN KEY (problem_id) REFERENCES problems(id) ON DELETE SET NULL;
