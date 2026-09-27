# DATAFLOW_MAP

```text
1. Book Ingest
Source (stratum.substrates) 
  → Fragment (stratum.substrate_chunk)
  → Evidence (stratum.evidence)
  → KU (aii.ku_onto via aii-flywheel scripts)

2. Knowledge Refinement
Raw KU (aii.ku_onto) 
  → B Refined KU (rf.refined_ku via scripts)
  → B Concept (rf.refined_concept)

3. Book Understanding Synthesis
Raw KU (sampled max 60) + A KC 
  → BU generation script (generate_bu.py)
  → aii.bu_onto (facets_grounded, learning_paths, deep_cards)

4. Learning Projection Generation
B Refined KU + B Concept 
  → Cornell generator (cornell_generator.py) 
  → stratum.cornell_notes

BU deep_cards (JSON) 
  → Frontend Book Page (LearningLayer.tsx)

5. Mastery Tracking (Fragmented)
Frontend DeepCards → localStorage (UI state)
Frontend Flashcards → stratum.flashcards (FSRS scheduler)
Frontend Cornell Drills → stratum.cornell_progress
Frontend Learning Mode → cx.learning_progress (SM-2 scheduler, aii_context DB)
```
