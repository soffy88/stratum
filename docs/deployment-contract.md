# AII deployment contract

The portable production topology is:

```text
client → reverse proxy/TLS → AII API → PostgreSQL + pgvector
                                   ├→ rebuildable lexical/vector indexes
                                   └→ optional providers (embedding, OCR, visual)
```

PostgreSQL (`aii_kg`, `stratum` and `aii` schemas) is the sole canonical
authority. Sources, Fragments, Evidence, Claims, projections and Artifacts do
not fall back to a local file database. Indexes are rebuildable projections.

The API is stateless apart from PostgreSQL and explicitly configured object/blob
storage. Migration, scheduler and watcher processes are separate concerns from
the API and web services;
the API does not silently start them. Apply migrations before accepting traffic:

```bash
python -m stratum.db.run_pg_migrations upgrade
```

Required configuration is supplied by a secret manager or an untracked env
file: database name/user/password, `JWT_SECRET`, public origin and CORS
allowlist. Absolute developer paths, dynamic `sys.path`, fixed Ollama hosts and
source-tree bind mounts are not production configuration. Health/readiness must
distinguish canonical DB failure from optional provider degradation.

Build from a tagged commit and pin base images in deployment automation.
Rollback uses the prior image/tag; migrations are forward-compatible and must
not require destructive rollback.

The OSS Compose file exposes the API on loopback port 9302 and the web UI on
loopback port 3000. Put TLS, public routing, rate limiting and authentication
policy in an operator-controlled reverse proxy; do not publish PostgreSQL
directly to the internet.
