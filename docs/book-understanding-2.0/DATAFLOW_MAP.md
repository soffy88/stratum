# DATAFLOW MAP

```text
Book ingest
→ Source (stratum.substrates)
→ KU Extraction (aii.ku_onto)
→ KC Extraction (aii.concept_onto)
→ BU Generation (aii.bu_onto)
→ Book page (Next.js frontend reads merged data)

Knowledge → Learning
BU / B knowledge (aii_refined)
→ Cornell (cornell_notes via generate_for_concept)
→ UI progress (cornell_progress)

Raw Source Text (Markdown)
→ Flashcards (stratum.flashcards via oprim.llm.llm_call bypass)
→ Review Scheduler (flashcard_service FSRS)
→ Event Bridge (learning_events)

Knowledge
→ Learning Progress (cx.learning_progress)
→ Mastery Update
→ Next Review At (cx.learning_progress)
```
