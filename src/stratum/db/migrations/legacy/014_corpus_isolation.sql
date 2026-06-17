-- src/stratum/db/migrations/014_corpus_isolation.sql

-- 1. substrate 表加 corpus_id
ALTER TABLE substrate ADD COLUMN corpus_id VARCHAR;
UPDATE substrate SET corpus_id = 'corpus_default' WHERE corpus_id IS NULL;
-- ALTER TABLE substrate ALTER COLUMN corpus_id SET NOT NULL; -- DuckDB might not support ALTER COLUMN SET NOT NULL
CREATE INDEX idx_substrate_corpus ON substrate(corpus_id);

-- 2. derivative 表
ALTER TABLE derivative ADD COLUMN corpus_id VARCHAR;
UPDATE derivative SET corpus_id = 'corpus_default' WHERE corpus_id IS NULL;
CREATE INDEX idx_derivative_corpus ON derivative(corpus_id);

-- 3. note 表
ALTER TABLE note ADD COLUMN corpus_id VARCHAR;
UPDATE note SET corpus_id = 'corpus_default' WHERE corpus_id IS NULL;
CREATE INDEX idx_note_corpus ON note(corpus_id);

-- 4. concept 表
ALTER TABLE concept ADD COLUMN corpus_id VARCHAR;
UPDATE concept SET corpus_id = 'corpus_default' WHERE corpus_id IS NULL;
CREATE INDEX idx_concept_corpus ON concept(corpus_id);

-- 5. views 表
ALTER TABLE views ADD COLUMN corpus_id VARCHAR;
UPDATE views SET corpus_id = 'corpus_default' WHERE corpus_id IS NULL;
CREATE INDEX idx_views_corpus ON views(corpus_id);

-- 6. tasks 表
ALTER TABLE tasks ADD COLUMN corpus_id VARCHAR;
UPDATE tasks SET corpus_id = 'corpus_default' WHERE corpus_id IS NULL;
CREATE INDEX idx_tasks_corpus ON tasks(corpus_id);

-- 7. templates 表
ALTER TABLE templates ADD COLUMN corpus_id VARCHAR;
UPDATE templates SET corpus_id = 'corpus_default' WHERE corpus_id IS NULL;
CREATE INDEX idx_templates_corpus ON templates(corpus_id);

-- 8. scheduled_jobs 表
ALTER TABLE scheduled_jobs ADD COLUMN corpus_id VARCHAR;
UPDATE scheduled_jobs SET corpus_id = 'corpus_default' WHERE corpus_id IS NULL;
CREATE INDEX idx_scheduled_jobs_corpus ON scheduled_jobs(corpus_id);

-- 9. scheduled_job_runs 表
ALTER TABLE scheduled_job_runs ADD COLUMN corpus_id VARCHAR;
UPDATE scheduled_job_runs SET corpus_id = 'corpus_default' WHERE corpus_id IS NULL;
CREATE INDEX idx_scheduled_job_runs_corpus ON scheduled_job_runs(corpus_id);

-- 10. agent_runs 表
ALTER TABLE agent_runs ADD COLUMN corpus_id VARCHAR;
UPDATE agent_runs SET corpus_id = 'corpus_default' WHERE corpus_id IS NULL;
CREATE INDEX idx_agent_runs_corpus ON agent_runs(corpus_id);

-- 11. push_subscriptions 表
ALTER TABLE push_subscriptions ADD COLUMN corpus_id VARCHAR;
UPDATE push_subscriptions SET corpus_id = 'corpus_default' WHERE corpus_id IS NULL;
CREATE INDEX idx_push_subscriptions_corpus ON push_subscriptions(corpus_id);

-- 12. browser_ext_url_index 表
ALTER TABLE browser_ext_url_index ADD COLUMN corpus_id VARCHAR;
UPDATE browser_ext_url_index SET corpus_id = 'corpus_default' WHERE corpus_id IS NULL;
CREATE INDEX idx_browser_ext_url_index_corpus ON browser_ext_url_index(corpus_id);
