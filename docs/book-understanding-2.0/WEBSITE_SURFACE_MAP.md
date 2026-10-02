# WEBSITE SURFACE MAP

| Page | Data Source | API | Primary Object | User Action | Local State | Server State | Overlap |
|---|---|---|---|---|---|---|---|
| `/books` | `aii.bu_onto`, `substrates` | - | Book Collection | View | - | - | - |
| `/book` | `aii.bu_onto` | - | Book BU | View Facets | - | - | - |
| `/learning` | `cx.learning_progress` | `/api/v1/learning` | Profile / Progress | View Plan | - | - | - |
| `/learning/[id]` | `aii.bu_onto.deep_cards` | - | Deep Cards | Mark Done | `localStorage` "✓ 已掌握" | `cx.learning_progress` (if integrated) | YES (Mastery state split) |
| `/notes/cornell` | `cornell_notes` | `/api/v1/cornell` | Cornell Note | Edit / Polish | UI cues | DB | - |
| `/flashcards` | `stratum.flashcards` | `/api/v1/flashcards` | Flashcard | Review | - | DB `due_at` | YES (Review scheduler split) |
