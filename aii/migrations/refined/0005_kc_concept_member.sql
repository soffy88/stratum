-- ============================================================================
-- rf.refined_kc_concept — 主题KC 的【概念】成员(AII-KNOWLEDGE-FIRST-SPEC-001 改进二)
--
-- 为什么需要这张表:
--   Leiden 社区检测是在【概念-概念】图上跑的(refined_concept + refined_directed_edge),
--   所以"某个主题KC由哪些概念组成"才是聚类的原始产物。但 0001 的 refined_kc_member
--   只存 (kc_id, ku_id)——KU 是经 refined_ku_concept 反查出来的【衍生物】, 且一个 KU
--   可 touch 多个社区, 不是双射, 反查不回概念集合。
--
--   结果是 /api/graph/themes 为了给概念染色, 只能每次请求【重跑一遍 Leiden】再按
--   "size降序"的位置去对齐固化时的 kc_id。这个对齐在概念图变动后会错位, 而它唯一的
--   护栏是"cluster 数量 == theme 行数"——数量恰好没变而边界变了, 就会静默给出错的
--   主题染色(把 A 主题的颜色刷到 B 主题的概念上)。看裸真相: 那是在猜, 不是在读。
--
--   把聚类当时的概念归属如实存下来, 读接口直接读, 不重算不对齐, 错位的可能性归零。
--
-- ★不删 refined_kc_member: KU 成员是另一个真实的问题("这个主题涉及哪些KU"), 两张表
--   各答各的, 不是替代关系。
-- ============================================================================

CREATE TABLE IF NOT EXISTS rf.refined_kc_concept (
  kc_id      bigint REFERENCES rf.refined_theme_kc(kc_id)     ON DELETE CASCADE,
  concept_id bigint REFERENCES rf.refined_concept(concept_id) ON DELETE CASCADE,
  PRIMARY KEY (kc_id, concept_id)
);

CREATE INDEX IF NOT EXISTS idx_refined_kc_concept_concept
  ON rf.refined_kc_concept USING btree (concept_id);
