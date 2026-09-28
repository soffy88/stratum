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
- **LEARNING_STATE_AUTHORITY**: `cx.learning_progress` (C仓) — sole canonical authority. `cornell_progress` (stratum) is Cornell note telemetry, NOT mastery. `stratum.flashcards` is flashcard scheduling state, NOT mastery. `localStorage` (frontend Deep Cards) is browser-local completion state, NOT mastery.
- **MASTERY_AUTHORITY**: `cx.learning_progress` (C仓) — sole canonical authority. `flashcards` determines card memory state (scheduling, not mastery). `cornell_progress` determines note telemetry (not mastery). `localStorage` tracks DeepCard completion (not mastery).
- **MEMORY_SCHEDULER_AUTHORITY**: `cx.learning_progress` (C仓) — SM-2-style interval schedule (1/3/7/14/30/60 days). `stratum.flashcards` uses FSRS (py-fsrs) with SM-2 fallback — this is card scheduling state, NOT mastery authority. Flashcard scheduler and history are preserved as-is.
- **BOOK_PAGE_RENDER_SOURCE**: `aii.bu_onto` (L1, renders from DB schema via API).
