# WEBSITE_SURFACE_MAP

- **`/books` & `/book`**
  - DATA SOURCE: `aii_kg` (`aii.bu_onto`, `stratum.substrates`).
  - API: `stratum-sl` (`/api/aii/*`).
  - PRIMARY OBJECT: Book Understanding (`facets_grounded`, `deep_cards`).
  - LOCAL STATE: `LearningLayer` stores `done` checkboxes in `localStorage`.
  - OVERLAP: DeepCard UI mastery does not sync with C仓.

- **`/learning` & `/learning/[id]`**
  - DATA SOURCE: `aii_context` (`cx.learning_profile`, `cx.learning_progress`).
  - API: `stratum-sl` (learning routes).
  - PRIMARY OBJECT: Learning Progress, Stuck Points.
  - SERVER STATE: SM-2 next review dates.

- **`/notes` & `/notes/[id]`**
  - DATA SOURCE: `stratum.notes_sl` and `stratum.cornell_notes`.
  - API: `stratum-sl`.
  - PRIMARY OBJECT: User notes and Machine generated Cornell notes.
  - SERVER STATE: `cornell_progress` tracked separately.

- **`/flashcards`**
  - DATA SOURCE: `stratum.flashcards`.
  - API: `stratum-sl` (Flashcard routes).
  - PRIMARY OBJECT: Flashcard (Raw text or generated).
  - SERVER STATE: FSRS scheduling parameters.
