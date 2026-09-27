# AUTHORITY_MAP

## Canonical Authorities (Where truth lives)

- **SOURCE_AUTHORITY**: `stratum.substrates` (L1)
- **RAW_KU_AUTHORITY**: `aii.ku_onto` (L1)
- **BOOK_CONCEPT_AUTHORITY**: SPLIT. `aii.concept_onto` (A仓) vs `rf.refined_concept` (B仓).
- **A_KC_AUTHORITY**: `aii.kc_onto` (L1)
- **BU_AUTHORITY**: `aii.bu_onto` (L1)
- **B_REFINED_KU_AUTHORITY**: `rf.refined_ku` (L1)
- **B_CONCEPT_AUTHORITY**: `rf.refined_concept` (L1)
- **NOTE_AUTHORITY**: SPLIT. `stratum.notes_sl` vs `cornell_notes`.
- **PERSONAL_NOTE_AUTHORITY**: `stratum.notes_sl` (L1)
- **LEARNING_STATE_AUTHORITY**: SPLIT. `cx.learning_progress` (C仓), `cornell_progress` (stratum), `stratum.flashcards` (stratum), and `localStorage` (frontend Deep Cards).
- **MASTERY_AUTHORITY**: SPLIT. `cx.learning_progress` determines point mastery, `flashcards` determines card memory state, `cornell_progress` determines note mastery, `localStorage` tracks DeepCard completion.
- **MEMORY_SCHEDULER_AUTHORITY**: SPLIT. SM-2 in `cx.learning_progress`, FSRS in `stratum.flashcards`.
- **BOOK_PAGE_RENDER_SOURCE**: `aii.bu_onto` (L1, renders from DB schema via API).
