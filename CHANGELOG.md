# Changelog

All notable changes to Stratum are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); versioning follows [SemVer](https://semver.org/).

---

## [0.0.4] — 2026-06-20

### Fixed
- **G5 anti-loop 根治**（SPEC-G5-v1.0）：`_anti_loop_check` 原查 `ORDER BY processed_at DESC LIMIT 1`，多源交替写入时成功源（gutenberg）可掩盖失败源（arxiv）连续 miss，G5 永不触发。
  - Migration 041：`aii_processed_needs` 建 `UNIQUE(need_hash, source_type)` 唯一索引；历史行去重并累加 `ingested_count`，确保 G1 SUM 不丢数；可回滚（`DROP INDEX`）。
  - `_anti_loop_check`：改为 `WHERE need_hash=? AND source_type=?`，按源独立判定。
  - `_record_need`：INSERT → `ON CONFLICT DO UPDATE`，`ingested_count` 跨轮累加。
  - `_process_one_need`：G5 检查移入 per-source 循环（`continue` 跳过该源），旧行为是 `return` 跳过整个 need。
  - `_get_prev_miss_rounds`：提取为具名函数，支持测试 patch。
  - `_create_and_run_subscription` / `_process_one_need`：新增 `_runner=None` 依赖注入点（keyword-only，生产路径向后兼容）。
- **D断言归属纠正**：撤回 `source_watcher_service.py` 中的装饰性 bundle_file_hash 断言；真实断言位置应在 `oskill/ingest_substrate.py`（§20 Owner 管辖，挂账）。

### Tests
- `tests/services/test_g5_anti_loop_e2e.py`：真实 DuckDB E2E，两用例：
  - 主测试：2 轮跑完后 arxiv→`needs_human_review` + UNRESOLVED_LOG 写入，gutenberg 不受影响，SUM(ingested_count)=4（O1-O4 全绿）。
  - 对照组：patch `_get_prev_miss_rounds` 为旧 SQL，证明旧代码 arxiv 永不触发（bug 复现，根治有效）。

---

## [0.7.0] — 2026-06-02

Phase 15 P1: 功能补足 (alpha v0.7)

### Added
- AI Agent 真触发: 3 omodul workflow 全注册 (daily_digest / weekly_review / knowledge_curator)
- Agent run history + detail endpoint (`GET /api/v1/agents/runs`, `GET /api/v1/agents/runs/{id}`)
- Agent run detail page (`/agents/runs/{id}`) 含 trace/citations/files_generated
- Scheduler CRUD API (`POST/GET/PUT/DELETE /api/v1/scheduled-jobs`, run-now, runs history)
- Scheduler 3 builtin_jobs (daily_digest 8AM / weekly_review Mon 9AM / knowledge_curator 每6h)
- changefeed 统一 emit_event() 模块; 14 种事件 (substrate/concept/agent/highlight/view + note)
- WebSocket 真广播 changefeed events (broadcast_to_user, active_connections)
- Sync changefeed scope 过滤 (`?scope=notes,substrates,highlights,concepts`)
- 平台内容 seed: 5 篇 Stratum 任务书 (build in public); /discover 真显示
- Frontend: jobs adapter 修正路径; discover 转 client component 真显示内容

### Deferred to v1.0+
- 4 Agent stub (translation_worker / reading_companion / lint_bot / audio_generator) — 等 omodul Phase 11D
- access_tier 拦截 (alpha 期全部 free)
- Agent trace 可视化 UI

### Tests
- 273 pytest (baseline 235, Wave 1-3 +38)
- vitest (前端类型安全)

---

## [1.0.0-alpha] — 2026-05-28

Phase 14 complete. Full SaaS backend + frontend.

### Added
- Multi-corpus isolation (migration 014/015, middleware, post-filter search)
- User system: register / login / JWT refresh / session management / profile
- Share tokens: public read-only access with expiry
- Hybrid search API (`oskill.hybrid_search` BM25 + vector)
- Agent runner stub + scheduled jobs CRUD
- Substrates / fragments / backlinks REST API (27 routes total)
- Next.js 15 frontend: auth pages, search, AI QA/summary, document tree, settings
- @helios/blocks 1.5.0 integration (9 blocks + 5 adapters)
- Admin dashboard with stats endpoint
- Landing page, legal pages, SEO meta
- 19 Playwright browser e2e tests
- 214 pytest backend tests
- Docker Compose + Nginx reverse proxy deployment
- Rate limiting + abuse detection middleware
- Feedback collection endpoint
- Sentry error tracking (env-guarded)
- Storybook 8 component documentation
- OpenAPI 3.1 spec (docs/STRATUM_API_v1.md)

### Fixed
- Constant-time secret comparison in admin route (timing attack)
- Share page hardcoded port → `STRATUM_API_INTERNAL_URL` env var
- oskill optional import (graceful fallback to SimpleNamespace mock)
- pytest pythonpath config for reliable test discovery

### Security
- JWT access + refresh token flow with bcrypt password hashing
- Corpus isolation enforced at middleware + DAO layer
- Admin route protected by HMAC secret comparison

---

## [0.6.0] — 2026-05-26

Phase 11C: Service layer initial implementation.

### Added
- `stratum.service.search` module with hybrid search orchestration
- `stratum.dao` layer for DuckDB operations
- Integration test workflow script
- MCP server wrapper for oprim tools

---

## [0.5.0] — 2026-05-20

Phase 10: Translation + knowledge pipeline.

### Added
- Trafilatura webpage ingestion
- PDF ingestion via pymupdf4llm
- Knowledge agent modules (`omodul/knowledge/agents/`)
- TTS service scaffold (`services/tts/`)

---

## [0.3.0] — 2026-05-18

Phase 1–4: Foundation + batch processing.

### Added
- Project structure: `_hub/`, `notes/`, `substrate/`, `concepts/`
- YAML schemas for all content types (18 schemas)
- DuckDB indexing pipeline
- Obsidian wikilink experiment (04)
- Embedding benchmark experiments (02-batch)
- stratum-cli: CLI tool for local operations
- Browser extension scaffold (stratum-extension)

---

## [0.1.0] — 2026-05-16

Initial commit. Project scaffolding.

### Added
- Repository structure
- pyproject.toml with optional dependency groups
- Basic schema definitions
