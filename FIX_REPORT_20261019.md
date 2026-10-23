# Stratum Deployment Fix — 2026-10-19

## 1. Chosen data dir (stratum-api)

**Chosen: `/mnt/d/stratum`** (this is what `~/.stratum` resolves to — a symlink
`/home/soffy/.stratum -> /mnt/d/stratum`).

| | hand-run container (`~/stratum-data`) | compose (`~/.stratum` → `/mnt/d/stratum`) |
|---|---|---|
| path | `/home/soffy/stratum-data` | `/mnt/d/stratum` |
| files | 383 | 33,863 |
| size | 72 MB | 25 GB |
| newest mtime | 2026-09-13 | 2026-10-18 |
| DB | none | `meta.duckdb` (1.6 MB, Sep 22) |

`/mnt/d/stratum` is the real, actively-used data dir (it is also what the live
`stratum-sl` container mounts and writes `vault/`, `notes/`, `index/`, and
`meta.duckdb` to). The hand-run container was pointed at the stale
`/home/soffy/stratum-data` (72 MB, untouched since Sep 13). **No data was
deleted, overwritten, or merged** — the stale dir was left in place and the
compose mount was made to point explicitly at the real dir.

## 2. Files changed

- `deploy/docker-compose.yml`
  - `stratum-api` port: `0.0.0.0:9309:9302` → `127.0.0.1:9309:9302` (loopback
    only, matching the hand-run container; caddy/stratum-sl reach it over
    `stratum-net` via docker DNS `stratum-api:9302`).
  - `stratum-api` volume: `~/.stratum:/root/.stratum` →
    `/mnt/d/stratum:/root/.stratum` (explicit real data dir).
  - Removed stale `DATABASE_PATH=/data/stratum/meta.duckdb` (dead — no code
    reads it; the store moved to aii-postgres).
- `deploy/Dockerfile.api`
  - Added embedding stack to `pip install`: `dashscope FlagEmbedding
    sentence-transformers torch`.
  - Rebuilt image `stratum-api:latest` (was 1.12 GB → now 10.4 GB; size grew
    because `torch` pulls CUDA runtime packages on PyPI by default — a
    CPU-only `torch` (`--index-url https://download.pytorch.org/whl/cpu`) would
    shrink it, but is not required for correctness).

Embedding libs the API code actually imports (verified via grep + import test):
- `dashscope` — `oprim/embedding/qwen3_dashscope.py` (top-level import, default
  `EMBEDDING_PROVIDER=qwen3_dashscope`).
- `FlagEmbedding` / `sentence_transformers` — `oprim/embedding/bge_m3.py`
  (`BgeM3Embedder`) and `src/stratum/services/visual_embedding.py`.
- `torch` — `src/stratum/services/visual_embedding.py` + runtime for the above.

## 3. Backup path

`/data/soffy/backups/stratum-20261019-011839/`

- `configs/` — docker-compose.yml, docker-compose.oss.yml, .env(.example),
  aii-secrets.conf, `/home/soffy/.config/keys/.env`, aegis `Caddyfile`, all
  Dockerfiles.
- `stratum-data.tar.gz` — `/home/soffy/stratum-data` (45 MB).
- `stratum-mnt-d.tar.gz` — `/mnt/d/stratum` (24 GB, full tar of the real data dir).

## 4. Verification results

| check | result |
|---|---|
| `curl 127.0.0.1:9309/health` | **200** `{"status":"healthy","database":"connected"}` |
| stratum-sl health (`127.0.0.1:9304/api/v1/health`) | **200** `{"status":"ok",...,"embedding":{"backend":"eg2","ok":true}}` |
| `https://stratum.kanpan.co/health` | **200** (reachable; public host routes to the aii-web frontend, which serves `/health` as a page — pre-existing routing, out of scope) |
| caddy → `stratum-api:9302/health` (from aegis-caddy) | **200** healthy |
| `docker logs stratum-api --since 5m` | no embedding errors, no import errors |
| embedding libs in running container | `dashscope`, `FlagEmbedding`, `sentence_transformers`, `torch` all import OK |

Container state:
- `stratum-api` — Up (healthy), `127.0.0.1:9309->9302`, network `stratum-net`.
- `stratum-docs` — Up (healthy), `127.0.0.1:8300->8300`, network `stratum-net`.
- `stratum-sl`, `stratum-web` — unchanged, still healthy.

## 5. Rollback command

The old container was kept **stopped, not deleted**, as `stratum-api-old`
(image `0d3052c65e83`).

```bash
docker stop stratum-api \
  && docker rename stratum-api stratum-api-new \
  && docker rename stratum-api-old stratum-api \
  && docker start stratum-api
```

## 6. REPLACE_ME keys still needing user values (NOT invented)

Present in `/home/soffy/.config/keys/.env` (and `deploy/.env`), left untouched:

- `DASHSCOPE_API_KEY` (`REPLACE_ME_DASHSCOPE`)
- `SEARXNG_URL` (`REPLACE_ME_SEARXNG_URL`)
- `STRATUM_STRIPE_SECRET` (`REPLACE_ME_STRIPE_SECRET`)
- `STRATUM_STRIPE_WEBHOOK_SECRET` (`REPLACE_ME_STRIPE_WEBHOOK_SECRET`)
- `STRATUM_WECHAT_APP_ID` (`REPLACE_ME_WECHAT_APP_ID`)
- `STRATUM_WECHAT_APP_SECRET` (`REPLACE_ME_WECHAT_APP_SECRET`)
- `STRATUM_WECHAT_TOKEN` (`REPLACE_ME_WECHAT_TOKEN`)
- `STRATUM_WECHAT_MCH_ID` (`REPLACE_ME_WECHAT_MCH_ID`)
- `STRATUM_WECHAT_API_KEY` (`REPLACE_ME_WECHAT_PAY_API_KEY`)
- `STRATUM_SMTP_HOST` (`REPLACE_ME_SMTP_HOST`)
- `STRATUM_SMTP_USER` (`REPLACE_ME_SMTP_USER`)
- `STRATUM_SMTP_PASS` (`REPLACE_ME_SMTP_PASS`)
- `STRATUM_TUNNEL_TOKEN` (`REPLACE_ME_STRATUM_CF_TUNNEL_TOKEN`)

(`NVIDIA_NIM_API_KEY`, `LX_API_KEY`, `STRATUM_API_KEY`, `STRATUM_PG_PASSWORD`
have real values and were not touched.)

## 7. stratum-docs status

`stratum-docs` **was** defined in `deploy/docker-compose.yml` but not running.
It has now been **built** (`docker compose build stratum-docs`) and **started**
(`docker compose up -d stratum-docs`). It is healthy, on `stratum-net`, listening
on `127.0.0.1:8300`, and reachable from aegis-caddy via docker DNS
`stratum-docs:8300` (the Caddyfile `handle /docs/*` route). Its own
`/health` returns `{"ok":true,"service":"stratum-docs"}` (200).

## Notes

- Docker build cache was pruned after the two builds to reclaim ~14 GB; the
  host data volume (`/data`) was at 95% used before this work and remains tight.
- The rebuilt `stratum-api` image includes the CUDA variant of `torch` (PyPI
  default), which accounts for most of the 10.4 GB image size. The API runs on
  CPU and delegates heavy embedding to the shared aii-embed service
  (`EMBEDDING_PROVIDER=aii_remote` for `stratum-sl`); switching to CPU-only
  `torch` is a safe follow-up if image size matters.
