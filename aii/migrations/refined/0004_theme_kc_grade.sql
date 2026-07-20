-- ============================================================================
-- rf.refined_theme_kc.grade — 主题 KC 是 AII 综合物(Leiden 聚类 + LLM 自动命名),
-- 同 rf.refined_ku.grade / rf.refined_directed_edge.grade 的 grade 铁律:
-- 综合产物默认不可信, 必须显式标记, 不能悄悄看起来像定论。
--   unverified = 默认(算法聚类 + LLM 命名, 未经人工审)
--   verified   = 人工看过聚类边界+主题名, 确认合理
-- ============================================================================

ALTER TABLE rf.refined_theme_kc
  ADD COLUMN IF NOT EXISTS grade text NOT NULL DEFAULT 'unverified'
    CHECK (grade = ANY (ARRAY['unverified'::text, 'verified'::text]));
