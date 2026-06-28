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

- **P0 — Monorepo colocation (this branch)**: AII brought in via `git subtree`
  under `aii/`; pnpm workspace updated. Both services still run independently
  (each its own venv / DB). No behavior change.
- **P1 — Unify on PostgreSQL**: migrate Stratum off DuckDB/LanceDB/Tantivy onto
  AII's PG16+pgvector (one instance, `stratum` + `aii` schemas). Stratum already
  has PG scaffolding (`src/stratum/db/__init__.py.pg-backup`, `pg_migrations/`).
- **P2 — Backend merge**: mount AII routers into Stratum's FastAPI app; adapt AII
  code to Stratum's newer 3O libs (oskill 4.3.0); replace the `~/shared/*` file
  hand-off with in-process / same-DB calls.
- **P3 — Frontend merge**: port AII's pages into stratum-web.
- **P4 — Deploy unify + decommission** the old separate services.

See the project memory `project_aii_merge.md` for the full decision record.
