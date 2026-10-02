# MIGRATION MAP

### 1. Dual Track Architecture Unification
CURRENT: `aii.ku_onto` (A repo real DB) vs `stratum.knowledge_claims` (schema/stub)
→ TARGET ROLE: Converge onto `aii.ku_onto` as the real storage or migrate data to `stratum.knowledge_claims`.
→ REQUIRED CHANGE: Either deprecate `stratum.knowledge_claims` from the architectural contract and acknowledge `aii.ku_onto` as the canonical authority, or run a data migration.
→ RISK: High
→ DEPENDENCIES: Architecture contract `AII_ARCHITECTURE_CONTRACT.md`

### 2. Flashcards Grounding
CURRENT: `flashcard_service.py` raw-text parsing (bypasses KU/BU/Mastery)
→ TARGET ROLE: Knowledge-grounded flashcards
→ REQUIRED CHANGE: Rewrite generator to source from `aii.ku_onto` / `rf.refined_ku`. Integrate review schedule with `cx.learning_progress`.
→ RISK: Medium
→ DEPENDENCIES: C repo authority

### 3. Mastery Convergence
CURRENT: LocalStorage `LearningLayer`, `cornell_progress`, and `cx.learning_progress` all manage mastery/completion.
→ TARGET ROLE: Single mastery authority
→ REQUIRED CHANGE: Deprecate `cornell_progress.state.mastered` and LocalStorage. Route all mastery signals to `cx.learning_progress`.
→ RISK: Medium
→ DEPENDENCIES: API convergence in `src/stratum/api/routers/learning.py`

### 4. Memory Scheduler Unification
CURRENT: `stratum.flashcards.due_at` vs `cx.learning_progress.next_review_at`
→ TARGET ROLE: Single review scheduler
→ REQUIRED CHANGE: Adapt flashcard review endpoint to update C repo mastery states.
→ RISK: Low
→ DEPENDENCIES: `flashcard_service.py` & `mastery_authority.py`
