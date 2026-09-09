# AII Final Product Quality Closure

## Parser

- Environment: `/data/soffy/projects/platform/3O/omodul/.venv`
- Frontmatter: `PASS`; declared as `python-frontmatter>=1.0` in the parser owner package `oprim/pyproject.toml` and locked in `oprim/uv.lock` (`oprim` dependency commit `f1e731a`).
- Canonical entrypoint: `POST /api/v1/inbox/submit` → `omodul.process_inbox_substrate` → `oprim.file_parser_pdf`; 30-doc measurement uses its `_stage_parse` parser stage.
- Production 1-doc: `PASS`; S1 source `01M21MEZ79GFJSDB37ZH3FM5N7`, persisted content 6,391 chars, 4 fragments, 4 resolvable anchors.
- 30-doc stage: 30/30 parse success; 134 fragments; 134/134 resolvable anchors (exact/normalized/approx); 30/30 monotonic ordering; exact quote fidelity 118/134 (88.06%); hash stability `PASS`.
- Table/code observations: 2 table-marker documents and 1 code-like document; independent source-format baselines were not available, so these are observations rather than fabricated preservation percentages.
- Re-ingest: `FAIL` at the HTTP endpoint; repeated S1 upload returned HTTP 500 on `idx_substrates_user_file_hash` instead of a stable deduplicated response.

## Retrieval

- Dataset: `gold_retrieval_verified_v1.json`; 100/100 verified, 0 candidate, 0 rejected.
- Types: 11 exact-source, 8 rare phrase, 73 claim question, 1 concept lookup, 7 cross-source synthesis.
- Path/model: `stratum.services.knowledge_view.search_knowledge_view`; query/index `BAAI/bge-m3`; dimension 1024.
- Metrics: Recall@1 `0.10`; Recall@5 `0.11`; Recall@10 `0.11`; MRR `0.105`; nDCG@10 `0.1063`.
- Citation validity `1.0`; anchor validity `1.0`; isolation leaks `0`.
- Failure categories: missing index `80`, ranking failure `8`, lexical miss `1`; wrong-source rate `0.9868`.

## Regression and release

- Embedding regression: 2 passed.
- Full backend suite: 510 passed, 3 failed, 14 skipped, 0 errors.
- The three failures are frozen/pre-existing closure data or environment conditions: duplicate `ScopeCept`, one orphan evidence row, and missing `obase` in the test environment.
- Release remains blocked by incomplete retrieval index coverage, duplicate re-ingest behavior, and the non-zero full-suite failures. Cloudflare/public deployment remains owner-blocked.
