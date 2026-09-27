# MIGRATION_MAP

1. **deep_cards**
   - CURRENT: `bu_onto.deep_cards` (JSON array) + frontend `localStorage` mastery.
   - TARGET ROLE: Independent `LearningObject` projection mapped to `stratum.learning_events` and `cx.learning_progress`.
   - REQUIRED CHANGE: Create explicit API for DeepCard mastery that writes to `learning_progress` instead of `localStorage`.
   - RISK: Low.
   - DEPENDENCIES: C仓 single-user to multi-tenant alignment.

2. **bu_onto.argument_structure / structure**
   - CURRENT: Flat JSON / LLM strings.
   - TARGET ROLE: Structured relations (`stratum.concept_relations` or new Argument object mapping to Evidence).
   - REQUIRED CHANGE: Extract arguments into explicit relational graphs, leaving `bu_onto` as projection cache.
   - RISK: High. Requires changes to BU generation scripts.
   - DEPENDENCIES: Cross-chapter state reasoning in `generate_bu.py`.

3. **Memory Schedulers (SM-2 vs FSRS)**
   - CURRENT: `cx.learning_progress` uses SM-2; `flashcards` uses FSRS.
   - TARGET ROLE: Unified FSRS engine tracking `LearningObject` reviews.
   - REQUIRED CHANGE: Migrate `learning_progress` to use FSRS parameters (`fsrs_state`, `fsrs_step`, `stability`, `difficulty`).
   - RISK: Medium.
   - DEPENDENCIES: FSRS integration logic for non-flashcard items.

4. **cornell_progress**
   - CURRENT: Dedicated table `stratum.cornell_progress`.
   - TARGET ROLE: Merge semantics into canonical `cx.learning_progress` or `stratum.learning_events`.
   - REQUIRED CHANGE: Make cornell drill answers emit `LearningEvent`.
   - RISK: Medium.
   - DEPENDENCIES: `LearningObject` abstraction over Cornell drills.
