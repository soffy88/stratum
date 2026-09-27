# TEST_BASELINE

- **`tests/architecture/test_aii_closure.py`**
  - TYPE: Static Architecture Analysis.
  - REALITY: `MOCK_ONLY` (Reads Python and SQL files via static analysis to ensure constitutional rules like "never overwrite").
  
- **`tests/architecture/test_final_production_closure.py`**
  - TYPE: Architecture Production Validation.
  - REALITY: `REAL_DB`. Checks DB connection and actual schemas, but focuses on structural presence rather than product end-to-end functionality.

- **BU Test Status**
  - "BU 已通过" mostly refers to unit tests or architecture closure tests verifying schema definitions and contract rules. 
  - There are no `TRUE_E2E` tests for cross-chapter BU synthesis logic (because cross-chapter synthesis does not truly exist).
