-- 0008: 论文向 BU 字段(2026-07-16)
-- 背景: bu_onto 原为教材(book understanding)设计, 字段偏"讲透概念/学习线索"。
-- 6篇跨类型论文实证(理论经济/计量/博弈/优化/金融/ML)一致结论: 论文需要两层——
--   「1」论文理解(人读): 复用现有 overview_oneline / problem_statement / main_claims / positional_summary + 新增 limitations
--   「skill」agent 可调用对象: 结构化存 method/preconditions/use_when/boundary/key_results/reusable_artifacts...
-- 概念一律只存指针(去重在概念层), bu 里不复述教材概念。
-- 教材路径零改动: 这些列对 doc_type='textbook' 行保持 NULL。

ALTER TABLE aii.bu_onto ADD COLUMN IF NOT EXISTS agent_skill jsonb;   -- 「skill」层: agent 可调用结构化对象(见下方键约定)
ALTER TABLE aii.bu_onto ADD COLUMN IF NOT EXISTS limitations jsonb;   -- 「1」层: 作者自陈局限/边界(text[] 语义, 存 jsonb 数组)
ALTER TABLE aii.bu_onto ADD COLUMN IF NOT EXISTS authors text;        -- 书目缺口: 作者
ALTER TABLE aii.bu_onto ADD COLUMN IF NOT EXISTS venue_year text;     -- 书目缺口: 出处/年份

COMMENT ON COLUMN aii.bu_onto.agent_skill IS
  'doc_type=paper 专用。agent 可调用对象, 键: contribution_type(method|empirical|impossibility|framework|survey), '
  'method{approach,steps,inputs,outputs}, preconditions[{assumption,failure_if_violated}], '
  'use_when[], do_not_use_when[], boundary_conditions[{claim,direction,holds_when,reverses_when}], '
  'key_results[{metric,value,baseline,dataset}], reusable_artifacts[{name,what,where}], '
  'dependencies[], references_concepts[](通用概念指针,不复制), coined_terms[{term,definition}](本篇新造术语)。';
COMMENT ON COLUMN aii.bu_onto.limitations IS 'doc_type=paper: 作者自陈的局限/失效边界(jsonb 字符串数组)。';
