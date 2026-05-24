# Stratum Technical Debt

## High Priority
- [ ] hybrid_search path migration left `oskill/knowledge/` placeholder, remove in Phase 11D.
- [ ] oprim stubs for tts, sd, whisper need real implementations or standard mock interface.
- [ ] omodul Wissen knowledge submodules are still in historical path, move to flat omodul in Phase 11D.

## Medium Priority
- [ ] task_dao and template_dao are currently minimal, need full DuckDB/SQLAlchemy implementation.
- [ ] weekly_review_workflow uses very basic prompt, need to enrich with detailed activity context.

### Phase 14 Wave 2 — Corpus Isolation
- [ ] oskill.hybrid_search currently accepts corpus_id but does not filter at the BM25/Vector index level. Stratum service layer implements a post-filter which works but is less efficient for large corpora. Needs physical partition or index-level filtering in oskill/oprim v1.2+.
