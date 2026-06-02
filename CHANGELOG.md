# Changelog

All notable changes to Stratum are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); versioning follows [SemVer](https://semver.org/).

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
