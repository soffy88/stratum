-- AII global 检索修复: 为 kc_onto(社区/知识簇摘要)增加向量列.
-- 动机: global "综述/体系"问题的正解是社区摘要(GraphRAG global search), 但 kc_onto 无向量,
--   旧 search_synthesis_kus() 恒返回空 → global 路径死. 加向量列后可对 KC 摘要做语义检索.
-- 维度 1024(BGE-M3, 与 ku_onto.embedding 一致). 幂等.

ALTER TABLE aii.kc_onto ADD COLUMN IF NOT EXISTS embedding vector(1024);

CREATE INDEX IF NOT EXISTS idx_kc_onto_embedding
  ON aii.kc_onto USING hnsw (embedding vector_cosine_ops);
