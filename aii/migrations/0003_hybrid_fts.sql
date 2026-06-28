-- AII 混合检索: 为 ku_onto 增加全文检索(lexical)通道, 与 pgvector(dense)做 RRF 融合.
-- 动机: 纯 dense 检索对专名/精确术语召回弱; 加 Postgres 内建 FTS(english)补词法召回.
--   natural_text 为英文(KU 双语, 中文在 natural_text_zh); 中文查询走 dense, 英文/专名走 lexical.
-- 不依赖 pg_trgm 等扩展, 仅用内建 to_tsvector/GIN.
-- 幂等: IF NOT EXISTS.

-- 生成列: title + natural_text 的 english tsvector(随行自动维护, 无需触发器)
ALTER TABLE aii.ku_onto
  ADD COLUMN IF NOT EXISTS fts tsvector
  GENERATED ALWAYS AS (
    to_tsvector('english', coalesce(title, '') || ' ' || coalesce(natural_text, ''))
  ) STORED;

CREATE INDEX IF NOT EXISTS idx_ku_onto_fts ON aii.ku_onto USING gin (fts);
