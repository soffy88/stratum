# TEST CONTRACT DRIFT REPORT

STATUS=REPORT_ONLY
SCOPE=BU2 application-layer test contract vs production schema authority (065/066)
RULES=Tests were scanned and reported only. No test was modified.

Authority reference: `docs/book-understanding-2.0/BU2_RUNTIME_AUTHORITY_SPEC.md`

## 1. Scan Method

- Pattern scan over `tests/` for deprecated BU2 vocabulary:
  `planned`, `in_progress`, `paused`, `completed`, `failed`,
  `IDENTIFIED`, `ANALYZING`, `DEFERRED`, `BLOCKED`
- Targeted scan of all test files referencing BU2 domain objects:
  `book_reading_run`, `understanding_gaps`, `PipelineRunState`, `GapStatus`,
  `VerificationOutcome`
- Cross-check against the 065/066 CHECK constraints and the model enums
  (`src/stratum/knowledge/bu_v2_models.py`).

## 2. Drift Findings

### D1 — hardcoded deprecated P1 terminal states (CONFIRMED DRIFT)

File: `tests/services/test_book_reading.py:20`

```python
res = [v for v in self.tables["stratum.book_reading_run"].values()
       if v.get("user_id") == uid and v.get("source_id") == sid
       and v.get("status") not in ("completed", "failed")]
```

- Hardcodes the deprecated acceptance literals `completed` / `failed`.
- Under migration 065 the terminal states of `stratum.book_reading_run` are
  `VERIFIED`, `COMPRESSION_TESTED`, and `FAILED`.
- Impact: the mock treats authority-terminal runs (`VERIFIED`,
  `COMPRESSION_TESTED`) as still active, so the idempotency check in
  `create_reading_run` (legacy path) would return a fresh run instead of
  resuming a completed one. The mock no longer models the production
  constraint.
- Required direction of fix (NOT applied per report-only rule): derive the
  terminal set from `PipelineRunState` (e.g. `VERIFIED`, `COMPRESSION_TESTED`,
  `FAILED`) or from the 065 constraint, instead of the deprecated literals.

### D2 — legacy service still emits deprecated P1 vocabulary (CODE PATH, NOT TEST)

File: `src/stratum/services/book_reading.py:68,82`

- L68: `status NOT IN ('completed', 'failed')` (idempotency filter)
- L82: `"status": "planned"` (run creation)

This is runtime code, not a test. It is the legacy `book_reading` service
path; the BU2 pipeline authority path is `src/stratum/services/bu_v2_pipeline.py`
which uses `PipelineRunState` exclusively. Reported for completeness: any
acceptance assertion built on this legacy path would use deprecated
vocabulary. No change made (runtime code is frozen for this task).

## 3. Compliant Findings (no drift)

### C1 — `tests/architecture/test_bu_v2_foundation.py`

Already aligned with the 065/066 authority:

- P1 assertions use `PipelineRunState.*` enum members
  (`CREATED`, `PERCEIVED`, `INSPECTED`, `DEEP_READ_COMPLETE`,
  `CHAPTER_MODELLED`, `BOOK_INTEGRATED`, `VERIFICATION_PENDING`, `VERIFIED`,
  `COMPRESSION_TESTED`, `FAILED`) — e.g. L459-505, L660, L693, L710, L729-735,
  L750, L788.
- P6 gap lifecycle assertions use authority vocabulary (`OPEN`,
  `TARGETED_REREAD_REQUIRED`, `REREAD_IN_PROGRESS`, `RESOLVED`, `REJECTED`,
  `WONTFIX`, `RECONCILED`) — e.g. L579-631.
- `VerificationOutcome.BLOCKED` (L482) is the correct authority vocabulary
  for `verification_artifacts.status` (066); it is not a gap lifecycle state.
- `BLOCKING_GAP_STATUSES` assertion (L626-631) matches
  `src/stratum/services/bu_v2_repositories.py:295-300`.

### C2 — Other test files

No BU2 domain state assertions found in:
`test_bu_p2_segmentation.py`, `test_bu_p3_structure.py`,
`test_bu_p4_working_bu.py`, `test_bu_p8p9_benchmark.py`,
`test_mastery_authority_convergence.py`, `test_final_production_closure.py`,
`test_understanding_projection.py`, `test_challenge_suite.py`,
`test_aii_closure.py`, `test_pg_acceptance.py`, `test_pg_migration_runner.py`.

## 4. Out-of-Scope Hits (not BU2)

The following matches are other domains' status vocabularies, not BU2
ReadingRun/Gap states. No action:

- `tests/service_layer/test_scheduled_jobs.py`, `test_agents_run.py`,
  `tests/http_api/test_inbox_routes.py` — agent/job run statuses.
- `tests/service_layer/test_changefeed_events.py` — changefeed event types.
- `tests/services/test_podcast_feed.py`, `test_social_content_ingest.py`,
  `test_media_runtime.py`, `test_media_platforms.py` — media ingest job
  statuses.
- `tests/middleware/test_abuse_detection.py` — auth event names.
- `tests/conftest.py` — `completed` BOOLEAN column on an unrelated table.

## 5. Summary

| ID | File | Line | Verdict |
|----|------|------|---------|
| D1 | tests/services/test_book_reading.py | 20 | DRIFT — deprecated P1 terminal states hardcoded |
| D2 | src/stratum/services/book_reading.py | 68, 82 | Legacy code path (not a test) — deprecated vocabulary, frozen |
| C1 | tests/architecture/test_bu_v2_foundation.py | — | COMPLIANT — enum/authority vocabulary |

DRIFT_COUNT=1 (test contract)
LEGACY_CODE_PATH_COUNT=1 (runtime, out of acceptance scope)
TESTS_MODIFIED=0
