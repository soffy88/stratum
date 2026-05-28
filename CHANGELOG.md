# Changelog

All notable changes to Stratum are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); versioning follows [SemVer](https://semver.org/).

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
