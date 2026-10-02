# BU2 RUNTIME AUTHORITY SPEC

STATUS=CANONICAL
SCOPE=Book Understanding 2.0 application-layer acceptance
DB=aii_kg
MIGRATION_LEDGER=49
BU2_SCHEMA=060-066
BU2_RUNTIME=LIVE

This spec is the sole authority for BU2 application-layer acceptance state
vocabulary. Where older acceptance texts, test fixtures, or legacy code paths
use a different vocabulary, this spec wins. Stale acceptance text is NOT
evidence of runtime failure.

## 1. Schema Authority Source

The production-verified authority for BU2 state vocabulary is the migration
chain 060-066, with 065 and 066 as the current canonical definitions:

- `src/stratum/db/pg_migrations/065_bu2_pipeline_state.sql`
  - Replaces `book_reading_run_status_check` with the 10-state P1 pipeline
    constraint (section 2 below).
  - Adds `failure_reason TEXT` for persistence of the FAILED state.
- `src/stratum/db/pg_migrations/066_bu2_p4_p9_repair.sql`
  - Replaces `understanding_gaps_status_check` with the P6 gap lifecycle
    constraint (section 3 below).
  - Creates `stratum.verification_artifacts` with
    `status CHECK (status IN ('PASS', 'FAIL', 'BLOCKED'))`.

Model-layer mirror (must stay in sync with the schema authority):

- `src/stratum/knowledge/bu_v2_models.py`
  - `PipelineRunState` (L103-113) — 10 states.
  - `GapStatus` (L62-69) — 7 values.
  - `VerificationOutcome` (L369-372) — PASS / FAIL / BLOCKED.

Runtime enforcers (read-only evidence, not to be modified by acceptance work):

- `src/stratum/services/bu_v2_pipeline.py` — `VALID_TRANSITIONS` (L29-38),
  `_fail_pipeline` (L81-86).
- `src/stratum/services/bu_v2_repositories.py` — `VALID_GAP_TRANSITIONS`
  (L264-291), `BLOCKING_GAP_STATUSES` (L295-300).

## 2. P1 ReadingRun State Machine

Table: `stratum.book_reading_run`
Column: `status`
Constraint: `book_reading_run_status_check` (migration 065)

### 2.1 Deprecated acceptance vocabulary (DO NOT USE)

The following lowercase literals are the OLD acceptance vocabulary. They
originate from the original `CREATE TABLE` in migration 060
(`060_bu2_p2_reading_evidence.sql` L8) and were dropped from the live
constraint by migration 065. They are deprecated and MUST NOT be used in
acceptance assertions:

```
planned
in_progress
paused
completed
failed
```

Note: `failed` (lowercase) is deprecated; the authority spelling is `FAILED`.

### 2.2 Production authority states (10)

Defined by migration 065 and mirrored by `PipelineRunState`:

| # | State | Meaning |
|---|-------|---------|
| 1 | `CREATED` | Run row created; pipeline not started |
| 2 | `PERCEIVED` | Pass 0: source perceived |
| 3 | `INSPECTED` | Pass 1: source inspected |
| 4 | `DEEP_READ_COMPLETE` | Pass 2: deep read complete |
| 5 | `CHAPTER_MODELLED` | Pass 3: chapter model built |
| 6 | `BOOK_INTEGRATED` | Pass 4: book-level understanding integrated |
| 7 | `VERIFICATION_PENDING` | Pass 5: verification gate entered, artifact not yet PASS |
| 8 | `VERIFIED` | Pass 5: verification artifact PASS, no blocking gaps |
| 9 | `COMPRESSION_TESTED` | Pass 6: compression/retrieval test passed (terminal success) |
| 10 | `FAILED` | Operational commit failure; `failure_reason` persisted |

### 2.3 Authority transition map

Forward chain (strict, enforced by `VALID_TRANSITIONS` in
`bu_v2_pipeline.py` L29-38):

```
CREATED -> PERCEIVED -> INSPECTED -> DEEP_READ_COMPLETE -> CHAPTER_MODELLED
  -> BOOK_INTEGRATED -> VERIFICATION_PENDING -> VERIFIED -> COMPRESSION_TESTED
```

Failure path: any non-FAILED state -> `FAILED`, only via `_fail_pipeline`
on operational commit failure (persistence error), never on validation
rejection. `PipelineTransitionError` leaves the persisted state unchanged.

### 2.4 Deprecated-to-authority mapping (reference only)

| Deprecated | Authority equivalent |
|------------|----------------------|
| `planned` | `CREATED` |
| `in_progress` | `PERCEIVED` / `INSPECTED` / `DEEP_READ_COMPLETE` / `CHAPTER_MODELLED` / `BOOK_INTEGRATED` (active passes) |
| `paused` | no direct equivalent; nearest awaiting state is `VERIFICATION_PENDING` |
| `completed` | `VERIFIED` / `COMPRESSION_TESTED` (terminal success) |
| `failed` | `FAILED` |

## 3. P6 UnderstandingGap Lifecycle

Table: `stratum.understanding_gaps`
Column: `status`
Constraint: `understanding_gaps_status_check` (migration 066)

### 3.1 Deprecated acceptance vocabulary (DO NOT USE)

The following uppercase literals are the OLD acceptance vocabulary for the
P6 gap lifecycle. They have no counterpart in the 066 constraint and MUST
NOT be used in acceptance assertions:

```
IDENTIFIED
ANALYZING
VERIFIED
DEFERRED
BLOCKED
```

Note: `BLOCKED` survives only as `VerificationOutcome.BLOCKED`
(`verification_artifacts.status`), which is a verification outcome, NOT a
gap lifecycle state.

### 3.2 Production authority states (7)

Defined by migration 066 and mirrored by `GapStatus`:

| State | Role |
|-------|------|
| `OPEN` | Gap identified, not yet triaged |
| `TARGETED_REREAD_REQUIRED` | Triage complete; targeted reread required |
| `REREAD_IN_PROGRESS` | Targeted reread in progress |
| `TARGETED_REREAD_DISPATCHED` | Legacy value; accepted for already-persisted rows, not the forward path |
| `RESOLVED` | Terminal: gap resolved |
| `REJECTED` | Terminal: triage rejection path |
| `WONTFIX` | Legacy value; accepted for already-persisted rows, not the forward path |

Canonical forward lifecycle (per migration 066 D7 comment):

```
OPEN -> TARGETED_REREAD_REQUIRED -> REREAD_IN_PROGRESS -> RESOLVED
                                                      \-> REJECTED (triage)
```

### 3.3 Authority transition map

Enforced by `VALID_GAP_TRANSITIONS` in `bu_v2_repositories.py` L264-291:

- `OPEN` -> `TARGETED_REREAD_REQUIRED` | `TARGETED_REREAD_DISPATCHED` | `REJECTED` | `WONTFIX`
- `TARGETED_REREAD_REQUIRED` -> `REREAD_IN_PROGRESS` | `REJECTED` | `WONTFIX`
- `REREAD_IN_PROGRESS` -> `RESOLVED` | `TARGETED_REREAD_REQUIRED` | `REJECTED` | `WONTFIX`
- `TARGETED_REREAD_DISPATCHED` -> `REREAD_IN_PROGRESS` | `RESOLVED` | `REJECTED` | `WONTFIX`
- `RESOLVED` / `REJECTED` / `WONTFIX` -> (terminal, no further transitions)

Blocking semantics: a gap blocks VERIFIED iff its status is in
`BLOCKING_GAP_STATUSES` = {`OPEN`, `TARGETED_REREAD_REQUIRED`,
`REREAD_IN_PROGRESS`, `TARGETED_REREAD_DISPATCHED`}. `RESOLVED`, `REJECTED`,
`WONTFIX`, `RECONCILED` never block.

### 3.4 Deprecated-to-authority mapping (reference only)

| Deprecated | Authority equivalent |
|------------|----------------------|
| `IDENTIFIED` | `OPEN` |
| `ANALYZING` | `TARGETED_REREAD_REQUIRED` / `REREAD_IN_PROGRESS` |
| `VERIFIED` | `RESOLVED` |
| `DEFERRED` | `REJECTED` / `WONTFIX` |
| `BLOCKED` | no gap status; blocking is derived from `BLOCKING_GAP_STATUSES` |

## 4. Acceptance Rule

1. Tests MUST NOT hardcode the deprecated state sets:
   - P1: `planned`, `in_progress`, `paused`, `completed`, `failed`
   - P6: `IDENTIFIED`, `ANALYZING`, `VERIFIED`, `DEFERRED`, `BLOCKED`
2. Tests MUST derive expected states from the schema authority
   (migrations 065/066 CHECK constraints) or from the model enums
   (`PipelineRunState`, `GapStatus`, `VerificationOutcome`).
3. Acceptance assertions against BU2 runtime behavior are valid only when
   expressed in the authority vocabulary of sections 2 and 3.
4. Stale acceptance text using deprecated vocabulary is a documentation
   defect, NOT a runtime failure. Reconciliation is done by updating the
   spec/docs, never by changing migrations, runtime code, or production data.
5. `VerificationOutcome` (`PASS` / `FAIL` / `BLOCKED`) is the vocabulary
   for `verification_artifacts.status` only; it is not interchangeable with
   `PipelineRunState` or `GapStatus`.

## 5. Related Documents

- `docs/book-understanding-2.0/AUTHORITY_MAP.md` — canonical storage authorities
- `docs/book-understanding-2.0/MIGRATION_MAP.md` — dual-track convergence map
- `docs/book-understanding-2.0/CURRENT_STATE_FINAL_REPORT.md` — convergence report
- `docs/UPGRADE_ACCEPTANCE_RUNBOOK.md` — deployment acceptance runbook
- `TEST_CONTRACT_DRIFT_REPORT.md` — test contract drift audit (report only)
- `BU2_SPEC_RECONCILIATION_REPORT.md` — final reconciliation report
