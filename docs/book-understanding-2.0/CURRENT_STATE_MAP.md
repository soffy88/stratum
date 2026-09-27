# CURRENT_STATE_MAP

## A. Knowledge / A 仓 (stratum.* & aii.* in aii_kg)
- **Source**: `CURRENT_PRODUCTION` (L1, `stratum.substrates`)
- **Fragment**: `CURRENT_PRODUCTION` (L1, `stratum.substrate_chunk`)
- **Evidence**: `CURRENT_PRODUCTION` (L1, `stratum.evidence` introduced in mig 020)
- **KU (Raw)**: `CURRENT_PRODUCTION` (L1, `aii.ku_onto` limits grade logic; `rf.refined_ku` in B仓 isolated). Missing cross-DB FK.

## B. Book Understanding (aii.bu_onto)
- **BU Generator**: `CURRENT_PARTIAL` (L1, `aii/scripts/generate_bu.py`). Only samples max 60 KUs.
- **BU Schema**: `CURRENT_PRODUCTION` (L1, `aii.bu_onto` has `facets_grounded`, `learning_paths`, `deep_cards`, `bu_quality`).
- **ChapterUnderstanding**: `MISSING` (L1, script level does not have chapter delta state tracking).
- **Argument/Mechanism**: `DOC_ONLY` / `SCHEMA_ONLY` (L1, fields like `argument_structure` exist but are JSON text without object-level relations).

## C. Notes / Expression (stratum.notes_sl, cornell_notes)
- **Notes**: `DUPLICATE_PATH` (L1, `notes_sl` vs legacy `NoteDAO`).
- **Cornell Notes**: `CURRENT_PRODUCTION` (L1, `cornell_notes` generated from B仓 `rf.refined_ku`).

## D. Learning / C 仓 (cx.* & stratum.learning_events)
- **LearningProgress (C仓)**: `CURRENT_PRODUCTION` (L1, `cx.learning_progress` uses custom 1/3/7/14/30/60 SM-2 scheduler).
- **Cornell Progress**: `DUPLICATE_PATH` (L1, `cornell_progress` in `stratum` DB).
- **DeepCard Progress**: `LEGACY_ACTIVE` (L1, `LearningLayer.tsx` saves to `localStorage`).
- **Flashcards**: `DUPLICATE_PATH` (L1, `stratum.flashcards` uses FSRS scheduler).

## E. Website / API
- **Website Surface**: `CURRENT_PRODUCTION` (L1, `/books`, `/book`, `/learning`, `/flashcards` in Next.js `aii-web/src/app/(aii)` and `(app)`).
- **Book Page**: `CURRENT_PRODUCTION` (L1, `book/page.tsx` renders `facets_grounded` and `LearningLayer`).

## F. Runtime / Storage / Authority
- **FastAPI**: `stratum-sl` (:9304) is main, `stratum-api` (:9302) is legacy.
- **Workers**: `aii-flywheel-*` scripts are running in systemd.
