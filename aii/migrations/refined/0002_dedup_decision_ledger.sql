-- AII B仓 步骤2 · KU去重人工签核记录表(ledger)
-- AII-REFINED-REPO-MASTER-001 §6.3: dry_run 浮候选 → 人工门签核 → 落库前拦自信错合。
-- 性质: 操作性 provenance(记录"看似同点但人工裁定不合并/合并"的判定), 非四层知识有机体,
--       亦非设计§6.4砍掉的时序版本审计表。供步骤3 ETL 读取(已签核held_apart不再合并/不再复judge)。
-- raw_ku_a/b = A仓(aii_kg)的 ku_id; 独立容器无跨库FK, 故存 text(对齐隔离原则)。

CREATE TABLE IF NOT EXISTS rf.dedup_decision (
  decision_id   bigserial PRIMARY KEY,
  raw_ku_a      text NOT NULL,          -- A仓 ku_id
  raw_ku_b      text NOT NULL,          -- A仓 ku_id
  a_title       text,
  b_title       text,
  sim           real,                   -- dry_run 余弦近邻相似度
  verdict       text NOT NULL,          -- held_apart(剔/不合并) / merged(合并) / uncertain(安全阀保留)
  band          text,                   -- red(疑似错合) / yellow(边缘) / green(真同点) / uncertain
  reason        text,
  signed_off_by text,                   -- 签核人(经理人/CC)
  run_tag       text,                   -- dry_run 批次标识
  created_at    timestamptz DEFAULT now(),
  UNIQUE (raw_ku_a, raw_ku_b)
);

COMMENT ON TABLE rf.dedup_decision IS 'KU去重人工签核记录: dry_run候选的最终裁定(held_apart/merged/uncertain), 步骤3 ETL据此落库且不再复judge';
