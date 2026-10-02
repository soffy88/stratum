# A P2 FREEZE REPORT — A仓证据质量层冻结

TASK=STRATUM_A_REPOSITORY_P2_QUALITY_FREEZE
BASELINE=stratum-a-p1-first-book-v0.1 (COMMIT=389d212)

## PIPELINE

```
ReadingEvidence
     |
     v
EvidenceQuality
     |
     v
KU Candidate (classification)
```

A仓不做世界理解。A仓只保存可验证理解单元。

## SOURCE_LOCATOR

SOURCE_LOCATOR=PASS

- spec: `docs/book-understanding-2.0/A_SOURCE_LOCATOR_SPEC.md`
- canonical `EvidenceLocator`: source_type, source_id, content_hash,
  logical_locator, physical_locator, line_range, page_number
- logical page != physical page — two coordinate systems, never
  interchangeable; `logical_locator` is the durable address
- persisted locators are frozen (Rule 3): re-anchoring is a new evidence
  row, never an update
- `locator_score` table (§5) implemented and asserted
- §6 policy recorded at this freeze: logical locator always accepted;
  physical page optional; for a markdown source `line_range` outranks
  `physical_page`; no schema change

## EVIDENCE_QUALITY

EVIDENCE_QUALITY=PASS

- migration `071_a_evidence_quality.sql` — additive only, re-runnable
- `stratum.evidence_quality`: one row per evidence row,
  `evidence_id TEXT NOT NULL UNIQUE`, four scores in [0,1], append-only
- scores: source_trace, locator, completeness, confidence
- `ku_candidate` gains `classification` + `classified_at` as additive
  columns with a closed CHECK list
- quality rows are never overwritten (`QualityViolation`)

## KU_CLASSIFICATION

KU_CLASSIFICATION=PASS

- `KIClassification`: FACT / EVENT / CONCEPT / RELATION / ARGUMENT
- classification reads the candidate and its own evidence, returns a type
- it never compares two candidates and never writes a conclusion
- migration CHECK list and Python enum asserted equal (no drift)
- 17/17 candidates classified, 0 unclassified

## BOOK

- title: 利率史（第四版）
- chapter: 第一章 古代时期的信贷
- source_version: sv_f548f51a5df5 (PDF, PDF-v1, 594 pages)
- reading_run: arr_d0d1473d79fc (READING)

## EVIDENCE_COUNT

EVIDENCE_COUNT=17

## QUALITY_COUNT

QUALITY_COUNT=17

## TRACEABILITY

TRACEABILITY=100%

- 17/17 evidence rows have a quality row (17/17 distinct evidence_id)
- 17/17 candidates resolve to their own evidence and are classified
- orphan_quality: 0
- unclassified_candidates: 0
- overall quality: source_trace 1.0, locator 1.0, completeness 1.0,
  confidence 1.0

Chain verified for every candidate:

```
evidence
  |
  + quality
  |
  + candidate (classification)
```

## REPLAY

REPLAY=PASS

- all IDs content-derived (sha256-truncated)
- `report(build_quality_baseline())` is byte-identical across
  independent runs
- re-applying the quality stage over a processed store adds no rows:
  `store.quality`, `_quality_by_evidence` and every evidence locator are
  unchanged
- re-classifying a candidate yields the same value
- no locator moves on replay

## AUTHORITY

AUTHORITY=PASS

- A仓 allows: append quality row, append classification
- A仓 forbids: quality overwrite, classification overwrite, candidate
  merging, conclusion writing (all raise `QualityViolation`)
- no external authority reference in P2 code: `quality.py`,
  `quality_runner.py` and migration 071 name no foreign table and no
  foreign repository
- 071 references only `stratum.reading_evidence`
- P1 frozen commit 389d212 untouched (no amend, no rebase); the P2
  changes to `ingestion.py` / `types.py` / `freeze_runner.py` are purely
  additive (two enum members, two optional candidate fields, two store
  slots, five locator keys)

## TEST

- tests/architecture/test_a_repository_contract.py: 22 passed
- tests/architecture/test_a_repository_p2_quality.py: 33 passed
- tests/integration/test_a_authority_freeze.py: 22 passed
- tests/integration/test_a_p1_real_book.py: 11 passed
- A-suite total: 88 passed

P2 coverage — 1 quality requires evidence, 2 evidence_id unique,
3 quality append-only, 4 classification enum, 5 runner deterministic,
6 replay unchanged, 7 no external authority reference, 8 locator
compatibility.

## DB_MUTATION

DB_MUTATION=071 only

- migration 071 is the sole schema artifact and is not executed against
  any database at this freeze
- all execution in-memory (`InMemoryAStore`); no production DB access
- migrations 060-066 and 070 not edited
- BU2_MUTATION=0, B_MUTATION=0

## KNOWN LIMITATION

Recorded, not fixed at this freeze:

- The P2 classifier is a deliberately shallow marker heuristic, and its
  numeric markers (`年`, `法典`, `上限`) are tested before its event
  markers. On the frozen baseline it therefore never returns EVENT,
  RELATION or ARGUMENT, and agrees with the corpus's declared
  `candidate_type` on 11/17 rows (breakdown: FACT 11, CONCEPT 6).
  Counts, traceability and orphan-freedom are unaffected; the
  classification is a type tag, not an interpretation.
- `classified_at` holds the quality version string in the in-memory
  model while migration 071 declares it `TIMESTAMP`. Naming, not
  behaviour, is wrong — flagged for the schema review.

STATUS=FROZEN