# AUTHORITY MAP

## Canonical Authorities

- **SOURCE_AUTHORITY=** `stratum.substrates` (L1 SOURCE_VERIFIED) - Used across all systems.
- **RAW_KU_AUTHORITY=** `aii_kg` -> `aii.ku_onto` (L1 SOURCE_VERIFIED) - Written by flywheel scripts. `stratum.knowledge_claims` is largely a stub/schema.
- **BOOK_CONCEPT_AUTHORITY=** `aii.concept_onto` (L1 SOURCE_VERIFIED)
- **A_KC_AUTHORITY=** `aii.kc_onto` (L1 SOURCE_VERIFIED)
- **BU_AUTHORITY=** `aii_kg` -> `aii.bu_onto` (L1 SOURCE_VERIFIED)
- **B_REFINED_KU_AUTHORITY=** `aii_refined` -> `rf.refined_ku` (L1 SOURCE_VERIFIED)
- **B_CONCEPT_AUTHORITY=** `aii_refined` -> `rf.refined_concept` (L1 SOURCE_VERIFIED)
- **NOTE_AUTHORITY=** `stratum.notes_sl` (L1 SOURCE_VERIFIED)
- **PERSONAL_NOTE_AUTHORITY=** `stratum.notes_sl` (L1 SOURCE_VERIFIED)

## Disputed / Split Authorities

- **LEARNING_STATE_AUTHORITY=** `cx.learning_progress` (C repo) — sole canonical authority.
  `cornell_progress` (stratum schema) is Cornell note telemetry, NOT mastery authority.
  `LearningLayer` (localStorage) is browser-local completion state, NOT mastery authority.
- **MASTERY_AUTHORITY=** `cx.learning_progress` (C repo) — SOLE canonical mastery authority
  (MASTERY_AUTHORITY_COUNT = 1). `stratum.cornell_progress` (mastered dict) is note
  telemetry, NOT mastery authority. `localStorage` (frontend Deep Cards, `aii-bu-learning-`
  keys) is browser-local completion state, NOT mastery authority. `stratum.flashcards`
  (FSRS scheduler state) is card scheduling state, NOT mastery authority.
- **MEMORY_SCHEDULER_AUTHORITY=** SPLIT (L1 SOURCE_VERIFIED)
  - FSRS in `flashcard_service.py` -> `stratum.flashcards` (card scheduling state, NOT mastery authority)
  - `cx.learning_progress.next_review_at`
- **BOOK_PAGE_RENDER_SOURCE=** SPLIT (L1 SOURCE_VERIFIED)
  - Merges `aii.bu_onto`, `aii.ku_onto`, UI local state.
