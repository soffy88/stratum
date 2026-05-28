# Stratum Technical Debt

Last updated: 2026-05-28 (Phase 14 P1 complete)

Legend: `[ ]` open · `[x]` resolved · priority: **P0** blocker / **P1** soon / **P2** eventually

---

## Phase 14 — SaaS Backend

### Search & Indexing

- [ ] **P1** `oskill.hybrid_search` accepts `corpus_id` but does not filter at BM25/vector index level.
  Service layer post-filters in Python (correct but slower for large corpora).
  Target: physical partition or index-level filtering in oskill/oprim v1.2+. (Wave 2)

- [ ] **P2** `oskill` not installed in primary venv — tests use `SimpleNamespace` mocks.
  Full integration requires `pip install oskill` or wheels build in CI. (Wave 12)

### Agent & Job Stubs

- [ ] **P1** Agent runner (`POST /api/agents/run`) stores a stub record but does not execute real
  agent logic. Wired to `oskill` stub via `OScheduledJobsManager`. (Wave 5 / Wave 8)

- [ ] **P1** `OAnnotationLayer` block is display-only; annotation write-back to substrate is not
  implemented. Requires `/api/substrates/:id/annotations` endpoint. (Wave 8)

### Third-party Integrations (deferred to v1.1+)

- [ ] **P2** `dashscope_rerank` integration referenced in `oprim` — not activated.
  Planned for oprim v1.1+ once dashscope API key policy confirmed. (Wave 5)

- [ ] **P2** TTS service (`services/tts/`) scaffolded, no real implementation.
  Planned for oprim v1.1+ after TTS provider selection. (Wave 5)

- [ ] **P2** SMTP email delivery not wired. Reset-password and email-verification flows show
  placeholder UI only. Planned for v1.1+. (B-3)

### Auth & Security

- [ ] **P2** JWT secret read from `STRATUM_JWT_SECRET` env var; no rotation mechanism.
  Rotation requires session invalidation strategy. (Wave 1)

- [ ] **P2** CORS wildcard + credentials allowed in dev config (`app.py:31-37`). Must lock
  to explicit origin list before public launch. Pre-existing; not introduced by Phase 14.

### Profile & Sessions

- [x] **P1** `GET /api/users/by-username/:username` public profile endpoint. (Wave 10 Task 2)
- [x] **P1** `GET /api/users/me/sessions` + `DELETE /api/users/me/sessions/:id`. (Wave 10 Tasks 1–2)
- [x] **P1** Profile settings page wired to real API. (Wave 10 Task 4)

---

## Phase 11 (pre-Phase 14 carryover)

- [ ] **P1** `omodul` Wissen knowledge submodules still at historical path.
  Target: flatten to `omodul/` in Phase 11D. (Phase 11D not yet started)

- [ ] **P2** `oprim` stubs for `tts`, `sd`, `whisper` need real implementations or standard
  mock interface. Blocked until provider selection in Phase 11D.

- [ ] **P2** `hybrid_search` path migration left `oskill/knowledge/` placeholder.
  Remove in Phase 11D.

---

## Phase 1–13 (earlier carryover)

- [ ] **P2** `task_dao` and `template_dao` minimal — no pagination, no search.
  Full DuckDB implementation deferred to Phase 15.

- [ ] **P2** `weekly_review_workflow` prompt basic; lacks detailed activity context.
  Needs enrichment when workflow engine productionized in Phase 15.

- [ ] **P2** `docs/yiwancheng/` contains outdated design notes from pre-Phase 14 era.
  Should be archived or removed before v1.0 release docs freeze.

---

## Part 2 Audit — items verified complete as of Phase 14

| Item | Status | Verified in |
|------|--------|-------------|
| `GET /api/users/by-username/:username` | ✅ Done | Wave 10 Task 2 |
| Sessions list/revoke endpoints | ✅ Done | Wave 10 Tasks 1–2 |
| Profile page real API wiring | ✅ Done | Wave 10 Task 4 |
| Share token `share_tokens` key naming | ✅ Done | Phase 14 B-6 |
| Corpus isolation post-filter | ✅ Done | Wave 2 (service layer) |
| Migration 014 index coverage | ✅ Done | Phase 14 Z-3 EXPLAIN |
