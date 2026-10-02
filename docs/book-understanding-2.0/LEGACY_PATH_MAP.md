# LEGACY PATH MAP

| Legacy Path | Still used? | Production traffic? | DB Writes? | Frontend reachable? | Tests? | Safe to freeze? |
|---|---|---|---|---|---|---|
| raw-text flashcard generation | YES | YES | YES (`stratum.flashcards`) | YES | YES | NO (Requires migration) |
| old BU generation (`synthesize_book_llm_v1.py`) | NO | NO | NO | NO | NO | YES |
| old note path (`legacy :9302 stratum-api`) | YES (fallback) | YES (auth/search) | NO | YES | NO | NO |
| old scheduler (SM-2 fields in flashcards) | YES | YES | YES | YES | YES | NO |
| aii_context (C repo) | YES | YES | YES (`cx.learning_progress`) | YES | YES | NO (It is the current production) |
| `stratum.knowledge_claims` | YES (via `knowledge.py` only) | NO (Main ingest uses `aii.ku_onto`) | YES (mock writes) | YES (some new API routes) | YES | YES (Schema layer only) |
