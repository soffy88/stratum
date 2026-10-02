# BU2 CANONICAL BASELINE REPORT

TASK=BU2_FREEZE_COMMIT_AND_BASELINE
COMMIT_SHA=c5f7afe16adc40c5869c5244a83f9e29c406d89c
TAG=bu2-v2.0-freeze
SCHEMA=060-066
LEDGER=49
RUNTIME_AUTHORITY=PASS
SPEC_RECONCILIATION=PASS
FOUNDATION_TEST=38_PASS
BU_V2_TEST_SCOPE=56_PASS_1_SKIP
DB_MUTATION=0
MIGRATION_CHANGE_AFTER_FREEZE=0
BASELINE_STATUS=CANONICAL

## Phase 0 — STAGED_CONTENT_GATE

`git status --short` + `git diff --cached --name-status -M` + `git diff --cached --stat`:

- Staged: 6× R100 renames (052→060 … 057→065) + 1× A (066_bu2_p4_p9_repair.sql)
  + 4× A (BU2 freeze docs).
- No src/stratum/** staged. No tests/** staged. No migration content
  modifications staged.
- Pre-existing dirty files (aii/, src/stratum runtime, tests, legacy docs,
  output.txt) left untouched, not staged, not committed.

STAGED_CONTENT_GATE=PASS

## Phase 1 — MIGRATION_CONTENT_INTEGRITY

`git diff --cached --find-renames -- src/stratum/db/pg_migrations`:

- 060-065: `similarity index 100%` pure renames (0 content change) ✓
- 066: only new file (87 lines, from /dev/null) ✓

MIGRATION_CONTENT_INTEGRITY=PASS

## Phase 2 — FREEZE_DOC_ALIGNMENT

All 4 freeze docs present in `docs/book-understanding-2.0/`:
BU2_RUNTIME_AUTHORITY_SPEC.md, TEST_CONTRACT_DRIFT_REPORT.md,
BU2_SPEC_RECONCILIATION_REPORT.md, BU2_FINAL_FREEZE_REPORT.md.

- `grep -R "SCHEMA=060-066"` → 3 hits (AUTHORITY_SPEC, FINAL_FREEZE_REPORT,
  SPEC_RECONCILIATION_REPORT) ✓
- `grep -R "SPEC_RECONCILIATION=PASS"` → 2 hits (FINAL_FREEZE_REPORT,
  SPEC_RECONCILIATION_REPORT) ✓

FREEZE_DOC_ALIGNMENT=PASS

## Phase 3 — COMMIT

Commit created with message `feat(bu2): freeze Book Understanding 2.0 runtime authority`:

- COMMIT_SHA=c5f7afe16adc40c5869c5244a83f9e29c406d89c
- 11 files changed, 610 insertions(+): 4 freeze docs + 6 migration renames
  (100%) + 066 add. No source, no test, no other docs.

## Phase 4 — TAG_CREATE

Annotated tag created:

- TAG=bu2-v2.0-freeze → c5f7afe16adc40c5869c5244a83f9e29c406d89c
- Message: "BU2 schema 060-066 runtime authority freeze"
- `git show bu2-v2.0-freeze --stat` verified (11 files, 610 insertions).

TAG_CREATE=PASS

## Phase 5 — FINAL FREEZE_STATUS

- `git log -1 --oneline` → c5f7afe feat(bu2): freeze Book Understanding 2.0
  runtime authority
- `git tag --list "bu2-v2.0-freeze"` → bu2-v2.0-freeze
- `git status --short` → only pre-existing dirty files remain; no BU2
  uncommitted content.

FINAL_FREEZE_STATUS=PASS

## Baseline Contents (canonical)

- Schema authority: migrations 060-066 (065 = P1 10-state
  book_reading_run constraint; 066 = P6 gap lifecycle + verification_artifacts
  PASS/FAIL/BLOCKED)
- Runtime authority: PipelineRunState / GapStatus / VerificationOutcome enums
  (src/stratum/knowledge/bu_v2_models.py) + VALID_TRANSITIONS
  (bu_v2_pipeline.py) + VALID_GAP_TRANSITIONS / BLOCKING_GAP_STATUSES
  (bu_v2_repositories.py)
- Production: DB=aii_kg, migration ledger=49, 16 BU2 tables in stratum
  schema, live CHECK constraints match 065/066 exactly
- Spec docs: BU2_RUNTIME_AUTHORITY_SPEC.md, TEST_CONTRACT_DRIFT_REPORT.md,
  BU2_SPEC_RECONCILIATION_REPORT.md, BU2_FINAL_FREEZE_REPORT.md

BASELINE_STATUS=CANONICAL
