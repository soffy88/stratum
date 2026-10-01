# A REPOSITORY START REPORT

TASK=STRATUM_A_REPOSITORY_REAL_BOOK_UNDERSTANDING_PIPELINE_START
BASELINE=bu2-v2.0-freeze
STATUS=COMPLETE

## Phase Results

### A_MODEL_SPEC
- DEFINED: `docs/book-understanding-2.0/A_REPOSITORY_SPEC.md`
- 核心对象：BookSource -> SourceVersion -> ReadingRun -> ReadingEvidence -> KnowledgeUnitCandidate
- KU Candidate status: EXTRACTED / REVIEWED / ACCEPTED / REJECTED
- 明确不做：B仓概念去重 / C仓推理生成 / 本性计算

### A_PIPELINE_SPEC
- DEFINED: `docs/book-understanding-2.0/A_PIPELINE_SPEC.md`
- 固定流水：INPUT -> INGESTION -> PARSER -> READING_LEDGER -> EVIDENCE_EXTRACTION -> KU_EXTRACTION -> HUMAN/AGENT_REVIEW -> A仓完成
- 复用 060 reading_ledger；新增 070+ additive

### A_SCHEMA_GAP
- AUDITED: `docs/book-understanding-2.0/A_SCHEMA_GAP_REPORT.md`
- 已有：book_reading_run / reading_ledger / evidence_trajectory / knowledge_claims
- 缺失：book_source / source_version / reading_evidence / ku_candidate
- SCHEMA_EXTENSION_REQUIRED=yes（070+，禁止修改 060-066）

### PILOT_SPEC
- READY: `docs/book-understanding-2.0/A_FIRST_BOOK_PILOT.md`
- 书籍：利率史（第四版）/ Sydney Homer & Richard Sylla / ISBN 9787508617497
- 范围：第 1 章（约 30-50 页），目标 20-50 条 KU 候选
- Acceptance：100% page accounting / ledger coverage / evidence provenance / KU traceability
- 禁止：批量导入

### IMPLEMENTATION_PLAN
- READY: `docs/book-understanding-2.0/A_IMPLEMENTATION_PLAN.md`
- P0 Book Ingestion -> P1 Parser -> P2 Reading Ledger -> P3 Evidence Extractor -> P4 KU Candidate -> P5 Review Workflow -> P6 Evaluation
- 每阶段含 input / output / tables / tests

## Architecture Tests

- `tests/architecture/test_a_repository_contract.py` — 12 passed
- 覆盖：provenance exists / evidence requires source / KU candidate requires evidence / no B/C dependency / migration freeze / pilot constraint
- 禁止测试内容质量评分（未包含）

## Invariants

CODE_CHANGE=0
DB_MUTATION=0
MIGRATION_CHANGE=0

- 未修改 060-066 migration
- 未修改 BU2 foundation schema
- 未修改 runtime authority
- 未修改生产历史数据
- 未执行 destructive migration
- 新能力全部 additive（设计 070+）

## Next Step

NEXT_STEP=IMPLEMENT_P0_BOOK_INGESTION

A_REPOSITORY_PIPELINE_READY
