# A IMPLEMENTATION AUDIT — Phase 0

STATUS=AUDITED
BASELINE=c5f7afe16adc40c5869c5244a83f9e29c406d89c
TAG=bu2-v2.0-freeze

## A_MODEL 确认

```
BookSource
 ↓
SourceVersion
 ↓
ReadingRun
 ↓
ReadingEvidence
 ↓
KnowledgeUnitCandidate
```

- BookSource: 真实书籍身份（title/author/publisher/isbn/language/source_type）
- SourceVersion: 版本固定（checksum/format/page_count/metadata）
- ReadingRun: 阅读运行（复用 060 book_reading_run，source_id 语义指向 SourceVersion）
- ReadingEvidence: A仓核心证据（page_locator/chapter_locator/quote_span/context/parser_version/extractor_version）
- KnowledgeUnitCandidate: KU 候选（content/concept_hint/confidence/status: EXTRACTED/REVIEWED/ACCEPTED/REJECTED）

关系基数：
- BookSource 1:N SourceVersion
- SourceVersion 1:N ReadingRun
- ReadingRun 1:N ReadingEvidence
- ReadingEvidence 1:N KnowledgeUnitCandidate

## Pipeline 确认

| Stage | 名称 | 职责 |
|-------|------|------|
| Stage1 | Source Registration | 登记 BookSource |
| Stage2 | Source Snapshot | 登记 SourceVersion（checksum 固定） |
| Stage3 | Reading Run Creation | 创建 ReadingRun |
| Stage4 | Evidence Extraction | 生成 ReadingEvidence |
| Stage5 | KU Candidate Generation | 生成 KnowledgeUnitCandidate |
| Stage6 | Verification | 验证 provenance 完整性 |
| Stage7 | Human/Agent Review | accept/reject 候选 |
| Stage8 | Freeze | 冻结 A仓状态 |

## Schema Gap 确认

已有（060-066）：
- book_reading_run（060/065 状态机）
- reading_ledger（060）
- evidence_trajectory（061，B仓）
- knowledge_claims（020，B仓）

缺失（需 070+）：
- book_source
- source_version
- reading_evidence
- ku_candidate

## 约束确认

- A仓 authoritative raw book understanding repository
- No B仓 concept deduplication
- No C仓 derivation
- No automatic merging of Knowledge Units
- Preserve original book evidence
- Migration only additive
- No modification to BU2 060-066
- No production DB mutation
- All changes require tests

## 实施范围

- 070_a_repository_foundation.sql（additive）
- src/stratum/knowledge/a_repository/（models.py, types.py, repository.py, pipeline.py）
- tests/architecture/test_a_repository_contract.py（10 required tests）
- docs/book-understanding-2.0/A_IMPLEMENTATION_AUDIT.md（本文件）

A_IMPLEMENTATION_AUDIT=CONFIRMED
