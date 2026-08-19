# Stratum + AII Monorepo

AII was originally split out of Stratum; keeping them in separate repos created
coordination overhead. This branch consolidates them into one repo, with
**Stratum as the base** (newer web framework + 3O libs + larger codebase) and
**AII contributing its PostgreSQL+pgvector foundation and knowledge engine**.

## Layout

```
stratum/                  # base: FastAPI backend + Next.js frontend
  src/stratum/            #   Stratum backend (DuckDB+LanceDB+Tantivy today → PG)
  stratum-web/            #   Stratum frontend (Next 16)
  aii/                    # subtree of soffy88/aii (history preserved)
    aii/                  #   AII backend (FastAPI, PG16+pgvector, knowledge engine)
    aii-web/              #   AII frontend (Next 16 + @helios/blocks)
    econ_pipeline/        #   economics knowledge flywheel
    math_pipeline/        #   math knowledge flywheel
    migrations/           #   AII PostgreSQL migrations
```

## Phased merge plan

- **P0 — Monorepo colocation** ✅: AII brought in via `git subtree`
  under `aii/`; pnpm workspace updated. Both services still run independently
  (each its own venv / DB). No behavior change.
- **P1 — Unify on PostgreSQL** ✅: migrated Stratum off DuckDB/LanceDB/Tantivy onto
  AII's PG16+pgvector (one instance, `stratum` + `aii` schemas).
- **P2 — Backend merge** ✅: AII routers mounted into Stratum SL's FastAPI app
  under `/api/aii/*` prefix. AII's asyncpg pool initialized in SL lifespan.
  API Key auth adapted in SL middleware for `/api/aii/*` routes.
  oskill monkey-patch + AII providers registered in SL startup.
  `aii_mount.py` is the single integration point.
- **P3 — Frontend merge** ✅: ported AII's pages into aii-web (Next.js).
- **P4 — Deploy unify** ✅: standalone `aii-backend` systemd service retired.
  AII routes served by `stratum-sl` (:9304) container. Frontend rewrites
  updated to point at stratum-sl. Pipeline services (feeder, flywheel,
  embed, OCR) remain as standalone systemd units (GPU/filesystem deps).

See the project memory `project_aii_merge.md` for the full decision record.
