# Stratum Service Layer (stratum-sl) — 设计 & 部署规范 v1.1

**版本**: v1.1  
**前一版本**: v1.0  
**日期**: 2026-06-01  
**作者**: Wiki (架构) / Claude (起草)  
**状态**: 生效 — 覆盖 v1.0

**v1.1 变更摘要**:
| 修订 | 内容 | 节 |
|------|------|----|
| R1 | changefeed.seq 改用显式 SEQUENCE (替代 BIGSERIAL/rowid) | §S9 |
| R2 | `query()` limit 推入 SQL，不再用 `fetchmany` 客户端裁剪 | §S0.6 |
| R3 | Dockerfile.sl CMD 显式 `--workers 1`，文档化单 writer 约束 | §R1 |
| R4 | TECHNICAL_DEBT 加 DuckDB FTS/VSS 评估项 (文档仅，不实施) | §T |
| R5 | 新增 §M6: stop 旧进程 → rename → start Docker 容器 时序 | §M6 |

---

## §0 概述

### §0.1 定位

`stratum-sl` (Service Layer) 是 Stratum 的**第二后端**，运行于 port **9304**，负责
SPEC 2 范围：笔记 CRUD、搜索、Agent 执行、收件箱、同步 (changefeed)、内容推荐、
标注、订阅、账单等。

第一后端 (`http_api/`, port 9302) 仍负责 SPEC 1 范围 (认证 / corpus 隔离 / share / 
DuckDB 元数据层)，两者通过 JWT 共享认证。

```
Browser / CLI
  │
  ├─→ 9302  stratum-api   (SPEC 1: auth, corpus, share, DuckDB)
  │
  └─→ 9304  stratum-sl    (SPEC 2: notes, search, inbox, sync, …)
              │
              └─→ PostgreSQL:5433  (pg_migrations 001–014)
```

### §0.2 运行时约束

| 属性 | 值 |
|------|----|
| Python | 3.14 |
| 框架 | FastAPI + uvicorn |
| 数据库 | PostgreSQL 15 (psycopg2-binary) |
| Worker 数 | **1** (alpha 期单 writer，见 §R1 / §T) |
| JWT 密钥 | 共享 `JWT_SECRET` env var (来自 `~/.config/keys/.env`) |
| 部署 | Docker (`stratum-sl:latest`)，docker-compose service |

---

## §S0 DB 层 (PostgreSQL 辅助函数)

文件: `src/stratum/db/__init__.py`

> **偏差记录 (SPEC 1 §S0.6 deviation)**: 当前实现使用直接 psycopg2，
> 而非 `oprim.{db_insert, db_read, db_query, db_write, db_update, db_soft_delete}`。
> 原因: oprim 1.14.0 的 helpers 缺少连接池 + JSONB dict 序列化 + TEXT[] 透传。
> 待 oprim 增加连接池 wrapper 或 Stratum 迁移至 psycopg3 后恢复。

### §S0.1 DSN

```python
_DSN = os.environ.get(
    "STRATUM_DATABASE_DSN",
    "postgresql://stratum:stratum@localhost:5433/stratum",
)
```

Docker 运行时通过 docker-compose `environment` 覆盖为:
```
STRATUM_DATABASE_DSN=postgresql://stratum:stratum@172.20.0.1:5433/stratum
```
(`172.20.0.1` = Docker gateway，宿主机侧 PostgreSQL 暴露在 5433)

### §S0.2 连接管理

```python
@contextmanager
def _conn():
    """每次请求获取新连接，autocommit=False，成功 commit，异常 rollback。"""
    con = psycopg2.connect(_get_dsn())
    con.autocommit = False
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
```

> alpha 期一连接一请求，无连接池。beta 升级: pgbouncer 或 asyncpg connection pool。

### §S0.3 insert()

```python
def insert(table: str, data: dict[str, Any], returning: str = "id") -> Any:
    """INSERT 并返回 returning 列值。"""
```

### §S0.4 read()

```python
def read(table: str, rid: str, id_column: str = "id") -> dict[str, Any] | None:
    """按 id 查单行，返回 dict 或 None。"""
```

### §S0.5 write()

```python
def write(table: str, data: dict[str, Any], conflict_on: list[str] | None = None) -> Any:
    """INSERT … ON CONFLICT DO UPDATE (upsert)，返回 id。"""
```

### §S0.6 query() — ⚡ R2 修订

**v1.0 问题**: limit 通过 `cur.fetchmany(limit)` 在客户端截断，服务端仍全量执行查询。  
**v1.1 规范**: limit 必须推入 SQL `LIMIT` 子句，服务端提前终止执行。

```python
def query(
    sql: str, params: dict[str, Any] | tuple | None = None, limit: int = 100
) -> list[dict[str, Any]]:
    """执行 SELECT，返回 dict 列表。
    
    limit 通过 LIMIT 子句推入 SQL — 不使用 cursor.fetchmany()。
    调用方不得在 sql 中再写 LIMIT；函数自动追加。
    若 limit=0 则不追加（无限制，谨慎使用）。
    """
    if limit:
        sql = sql.rstrip(" ;") + f" LIMIT {limit}"
    with _conn() as con:
        with con.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]
```

> 调用示例 (sync.py):
> ```python
> rows = query(
>     "SELECT seq, event_id, event_type, payload, timestamp "
>     "FROM changefeed "
>     "WHERE user_id = %(uid)s AND seq > %(since)s "
>     "ORDER BY seq ASC",
>     {"uid": user_id, "since": since},
>     limit=limit,   # → 追加 "LIMIT 50" 到 SQL
> )
> ```

### §S0.7 update()

```python
def update(table: str, rid: str, data: dict[str, Any], id_column: str = "id") -> None:
    """按 id UPDATE 字段集合。"""
```

### §S0.8 soft_delete()

```python
def soft_delete(table: str, rid: str, deleted_at_column: str = "deleted_at") -> None:
    """SET deleted_at = NOW()。"""
```

---

## §S1–§S14 表 Schema (PG Migrations)

文件目录: `src/stratum/db/pg_migrations/`

| 序号 | 文件 | 核心表 |
|------|------|--------|
| 001 | (未列出) | 基础用户表 |
| 002 | 002_agent_runs_trace.sql | agent_runs_trace |
| 003 | 003_substrate_pin.sql | substrate_pin |
| 004 | 004_views.sql | views |
| 005 | 005_platform_content.sql | platform_content |
| 006 | 006_pgvector.sql | 向量索引扩展 |
| 007 | 007_highlights.sql | highlights |
| 008 | 008_subscriptions.sql | subscriptions |
| 009 | 009_changefeed.sql | **changefeed** (见 §S9) |
| 010 | 010_recommendations.sql | recommendations |
| 011 | 011_notes.sql | notes |
| 012 | 012_concepts.sql | concepts |
| 013 | 013_scheduled_job_runs.sql | scheduled_job_runs |
| 014 | 014_fix_user_id_type.sql | 修复 user_id 类型 |

### §S9 changefeed — ⚡ R1 修订

**v1.0 问题**: `seq BIGSERIAL PRIMARY KEY` 使用隐式序列。BIGSERIAL 的序列名与表名
绑定 (`changefeed_seq`)，在表 rename / partition attach 等 DDL 操作后序列名可能发生
漂移，rowid 语义不稳定。  
**v1.1 规范**: 使用显式具名 SEQUENCE，seq 列通过 `nextval()` 绑定。

```sql
-- src/stratum/db/pg_migrations/009_changefeed.sql  (v1.1 规范)

CREATE SEQUENCE IF NOT EXISTS changefeed_seq START 1;

CREATE TABLE IF NOT EXISTS changefeed (
    seq       BIGINT      DEFAULT nextval('changefeed_seq') PRIMARY KEY,
    event_id  TEXT        NOT NULL UNIQUE,
    user_id   UUID        NOT NULL,
    device_id TEXT        NOT NULL DEFAULT 'server',
    timestamp TIMESTAMP   NOT NULL DEFAULT NOW(),
    event_type TEXT       NOT NULL,
    payload   JSONB       NOT NULL DEFAULT '{}',
    processed BOOLEAN     DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_cf_user_seq ON changefeed(user_id, seq DESC);
CREATE INDEX IF NOT EXISTS idx_cf_type     ON changefeed(event_type);
```

> `sync.py` 直接 `SELECT seq`，不需要 alias（seq 列名即主键名，无歧义）。

---

## §R 运行时

### §R1 Dockerfile.sl — ⚡ R3 修订

**v1.0 问题**: CMD 未显式指定 `--workers`，uvicorn 默认推断 CPU 核数，可能启动多
worker 进程共享同一 DuckDB writer 文件锁，引发 write 冲突。  
**v1.1 规范**: CMD 必须显式 `--workers 1`。

```dockerfile
# deploy/Dockerfile.sl  (v1.1 规范)

CMD ["uvicorn", "stratum.api.main:app",
     "--host", "0.0.0.0",
     "--port", "9304",
     "--workers", "1"]
```

**单 writer = alpha OK，beta 需评估替代**:
- alpha 期单用户，单 worker 无并发瓶颈
- beta 水平扩展候选方案 (Phase 14.5 决策点):
  - 方案 A: 迁移至 asyncpg async pool，多 worker 共享 PG 连接池
  - 方案 B: 前置 pgbouncer transaction pool，多 worker 复用连接
  - 方案 C: DuckDB 部分迁移至 PG (目前 DuckDB 仍用于 SPEC 1 元数据)
- 触发条件: 100+ 并发用户 / P50 响应 >500ms

### §R2 docker-compose 条目

```yaml
# deploy/docker-compose.yml  (stratum-sl service)

stratum-sl:
  image: stratum-sl:latest
  build:
    context: /home/soffy/projects
    dockerfile: stratum/deploy/Dockerfile.sl
  container_name: stratum-sl
  restart: unless-stopped
  ports:
    - "127.0.0.1:9304:9304"
  env_file:
    - /home/soffy/.config/keys/.env
  environment:
    - STRATUM_DATABASE_DSN=postgresql://stratum:stratum@172.20.0.1:5433/stratum
  volumes:
    - /home/soffy/projects/platform/obase:/opt/platform/obase
    - /home/soffy/projects/platform/oprim:/opt/platform/oprim
    - /home/soffy/projects/platform/oskill:/opt/platform/oskill
    - /home/soffy/projects/platform/omodul:/opt/platform/omodul
    - ~/.stratum:/root/.stratum
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:9304/api/v1/health"]
    interval: 30s
    timeout: 5s
    retries: 3
```

---

## §A 路由目录 (20 routers, ~40 endpoints)

| Router 文件 | 前缀 | 代表性 endpoint |
|-------------|------|----------------|
| account.py | `/api/v1/account` | POST /delete |
| agents.py | `/api/v1/agents` | POST /{name}/run, GET /{name}/runs |
| billing.py | `/api/v1/billing` | POST /subscribe, GET /subscription |
| bookmarks.py | `/api/v1/bookmarks` | POST / GET |
| concepts.py | `/api/v1/concepts` | CRUD + GET /graph/:id |
| content.py | `/api/v1/content` | GET /feed, GET /:id |
| highlights.py | `/api/v1/highlights` | POST / GET / DELETE |
| inbox.py | `/api/v1/inbox` | POST /submit, POST /web-clip |
| interactions.py | `/api/v1/interactions` | POST/GET /content/:id/progress |
| notes.py | `/api/v1` | POST/GET/PUT/DELETE /notes |
| notifications.py | `/api/v1/notifications` | POST /send |
| recommendations.py | `/api/v1/recommendations` | GET / |
| search.py | `/api/v1/search` | POST /search |
| substrate.py | `/api/v1/substrates` | POST /:id/pin, POST /:id/unpin |
| sync.py | `/api/v1/sync` | GET /status, GET /changefeed |
| translate.py | `/api/v1/translate` | POST /substrate/:id, GET /detect/:id |
| views.py | `/api/v1/views` | POST / GET / PUT |

---

## §M 部署流程

### §M1 PostgreSQL 准备

```bash
# 确认 postgres 容器运行
docker ps | grep deploy-postgres-1
# 期待: Up, healthy

# 确认 stratum DB 可访问
psql postgresql://stratum:stratum@localhost:5433/stratum -c "\dt" | wc -l
# 期待: >= 14 行 (14 张表)
```

### §M2 运行 PG Migrations

```bash
cd ~/projects/stratum
python3 -c "
import psycopg2
import os
from pathlib import Path

dsn = os.environ.get('STRATUM_DATABASE_DSN', 'postgresql://stratum:stratum@localhost:5433/stratum')
migs = sorted(Path('src/stratum/db/pg_migrations').glob('*.sql'))
con = psycopg2.connect(dsn)
con.autocommit = True
with con.cursor() as cur:
    for m in migs:
        print(f'  applying {m.name}')
        cur.execute(m.read_text())
con.close()
print('Done')
"
```

### §M3 Build stratum-sl 镜像

```bash
# 构建上下文必须是 /home/soffy/projects (包含 platform/ 和 stratum/)
cd /home/soffy/projects
docker build -f stratum/deploy/Dockerfile.sl -t stratum-sl:latest .
# 期待: Successfully tagged stratum-sl:latest
```

### §M4 验证 PG 连接 (容器内)

```bash
docker run --rm \
  -e STRATUM_DATABASE_DSN="postgresql://stratum:stratum@172.20.0.1:5433/stratum" \
  stratum-sl:latest \
  python3 -c "
from stratum.db import query
rows = query('SELECT COUNT(*) AS n FROM changefeed', limit=1)
print('changefeed rows:', rows[0]['n'])
"
# 期待: changefeed rows: <N> (无异常)
```

### §M5 启动 stratum-sl 容器

```bash
cd ~/projects/stratum/deploy
docker compose up -d stratum-sl
sleep 5
curl -f http://localhost:9304/api/v1/health
# 期待: 200 {"status":"ok"}
```

### §M6 — ⚡ R5 新增: 裸进程 → Docker 容器 切换时序

**背景**: 当前宿主机上可能仍有裸进程 `uvicorn stratum.api.main:app --port 9304` 运行
(源自 P0-1 修复前的临时进程，pid 约 3541718)。需原子切换至 Docker 容器。

**约束**: 公网瞬间停 5–10 秒可接受 (alpha 单用户环境)。

**步骤**:

```bash
# 1. Stop — 停裸进程 (释放 9304 端口)
OLD_PID=$(lsof -ti tcp:9304 2>/dev/null || echo "")
if [ -n "$OLD_PID" ]; then
  echo "Stopping bare process pid=$OLD_PID on port 9304"
  kill "$OLD_PID"
  sleep 2
fi

# 2. Verify — 确认端口已释放
lsof -ti tcp:9304 && echo "WARNING: port still in use" || echo "Port 9304 free"

# 3. Start — 启动 Docker 容器 (映射到同一端口)
cd ~/projects/stratum/deploy
docker compose up -d stratum-sl

# 4. Healthcheck — 等容器健康
sleep 5
curl -f http://localhost:9304/api/v1/health \
  && echo "stratum-sl Docker container UP" \
  || echo "ERROR: health check failed"

# 5. Verify restart policy — 确认 unless-stopped 生效
docker inspect stratum-sl | python3 -c "
import json, sys
d = json.load(sys.stdin)[0]
rp = d['HostConfig']['RestartPolicy']['Name']
print(f'RestartPolicy: {rp}')
assert rp == 'unless-stopped', 'FAIL: restart policy not set'
print('PASS')
"
```

**回滚**: 若 Docker 启动失败，`docker compose down stratum-sl` 后重新拉起裸进程:
```bash
cd ~/projects/stratum
nohup uvicorn stratum.api.main:app --host 127.0.0.1 --port 9304 --workers 1 \
  > /tmp/stratum-sl.log 2>&1 &
echo "Bare process fallback PID=$!"
```

---

## §T Technical Debt

### §T1 DB 层偏差 (继承自 v1.0)

见 TECHNICAL_DEBT.md §DB Layer:
- `SPEC 1 §S0.6 deviation`: psycopg2 直调，未用 oprim helpers
- `IngestResult.substrate_id` repr bug (omodul 1.14.0)

### §T2 进程模型限制 (继承自 v1.0)

- `--workers 1` 单 worker = alpha OK，beta 前需评估连接池方案 (见 §R1)
- DedupCache 进程内存 → 多 worker 无法共享，beta 前换 Redis (见 common.py)

### §T3 — ⚡ R4 新增: DuckDB 搜索扩展评估

**触发条件**: Phase 14.5 alpha 用户反馈 / 100+ 注册引流后

#### §T3.1 DuckDB FTS Extension 评估

- **目标**: 评估 DuckDB `fts` 扩展能否替代当前 PostgreSQL `to_tsvector / GIN` 方案
  (SPEC 2 文本搜索路径)
- **评估维度**:
  - BM25 召回质量 vs PG to_tsvector (中文分词支持)
  - 写入延迟 (DuckDB 单 writer vs PG 并发写)
  - 索引大小对比
  - FTS + 向量混合排序可行性
- **候选迁移路径**: SPEC 2 search.py `POST /search` → DuckDB FTS + LanceDB 向量双路召回
- **优先级**: P2 (Phase 14.5 决策点)
- **参考**: DuckDB `INSTALL fts; LOAD fts; PRAGMA create_fts_index(...)`

#### §T3.2 DuckDB VSS Extension 评估

- **目标**: 评估 DuckDB `vss` 扩展能否替代当前 PostgreSQL `pgvector / ivfflat` 方案
  (SPEC 2 语义搜索路径)
- **评估维度**:
  - HNSW ANN 召回质量 vs pgvector ivfflat
  - 向量维度支持 (≥1024 dim Qwen3 embeddings)
  - DuckDB 单文件部署优势 (简化 alpha 基础设施)
  - 写放大 / 索引重建开销
- **候选迁移路径**: migration 006_pgvector.sql → DuckDB VSS (减少外部服务依赖)
- **优先级**: P2 (Phase 14.5 决策点)
- **参考**: DuckDB `INSTALL vss; LOAD vss; CREATE INDEX ... USING HNSW(...)`

---

## §V 验收标准 (v1.1 sign-off)

```bash
# 1. 服务启动健康
curl -f http://localhost:9304/api/v1/health  # → 200

# 2. changefeed 序列可用
psql postgresql://stratum:stratum@localhost:5433/stratum -c "
  SELECT nextval('changefeed_seq') AS next_seq;
"  # → 返回整数, 无报错

# 3. sync.py 直接 SELECT seq (无 alias 需求)
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:9304/api/v1/sync/changefeed?since=0&limit=10"
# → {"events": [...], "latest_seq": <int>, "has_more": false}

# 4. query() LIMIT 走 SQL (验证: explain 含 LIMIT)
python3 -c "
from stratum.db import query
import os; os.environ['STRATUM_DATABASE_DSN']='postgresql://stratum:stratum@localhost:5433/stratum'
rows = query('SELECT seq FROM changefeed WHERE user_id IS NOT NULL ORDER BY seq DESC', limit=5)
print(f'Returned {len(rows)} rows (<= 5)')
assert len(rows) <= 5
print('PASS')
"

# 5. Docker workers=1
docker inspect stratum-sl | python3 -c "
import json, sys
d = json.load(sys.stdin)[0]
cmd = d['Config']['Cmd']
assert '--workers' in cmd and cmd[cmd.index('--workers')+1] == '1', f'FAIL: workers not 1. Cmd={cmd}'
print('workers=1 PASS')
"
```

---

**End STRATUM_SL_SPEC v1.1**

— Stratum 经理人 Claude  
2026-06-01
