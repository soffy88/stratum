-- 018_decision_intelligence.sql — semantica 能力 3O 化: 决策智能 / 溯源 (P0)
-- decision_ledger / kg_reasoning / provenance_w3c operator 的持久层 (PostgreSQL)

-- ── 决策账本: 决策是一等对象 ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS decision_ledger_decisions (
    decision_id   TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL,
    category      TEXT NOT NULL DEFAULT 'general',
    scenario      TEXT NOT NULL,
    reasoning     TEXT NOT NULL DEFAULT '',
    outcome       TEXT NOT NULL,
    confidence    DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    decision_maker TEXT NOT NULL DEFAULT 'master',
    decision_ts   TIMESTAMP NOT NULL DEFAULT NOW(),
    source_refs   JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata      JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_dl_decisions_user ON decision_ledger_decisions(user_id, decision_ts DESC);
CREATE INDEX IF NOT EXISTS idx_dl_decisions_cat ON decision_ledger_decisions(user_id, category);

-- ── 因果链: CAUSED / INFLUENCED / PRECEDENT_FOR ─────────────────────
CREATE TABLE IF NOT EXISTS decision_ledger_relations (
    id                TEXT PRIMARY KEY,
    user_id           TEXT NOT NULL,
    src_id            TEXT NOT NULL REFERENCES decision_ledger_decisions(decision_id) ON DELETE CASCADE,
    dst_id            TEXT NOT NULL REFERENCES decision_ledger_decisions(decision_id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL CHECK (relationship_type IN ('CAUSED','INFLUENCED','PRECEDENT_FOR')),
    metadata          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at        TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_dl_relations_src ON decision_ledger_relations(user_id, src_id);
CREATE INDEX IF NOT EXISTS idx_dl_relations_dst ON decision_ledger_relations(user_id, dst_id);

-- ── W3C PROV-O 溯源 (通用实体/活动/关系) ─────────────────────────────
CREATE TABLE IF NOT EXISTS decision_provenance (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL,
    kind       TEXT NOT NULL,  -- used | wasGeneratedBy | wasDerivedFrom | wasAttributedTo
    src        TEXT NOT NULL,
    dst        TEXT NOT NULL,
    attrs      JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_dl_prov_user ON decision_provenance(user_id, created_at DESC);
