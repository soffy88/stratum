# Contributing to AII

The product is AII; `stratum` is the retained implementation namespace. Keep
that distinction in user-facing text and do not rename the namespace casually.

Before opening a pull request:

```bash
uv sync
uv run pytest tests -q --tb=short
uv run ruff format --check .
uv run ruff check .
uv run mypy src
```

Frontend changes also require `cd aii-web && pnpm install --frozen-lockfile &&
pnpm type-check && pnpm build`. Database changes require disposable PostgreSQL
migration tests and an upgrade/data-preservation note.

PostgreSQL is the sole canonical authority; indexes and projections are
rebuildable. Preserve authenticated owner checks, route retrieval through
`KnowledgeView`, keep optional providers lazy, and add provenance, idempotency
and negative cross-user tests for new data paths. Never commit `.env`,
credentials, dumps, model files, caches or runtime outputs. Use small,
concern-focused commits and document operational/privacy impact in the PR.
