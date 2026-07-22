-- ============================================================================
-- rf.dedup_decision — 人工"判同但保留分开"决策记录(held_apart), 供 refined_ingest_dryrun.py
-- 的 union-find 判同流程跳过这些对(宁冗余不误删, 即使相似度高也不强制并簇)。
--
-- ★补建: 原表在 2026-06-30 经济学首跑时手工建过(未入migration), 07-03 aii-refined-postgres
-- 容器重建时连同数据一起丢失, 之后 refined_ingest_dryrun.py 一直依赖它却无处可查——
-- math_prog 批次首次跑 dry-run 时才发现(UndefinedTableError)。现补进 migration, 空表起步
-- (没有任何脚本会自动写入, 是人工审核后手动 INSERT 的决策记录)。
-- ============================================================================

CREATE TABLE IF NOT EXISTS rf.dedup_decision (
  decision_id   bigserial PRIMARY KEY,
  raw_ku_a      text NOT NULL,
  raw_ku_b      text NOT NULL,
  verdict       text NOT NULL,      -- held_apart(判同但人工决定不并簇) / 其它以后再加
  why           text,
  created_at    timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_dedup_decision_pair ON rf.dedup_decision (raw_ku_a, raw_ku_b);
