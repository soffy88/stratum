# A P1 FREEZE REPORT — 首次真实书籍阅读链冻结

TASK=STRATUM_A_REPOSITORY_P1_FREEZE_REAL_BOOK_CHAIN
BASELINE=stratum-a-repository-v0.1

## BOOK

- title: 利率史（第四版）
- author: [美]悉尼·霍默 理查德·西勒
- isbn: 9787508617497
- chapter: 第一章 古代时期的信贷
- pages: 1-10 (coverage 100%)
- book_source_id: bs_04a94146a35f

## SOURCE_VERSION

- id: sv_f548f51a5df5
- checksum: 4125ee83a0bebeafab0260123278135d773d525461011295297645002b182449
- version: PDF-v1
- format: PDF
- page_count: 594

## READING_RUN

- id: arr_d0d1473d79fc
- status: READING
- transitions: CREATED → SNAPSHOTTED → READING

## EVIDENCE_COUNT

- 17 evidence rows
- all carry: reading_run_id, source_version_id, page_number, locator,
  content_span, extractor_version
- orphan_evidence: 0
- page coverage: 10/10 = 100%

## KU_COUNT

- 17 KU candidates
- all carry: evidence_id, reading_run_id, confidence, source_span
- orphan_candidates: 0
- all status: EXTRACTED (no auto-merge, no dedup)

## PROVENANCE

PROVENANCE=PASS

- every evidence traceable to run + version + page + locator + span
- every candidate traceable to evidence
- zero orphans

## REPLAY

REPLAY=PASS

- same checksum resolves to existing SourceVersion (no duplicate)
- replay skips all 17 existing evidence (fingerprint unchanged)
- replay skips all 17 existing candidates
- existing ReadingRun resumes (status READING preserved)
- baseline reproducible: two independent executions yield identical IDs

## AUTHORITY

AUTHORITY=PASS

- A仓 allows: append evidence, append candidate
- A仓 forbids: evidence overwrite, candidate overwrite, auto-merge
  (enforced by AuthorityViolation; no update/delete on EvidenceRepository)
- no B仓 dependency: no knowledge_claims reference in a_repository package
- 070 schema has no FK into B仓/BU2 tables

## REPRODUCIBILITY

All object IDs are content-derived (sha256-truncated). Re-executing
`freeze_runner.build_baseline()` yields byte-identical IDs and counts,
verified across independent runs and asserted in
`test_baseline_is_reproducible`.

## TEST

- tests/integration/test_a_authority_freeze.py: 22 passed
- tests/integration/test_a_p1_real_book.py: 11 passed
- tests/architecture/test_a_repository_contract.py: 22 passed
- A-suite total: 55 passed

Note: `tests/integration/test_cross_corpus_block.py` has pre-existing
`ulid.ULID` collection errors, unrelated to A仓 (verified present with
A仓 work stashed).

## DB_MUTATION

DB_MUTATION=0

- All execution in-memory (InMemoryAStore)
- No production DB access
- No migration executed

STATUS=FROZEN