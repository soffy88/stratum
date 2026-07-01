-- AII B仓 步骤4 M0 · concept canonical 人工签核记录表(ledger)
-- AII-REFINED-REPO-MASTER-001 §6.3: 概念归一 dry_run 浮候选 → 人工门签核 → 落 refined_concept 前拦自信错合。
-- 性质: 操作性 provenance(记录概念判同最终裁定); ★LLM判同非确定性(同对跨run裁决会变),
--       故签核决定必须 pin 在此(按 A仓 concept_id), M0落库照此应用, 不再凭单次run。
-- raw_concept_a/b = A仓(aii_kg) concept_onto.concept_id; 独立容器无跨库FK, 存 bigint。

CREATE TABLE IF NOT EXISTS rf.concept_decision (
  decision_id     bigserial PRIMARY KEY,
  raw_concept_a   bigint NOT NULL,        -- A仓 concept_id
  raw_concept_b   bigint NOT NULL,        -- A仓 concept_id
  a_name          text,
  b_name          text,
  sim             real,
  verdict         text NOT NULL,          -- merged(归一同一) / held_apart(剔,保持独立) / candidate
  band            text,                   -- green(真同一) / yellow(边缘剔) / ...
  reason          text,
  signed_off_by   text,
  run_tag         text,
  created_at      timestamptz DEFAULT now(),
  UNIQUE (raw_concept_a, raw_concept_b)
);

COMMENT ON TABLE rf.concept_decision IS 'concept canonical 人工签核记录: M0判同最终裁定(merged/held_apart), 落refined_concept据此, LLM非确定性故必须pin';
