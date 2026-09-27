# GAP_MAP

- **Evidence Layer**: `READY` (New `stratum.evidence` handles anchoring well).
- **KU Layer**: `PARTIAL` (A仓 `ku_onto` and B仓 `refined_ku` disconnected, no explicit cross-DB FK).
- **Argument / Mechanism**: `MISSING` (Only JSON text in `bu_onto`; no explicit graph objects).
- **ChapterUnderstanding**: `MISSING` (Scripts synthesize chapter summaries, but do not maintain cross-chapter delta states).
- **BU Layer**: `PARTIAL` (Sampling limit of 60 KUs; `facets_grounded` exists but relies on shallow script logic).
- **Verification**: `PARTIAL` (`bu_learning_gate.py` has format/content checks, but no targeted reread logic).
- **Projection**: `READY` (Cornell, Flashcards, DeepCards are generating, though heavily siloed).
- **LearningGraph**: `MISSING` (No canonical `LearningObject` bridging BU, Cornell, and Flashcards).
- **Mastery**: `BLOCKED_BY_UPSTREAM` (Fragmented authorities: SM-2, FSRS, localStorage, `cornell_progress`. Needs unified `LearningObject` contract).
