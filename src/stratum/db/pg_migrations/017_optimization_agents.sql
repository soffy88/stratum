-- 017_optimization_agents.sql
-- Integration of My Brain Is Full Crew patterns into Stratum
--
-- Registers new scheduled jobs and provides seed data.

-- Vault Audit: monthly health audit (runs 1st of each month at 03:00 CST)
INSERT INTO scheduled_jobs_sl (
    id,
    name,
    cron_expression,
    timezone,
    job_type,
    agent_name,
    config,
    enabled,
    created_at
) VALUES (
    'vault_health_audit',
    'vault_health_audit',
    '0 3 1 * *',
    'Asia/Shanghai',
    'native',
    'vault_audit',
    '{"include_graph_health": true}'::jsonb,
    true,
    NOW()
) ON CONFLICT (name) DO NOTHING;

-- Knowledge Gap Analysis: weekly (Sunday 04:00 CST)
INSERT INTO scheduled_jobs_sl (
    id,
    name,
    cron_expression,
    timezone,
    job_type,
    agent_name,
    config,
    enabled,
    created_at
) VALUES (
    'knowledge_gap_analysis',
    'knowledge_gap_analysis',
    '0 4 * * 0',
    'Asia/Shanghai',
    'native',
    'knowledge_gap',
    '{"top_k": 20}'::jsonb,
    true,
    NOW()
) ON CONFLICT (name) DO NOTHING;

-- Graph Health Scoring: daily (05:00 CST)
INSERT INTO scheduled_jobs_sl (
    id,
    name,
    cron_expression,
    timezone,
    job_type,
    agent_name,
    config,
    enabled,
    created_at
) VALUES (
    'graph_health_daily',
    'graph_health_daily',
    '0 5 * * *',
    'Asia/Shanghai',
    'native',
    'graph_health',
    '{"include_clusters": true}'::jsonb,
    true,
    NOW()
) ON CONFLICT (name) DO NOTHING;
