-- AII 跨块共现表 (migration / 重建用)
-- 守 VHDX 数据丢失教训: DDL 固化进 repo.
-- 共现 ≠ 边 (正交): 边=edge_onto(LLM识别的真实关系); 共现=共含概念的纯计算联系(无方向).
-- 强度: weak(共享1概念) / medium(共享≥2) / strong(共享≥2 且 semantic_sim>=阈值).
-- 由 aii.service.cooccurrence.compute_cooccurrence 纯计算填充 (0 LLM).
-- 前置依赖: pgvector (semantic_sim 用 embedding 余弦).

CREATE TABLE IF NOT EXISTS aii.ku_cooccurrence (
    substrate_id          text NOT NULL,
    ku_a                  text NOT NULL,
    ku_b                  text NOT NULL,
    shared_concept_count  int  NOT NULL,
    semantic_sim          real,
    strength              text NOT NULL,
    PRIMARY KEY (substrate_id, ku_a, ku_b)
);

CREATE INDEX IF NOT EXISTS idx_cooc_sub_strength ON aii.ku_cooccurrence(substrate_id, strength);
