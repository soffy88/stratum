# A IMPLEMENTATION PHASE 0 REPORT

TASK=STRATUM_A_REPOSITORY_IMPLEMENTATION_PHASE_0
BASELINE=c5f7afe16adc40c5869c5244a83f9e29c406d89c
TAG=bu2-v2.0-freeze

## MIGRATION

070_status=CREATED

- 070_a_repository_foundation.sql
- 5 tables: book_source, source_version, reading_run, reading_evidence, ku_candidate
- additive only: CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS
- no DROP / ALTER / DELETE / UPDATE
- no modification to 060-066

## SCHEMA

tables=book_source,source_version,reading_run,reading_evidence,ku_candidate

fk=
- source_version.book_source_id -> book_source.id
- reading_run.source_version_id -> source_version.id
- reading_evidence.reading_run_id -> reading_run.id
- ku_candidate.reading_run_id -> reading_run.id
- ku_candidate.evidence_id -> reading_evidence.id

indexes=
- idx_book_source_title
- idx_source_version_book, idx_source_version_file_hash
- idx_reading_run_source_version, idx_reading_run_status
- idx_reading_evidence_run, idx_reading_evidence_page
- idx_ku_candidate_run, idx_ku_candidate_evidence

## PIPELINE

stages=register,snapshot,read,extract,candidate,verify,freeze

- ARepositoryPipeline (src/stratum/knowledge/a_repository/pipeline.py)
- Input: SourceVersion -> Output: ReadingRun
- Every stage: emits PipelineEvent, persists state, resumable, idempotent
- No max_rounds. No coordinator slicing.
- Repository authority: BookSourceRepository, SourceVersionRepository,
  ReadingRunRepository, EvidenceRepository, KUCandidateRepository
- No direct SQL from service layer

## TEST

architecture=22_PASS

- tests/architecture/test_a_repository_contract.py
- 10 required contract tests + 12 spec-invariant tests
- FK chain, resume, duplicate rejection, evidence immutability,
  no-dedup, state transition, migration additive, no B/C dependency

## DB_MUTATION

DB_MUTATION=0

- Migration file created but NOT applied to production DB
- No INSERT / UPDATE / DELETE / migration upgrade executed

## CODE_CHANGE

CODE_CHANGE=additive_only

New files:
- src/stratum/db/pg_migrations/070_a_repository_foundation.sql
- src/stratum/knowledge/a_repository/__init__.py
- src/stratum/knowledge/a_repository/types.py
- src/stratum/knowledge/a_repository/models.py
- src/stratum/knowledge/a_repository/repository.py
- src/stratum/knowledge/a_repository/pipeline.py
- tests/architecture/test_a_repository_contract.py
- docs/book-understanding-2.0/A_IMPLEMENTATION_AUDIT.md

No modification to:
- BU2 migrations 060-066
- BU2 runtime authority (bu_v2_pipeline.py, bu_v2_models.py, bu_v2_repositories.py)
- B仓 files
- C仓 files
- production schema

## COMMIT

COMMIT=PENDING

- Changes are in worktree, not yet committed
- Awaiting commit instruction

## FINAL_STATUS

FINAL_STATUS=READY_FOR_COMMIT

- 070 migration: additive, 5 tables, FK complete, indexes complete
- Domain model: ORM-aligned, repository authority, no direct SQL
- Pipeline: 7 stages, event-emitting, resumable, idempotent
- Tests: 22 passed (10 required + 12 spec invariants)
- Scope: only A repository code + A tests + A docs + 070 migration
