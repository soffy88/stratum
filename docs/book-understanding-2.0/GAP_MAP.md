# GAP MAP

| Capability Layer | Status | Notes | Priority |
|---|---|---|---|
| Evidence | READY | `aii.ku_onto.evidence` | - |
| KU | READY | `aii.ku_onto` | - |
| Argument / Mechanism | PARTIAL | `bu_onto.argument_structure` is text/JSON, no distinct mechanism objects. | P1 |
| ChapterUnderstanding | PARTIAL | Summary level only, lacks structured delta/dependencies. | P1 |
| BU | READY | `aii.bu_onto` has rich generation scripts. | - |
| Verification | READY | Handled by `bu_learning_gate.py` | - |
| Projection | READY | `deep_cards`, `learning_paths` in `aii.bu_onto` | - |
| LearningGraph | MISSING | Flashcards and Cornell use disjoint paths. | P3 |
| Mastery | PARTIAL | Split across 3 authorities (`localStorage`, `cornell_progress`, `cx.learning_progress`). | P0 |

## Priority Classifications
- **P0**: Mastery authority split (LocalStorage / Cornell / C repo). Dual track DB architecture (AII vs Stratum).
- **P1**: Argument model is text-only. No cross-chapter structural state.
- **P3**: Flashcards bypass knowledge base. Multiple schedulers active.
