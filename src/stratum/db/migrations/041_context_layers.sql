-- 041_context_layers.sql
-- L0/L1/L2 内容分层系统 (对标 OpenViking Context Layers)
SET search_path TO stratum;
--
-- L0 (Abstract): 一句话摘要 ~100 token — 快速相关性判断
-- L1 (Overview): 结构化概览 ~2K token — 关键信息 + 使用场景
-- L2 (Details): 原文引用 — 按需加载
--
-- substrate_layers: 文档级三层摘要
-- ku_layers: KU 级三层摘要
-- context_directory: 虚拟文件系统目录树 (viking:// URI)
-- retrieval_trajectories: 检索轨迹记录 (Phase 2 用)

-- ── substrate_layers ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS substrate_layers (
    id              TEXT PRIMARY KEY,
    substrate_id    TEXT NOT NULL REFERENCES stratum.substrates(id) ON DELETE CASCADE,
    layer           TEXT NOT NULL CHECK (layer IN ('L0', 'L1', 'L2')),
    content         TEXT NOT NULL,
    token_count     INT NOT NULL DEFAULT 0,
    model_used      TEXT,
    generated_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(substrate_id, layer)
);

CREATE INDEX IF NOT EXISTS idx_sl_substrate ON substrate_layers(substrate_id);
CREATE INDEX IF NOT EXISTS idx_sl_layer ON substrate_layers(layer);

-- ── ku_layers ────────────────────────────────────────────────────────────────
-- ku_id references aii.ku_onto(id) in the aii schema

CREATE TABLE IF NOT EXISTS ku_layers (
    id          TEXT PRIMARY KEY,
    ku_id       TEXT NOT NULL,
    layer       TEXT NOT NULL CHECK (layer IN ('L0', 'L1', 'L2')),
    content     TEXT NOT NULL,
    token_count INT NOT NULL DEFAULT 0,
    model_used  TEXT,
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(ku_id, layer)
);

CREATE INDEX IF NOT EXISTS idx_kl_ku ON ku_layers(ku_id);
CREATE INDEX IF NOT EXISTS idx_kl_layer ON ku_layers(layer);

-- ── context_directory ────────────────────────────────────────────────────────
-- Virtual filesystem: viking://resources/数学/线性代数/xxx

CREATE TABLE IF NOT EXISTS context_directory (
    id              TEXT PRIMARY KEY,
    parent_id       TEXT REFERENCES context_directory(id) ON DELETE CASCADE,
    uri             TEXT NOT NULL UNIQUE,
    node_type       TEXT NOT NULL CHECK (node_type IN ('directory', 'substrate', 'ku', 'session', 'memory', 'skill')),
    ref_id          TEXT,
    l0_content      TEXT,
    l1_content      TEXT,
    depth           INT NOT NULL DEFAULT 0,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cd_uri ON context_directory(uri);
CREATE INDEX IF NOT EXISTS idx_cd_parent ON context_directory(parent_id);
CREATE INDEX IF NOT EXISTS idx_cd_type ON context_directory(node_type);
CREATE INDEX IF NOT EXISTS idx_cd_ref ON context_directory(ref_id);
CREATE INDEX IF NOT EXISTS idx_cd_depth ON context_directory(depth);

-- ── retrieval_trajectories ──────────────────────────────────────────────────
-- Phase 2 检索轨迹 (提前建表, Phase 2 直接可用)

CREATE TABLE IF NOT EXISTS retrieval_trajectories (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    query           TEXT NOT NULL,
    query_embedding FLOAT[1024],
    results         JSONB NOT NULL DEFAULT '[]',
    trajectory      JSONB NOT NULL DEFAULT '[]',
    total_ms        INT,
    result_count    INT DEFAULT 0,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rt_user ON retrieval_trajectories(user_id, created_at DESC);
-- trigram index requires pg_trgm extension; use simple btree prefix index instead
CREATE INDEX IF NOT EXISTS idx_rt_query ON retrieval_trajectories(left(query, 100));

-- ── agent_sessions (Phase 4 用) ─────────────────────────────────────────────
-- 注意: stratum.sessions 已存在(auth session), 所以 agent session 用 agent_sessions

CREATE TABLE IF NOT EXISTS agent_sessions (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    title           TEXT,
    status          TEXT NOT NULL DEFAULT 'active',
    message_count   INT DEFAULT 0,
    total_tokens    INT DEFAULT 0,
    commit_count    INT DEFAULT 0,
    pending_tokens  INT DEFAULT 0,
    keep_recent_count INT DEFAULT 0,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    meta_json       JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_asess_user ON agent_sessions(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_asess_status ON agent_sessions(status);

-- ── session_messages ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS session_messages (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES agent_sessions(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
    content         TEXT NOT NULL,
    parts_json      JSONB DEFAULT '[]',
    estimated_tokens INT DEFAULT 0,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sm_session ON session_messages(session_id, created_at);

-- ── session_archives ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS session_archives (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES agent_sessions(id) ON DELETE CASCADE,
    archive_index   INT NOT NULL,
    overview        TEXT,
    checkpoint      TEXT,
    message_count   INT,
    token_count     INT,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sa_session ON session_archives(session_id, archive_index);

-- ── long_term_memories ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS long_term_memories (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    memory_type     TEXT NOT NULL CHECK (memory_type IN (
                        'preference', 'experience', 'case', 'trajectory',
                        'skill', 'knowledge_gap', 'fact'
                    )),
    content         TEXT NOT NULL,
    source_session  TEXT,
    confidence      FLOAT DEFAULT 0.8,
    embedding       FLOAT[1024],
    tags            TEXT[] DEFAULT '{}',
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at      TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_ltm_user ON long_term_memories(user_id, memory_type);
CREATE INDEX IF NOT EXISTS idx_ltm_session ON long_term_memories(source_session);
CREATE INDEX IF NOT EXISTS idx_ltm_tags ON long_term_memories USING gin(tags);
