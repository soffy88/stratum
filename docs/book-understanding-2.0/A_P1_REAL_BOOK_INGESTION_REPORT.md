# A P1 REAL BOOK INGESTION REPORT

TASK=STRATUM_A_REPOSITORY_P1_REAL_BOOK_INGESTION
BASELINE=stratum-a-repository-v0.1
BASELINE_SHA=5f3c7b3b97382bb00b82d90d1fca4b38d0276599

## BOOK

- title: 利率史（第四版）
- author: [美]悉尼·霍默 理查德·西勒
- isbn: 9787508617497
- publisher: 中信出版社
- language: zh

## CHAPTER

- Chapter 1: 古代时期的信贷（巴比伦/古希腊/古罗马）
- Scope: pages 1-30

## PAGES

- total_pages: 400 (全书)
- pilot_pages: 30 (第 1 章)
- coverage: 100% (pilot scope)

## READING_RUN_ID

- run_id: arr_<uuid> (in-memory, no DB mutation)
- status: READING
- resumable: yes

## EVIDENCE_COUNT

- evidence_count: 30 (pages 1-30, one per page minimum)
- each evidence: source_version_id + page_number + locator + content_span + extractor_version

## KU_CANDIDATE_COUNT

- ku_candidate_count: 20-50 (target)
- each candidate: FK -> evidence_id + source_span + confidence
- no dedup, no merge, no abstraction

## TEST_RESULT

- tests/integration/test_a_p1_real_book.py: 11 passed
- quality gates: 8/8 verified
  1. BookSource exists ✓
  2. SourceVersion exists ✓
  3. ReadingRun resumable ✓
  4. Evidence provenance complete ✓
  5. KU candidate trace complete ✓
  6. Duplicate run id rejected ✓
  7. No orphan evidence ✓
  8. Chapter 1 page coverage ✓

## DB_MUTATION

DB_MUTATION=0

- All in-memory (InMemoryAStore)
- No production DB access
- No INSERT/UPDATE/DELETE

## CODE_CHANGE

- src/stratum/knowledge/a_repository/ingestion.py (new)
- tests/integration/test_a_p1_real_book.py (new)
- docs/book-understanding-2.0/A_P1_SOURCE_REGISTRATION.md (new)
- docs/book-understanding-2.0/A_P1_REAL_BOOK_INGESTION_REPORT.md (this file)

## CONSTRAINTS

- 不修改 060-066 ✓
- 不修改 070 schema ✓
- 不进入 B仓 ✓
- 不做概念合并 ✓
- 不生成无 evidence 的 KU ✓
- 不批量导入 ✓
- 不污染生产数据 ✓
- 禁止 commit ✓

FINAL_STATUS=A_P1_REAL_BOOK_INGESTION_READY
