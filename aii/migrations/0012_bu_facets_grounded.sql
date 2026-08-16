-- 0012: BU 七项书级理解 → 证据挂接版(2026-08-14)
-- 背景: 原七项(soul/positioning/question/skeleton/thinking/for_whom/boundary)是 LLM 单次调用的
--   抽象文本, 无依据、无定位、无可核验性("太简陋")。升级后每项 = {text, basis, ku_ids,
--   evidence(代码按 KU grade 计算), grades, excerpts(代码注入逐字切片, 0-LLM)}。
--   兼容: facets_zh/facets_en 保留扁平文本(旧前端继续可用); 新前端读 facets_grounded 渲染依据+证据。
ALTER TABLE aii.bu_onto ADD COLUMN IF NOT EXISTS facets_grounded jsonb;

COMMENT ON COLUMN aii.bu_onto.facets_grounded IS
  '七项书级理解的证据挂接版: [{key,text,basis,ku_ids[],evidence,grades[],excerpts[{text,ku_id,locator}]}]。'
  'basis=判断依据(依据哪些KC/枢纽/KU); evidence 由代码按 KU grade 重算(LLM 无权); '
  'excerpts 为逐字原文切片(代码从 grounded_by quote 或 0-LLM 抠原文注入)。'
  '质量门见 scripts/bu_learning_gate.py::validate_bu_facets; 记录并入 bu_onto.bu_quality.facets。';
