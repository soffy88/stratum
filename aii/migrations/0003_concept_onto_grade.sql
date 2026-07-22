-- ============================================================================
-- aii.concept_onto.grade —— 概念也要受 grade 铁律
--
-- 缺口(2026-07-20 发现): refined_ku / refined_theme_kc / refined_directed_edge /
-- cx.decision_case 全都有 grade, 唯独 A 仓的 concept_onto 没有 —— 于是"这个概念是
-- 从书里抠出来的、还是 LLM 起的名、还是人确认过的"三者在库里长得一模一样。
--
-- 触发它的具体场景: math_prog 概念层接入。②规划审核给定理/定义起的名, 实测编造率
-- 约 8%(样本12条中1条 "Dimension as Number of Bases" —— 维数是基的大小, 不是基的
-- 个数, 数学上就是错的)。这种错读起来像模像样、程序 checker 发现不了、只有懂数学的
-- 人能看出 —— 原则二的教科书情形: 没有不能撒谎的自动裁判 → 留人。
-- 所以它们必须落在一个【明确不可信】的层里, 而不是和人工确认过的概念混在一起。
--
--   candidate  = 默认。AI 命名/抽取产出, 未经人工确认。★不参与自动合并(判同),
--                编造的概念到不了 confirmed, 只是躺着等确认或交叉印证
--                (同名概念在另一本书独立出现 = 交叉印证, 是自动升级的线索而非依据)。
--   confirmed  = 人工确认过, 或有足够交叉证据。可参与判同/上层结构。
--
-- ★默认值给 candidate 而不是 confirmed: 存量 17771 个概念也不是人工确认过的,
--   把它们默认成 confirmed 等于凭空发一顶可信帽子。宁可全体从 candidate 起步。
-- ============================================================================

ALTER TABLE aii.concept_onto
  ADD COLUMN IF NOT EXISTS grade text NOT NULL DEFAULT 'candidate'
    CHECK (grade = ANY (ARRAY['candidate'::text, 'confirmed'::text]));

CREATE INDEX IF NOT EXISTS idx_concept_onto_grade
  ON aii.concept_onto USING btree (grade);

COMMENT ON COLUMN aii.concept_onto.grade IS
  'candidate=AI产出未经确认(默认, 不参与自动判同合并) / confirmed=人工确认或交叉印证。见 migrations/0003 注释。';
