# REUSE_MAP

- **A Raw KU**: `KEEP_AS_AUTHORITY`. Need to bridge cross-DB gap to Evidence.
- **A KC**: `ADAPT`. Expand to proper hierarchical chapter understanding.
- **BU (bu_onto)**: `EXTEND`. It is the canonical authority, but fields are overloaded JSON strings.
- **facets_grounded**: `USE_AS_PROJECTION`. Should be projected from genuine Mechanism/Argument models.
- **learning_paths / deep_cards**: `ADAPT`. Deep cards should become canonical `LearningObject` entities rather than pure JSON inside `bu_onto`.
- **Cornell**: `KEEP_AS_AUTHORITY` for generated document-centric notes.
- **flashcards**: `ADAPT`. Align their target to canonical Knowledge Objects (KU/Concept).
- **learning_profile / learning_plan / learning_progress / learning_stuck (C仓)**: `EXTEND`. Merge `cornell_progress` and DeepCard local mastery into canonical `learning_progress`.
- **mastery_score / quiz**: `EXTEND`. Support multi-modal assessments beyond naive SM-2.
- **error_type**: `ADAPT`. Needs policy integration (currently just logged in `learning_stuck`).
- **Book page / Learning page**: `KEEP_AS_AUTHORITY`. Re-wire to new merged APIs.
