-- Create agent_runs if it doesn't exist (this is the service-layer copy;
-- the DuckDB version lives in ~/.stratum/meta.duckdb separately).
CREATE TABLE IF NOT EXISTS agent_runs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    corpus_id TEXT,
    agent_name TEXT NOT NULL,
    params JSONB DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending',
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    total_input_tokens INT DEFAULT 0,
    total_output_tokens INT DEFAULT 0,
    cost_usd FLOAT DEFAULT 0.0,
    error TEXT,
    trace JSONB,
    citations JSONB,
    files_generated JSONB
);

CREATE INDEX IF NOT EXISTS idx_ar_user ON agent_runs(user_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_ar_status ON agent_runs(status);
