# A IMPLEMENTATION PLAN — A仓流水实施计划

STATUS=PLANNED
BASELINE=bu2-v2.0-freeze
SCOPE=additive implementation, no modification to 060-066 / runtime authority

## 拆分

### P0 — Book Ingestion

- input: PDF/EPUB/HTML 文件 + 书籍元数据
- output: book_source_id, source_version_id, run_id
- tables: book_source (070), source_version (071), book_reading_run (已有)
- tests: test_ingestion.py — 登记幂等性、checksum 重复检测、元数据完整性
- migration: 070_book_source.sql, 071_source_version.sql

### P1 — Parser

- input: 已登记 SourceVersion 的 PDF 文件
- output: reading_ledger 条目（chapter/section/page/fragment/figure/table/equation）
- tables: reading_ledger (已有, 060)
- tests: test_parser_contract.py — 结构解析覆盖率、item_type 正确性、page_number 范围
- migration: 无（复用 060）

### P2 — Reading Ledger Integration

- input: Parser 输出的 reading_ledger 条目
- output: ledger 状态流转（UNSEEN -> PARSED -> READ -> INTERPRETED）
- tables: reading_ledger (已有, 060)
- tests: test_ledger_integration.py — 状态流转合法性、coverage 计算
- migration: 无（复用 060）

### P3 — Evidence Extractor

- input: READ/INTERPRETED 状态的 ledger 项
- output: ReadingEvidence 行（page_locator/chapter_locator/quote_span/context/parser_version/extractor_version）
- tables: reading_evidence (072)
- tests: test_evidence_extractor.py — provenance 完整性、quote_span 非空、source_version_id 必填
- migration: 072_reading_evidence.sql

### P4 — KU Candidate Generator

- input: ReadingEvidence 行
- output: KnowledgeUnitCandidate 行（content/concept_hint/confidence/status=EXTRACTED）
- tables: ku_candidate (073)
- tests: test_ku_candidate.py — candidate 必须挂 evidence、status 初始为 EXTRACTED、confidence 范围 [0,1]
- migration: 073_ku_candidate.sql

### P5 — Review Workflow

- input: EXTRACTED 状态的 KU Candidate
- output: candidate status 终态（REVIEWED -> ACCEPTED / REJECTED）
- tables: ku_candidate (073)
- tests: test_review_workflow.py — 状态机合法性、禁止 EXTRACTED 直接到 ACCEPTED、审核记录
- migration: 无（复用 073）

### P6 — Evaluation

- input: Pilot 书籍（利率史第 1 章）完整 A仓数据
- output: 覆盖率报告、provenance 完整性报告、KU 候选质量抽样
- tables: 无新表
- tests: test_pilot_acceptance.py — 100% page accounting、evidence provenance、KU traceability
- migration: 无

## 依赖关系

```
P0 -> P1 -> P2 -> P3 -> P4 -> P5 -> P6
```

- P0 是基础（无 book_source 无法登记 version）
- P1/P2 复用已有 reading_ledger，无新 migration
- P3/P4 引入新表（072/073），是 A仓核心
- P5 依赖 P4 的候选
- P6 是验收，依赖全部前置阶段

## 约束

- 不修改 060-066 migration
- 不修改 BU2 foundation schema
- 不修改 runtime authority
- 不修改生产历史数据
- 不执行 destructive migration
- 新能力必须 additive（070+）

## 每阶段验收标准

| 阶段 | 验收 |
|------|------|
| P0 | 同 checksum 不重复登记；元数据完整 |
| P1 | 第 1 章 100% 结构项登记 |
| P2 | 状态流转合法；coverage 可计算 |
| P3 | 每条 evidence 有完整 provenance |
| P4 | 每条 candidate 挂 evidence；status=EXTRACTED |
| P5 | 审核决定有记录；状态机合法 |
| P6 | 4 项 acceptance 全过 |

IMPLEMENTATION_PLAN_READY
