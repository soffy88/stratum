# BU2 SPEC RECONCILIATION REPORT

TASK=BU2_SPEC_RECONCILIATION_AND_FINAL_FREEZE
DB=aii_kg
MIGRATION_LEDGER=49
BU2_SCHEMA=060-066
BU2_RUNTIME=LIVE

## Verdict

SPEC_RECONCILIATION=PASS

PRODUCTION_SCHEMA_AUTHORITY=PASS

P1_STATUS:
OLD_SPEC=STALE
RUNTIME_AUTHORITY=PASS

P6_STATUS:
OLD_SPEC=STALE
RUNTIME_AUTHORITY=PASS

CODE_CHANGE=0
MIGRATION_CHANGE=0
DB_MUTATION=0

## Evidence

### Production schema authority (065/066)

- `src/stratum/db/pg_migrations/065_bu2_pipeline_state.sql` —
  `book_reading_run_status_check` defines the 10 P1 states:
  `CREATED`, `PERCEIVED`, `INSPECTED`, `DEEP_READ_COMPLETE`,
  `CHAPTER_MODELLED`, `BOOK_INTEGRATED`, `VERIFICATION_PENDING`, `VERIFIED`,
  `COMPRESSION_TESTED`, `FAILED`; adds `failure_reason`.
- `src/stratum/db/pg_migrations/066_bu2_p4_p9_repair.sql` —
  `understanding_gaps_status_check` defines the P6 lifecycle:
  `OPEN`, `TARGETED_REREAD_REQUIRED`, `REREAD_IN_PROGRESS`,
  `TARGETED_REREAD_DISPATCHED`, `RESOLVED`, `RECONCILED`, `REJECTED`,
  `WONTFIX`; `verification_artifacts.status` in (`PASS`, `FAIL`, `BLOCKED`).
- Model mirror: `src/stratum/knowledge/bu_v2_models.py` —
  `PipelineRunState` (L103-113), `GapStatus` (L62-69),
  `VerificationOutcome` (L369-372).
- Runtime enforcers: `src/stratum/services/bu_v2_pipeline.py`
  (`VALID_TRANSITIONS` L29-38), `src/stratum/services/bu_v2_repositories.py`
  (`VALID_GAP_TRANSITIONS` L264-291, `BLOCKING_GAP_STATUSES` L295-300).

### P1 ReadingRun

- OLD_SPEC=STALE: deprecated acceptance vocabulary
  (`planned`, `in_progress`, `paused`, `completed`, `failed`) originates from
  the original 060 CREATE TABLE and was dropped from the live constraint by
  065. Stale acceptance text is a documentation defect, not a runtime
  failure.
- RUNTIME_AUTHORITY=PASS: live constraint (065) + `PipelineRunState` enum +
  `VALID_TRANSITIONS` enforce the 10-state machine; architecture tests
  (`tests/architecture/test_bu_v2_foundation.py`) assert against the enum.

### P6 UnderstandingGap

- OLD_SPEC=STALE: deprecated acceptance vocabulary
  (`IDENTIFIED`, `ANALYZING`, `VERIFIED`, `DEFERRED`, `BLOCKED`) has no
  counterpart in the 066 constraint. `BLOCKED` survives only as
  `VerificationOutcome.BLOCKED` (artifact outcome, not a gap state).
- RUNTIME_AUTHORITY=PASS: live constraint (066) + `GapStatus` enum +
  `VALID_GAP_TRANSITIONS` enforce the lifecycle
  `OPEN -> TARGETED_REREAD_REQUIRED -> REREAD_IN_PROGRESS -> RESOLVED`
  (plus `REJECTED` triage); architecture tests assert the authority
  vocabulary and `BLOCKING_GAP_STATUSES`.

### Test contract

- 1 drift reported (report-only, no test modified):
  `tests/services/test_book_reading.py:20` hardcodes deprecated P1 terminal
  states `("completed", "failed")`. See
  `docs/book-understanding-2.0/TEST_CONTRACT_DRIFT_REPORT.md`.
- `tests/architecture/test_bu_v2_foundation.py` is compliant (enum-based).

## Deliverables

- `docs/book-understanding-2.0/BU2_RUNTIME_AUTHORITY_SPEC.md` (new)
- `docs/book-understanding-2.0/TEST_CONTRACT_DRIFT_REPORT.md` (new)
- `docs/book-understanding-2.0/BU2_SPEC_RECONCILIATION_REPORT.md` (this file)

## Final Gate

BU2_APPLICATION_LAYER_FINAL_STATUS=PASS

Basis: production schema authority (065/066) + runtime evidence.
Not basis: stale acceptance text.
