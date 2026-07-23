# PHASE 15 — alpha v0.7 P1 功能补足 CC 执行指令书

**项目**: stratum-web alpha v0.7 — P1 功能补足
**前置**: Phase 14 全完工 + Phase 14.5 装配 + SPEC v0.5/v0.6 / SPEC v1.1 DB 合并完成
**执行**: CC FULL AUTO, 4 Wave
**预算**: 2-3 周
**目标**: 把 alpha 从"装样子"升级到"真能用"

---

## §0 范围声明 (R-4)

✅ 允许:
- 新加路由 (Scheduler CRUD / Agent run detail / changefeed event types)
- 改 Stratum 服务层 `src/stratum/api/routers/*.py`
- 改 Stratum 调用 `~/projects/platform/omodul` API (不改 omodul 本身, 只调)
- 改 stratum-web 前端组件 (AgentRunPanel / SearchPanel 等已有组件)
- 灌入测试 platform_content (用 Stratum 自己的任务书 markdown)
- 改 scheduler 容器 + ws 广播逻辑

❌ 禁止:
- 改 `~/projects/platform/omodul/oskill/oprim/obase` 任何代码
- 改 DB schema (DB 合并刚 ship, 不再动 migration)
- 改 Phase 14 DuckDB API (`/api/*`), 只动新 SL API (`/api/v1/*`)
- 改 nginx / docker-compose 架构

如发现必须改 platform/* → 立即停报告, 不擅自改。

---

## §1 R-1 ~ R-6 (沿用)

### R-1 失败不静默
- AI Agent 触发返 status=pending = stub 没真触发, 必须 catch
- 每 P1 项完工时验证"真触发"而非"代码写完"
- 用 curl 真调 endpoint 看 response 是真数据还是 mock

### R-3 真实示例强制
- 每个补足 endpoint 必须有真实 curl + 真后端验证
- AI Agent 真返回 findings / citations, 不接受 "completed" 但 findings=null
- 平台内容灌入后 /discover 真显示 (Playwright e2e 验证)

### R-4 严格范围
见 §0。

### R-5 namespace
改动文件清单:
```
src/stratum/api/routers/agents.py            # P1-A1 + A3 + B3
src/stratum/api/routers/scheduled_jobs.py    # P1-B2 (新建)
src/stratum/api/routers/sync.py              # P1-C1
src/stratum/api/ws.py                        # P1-C2
src/stratum/services/scheduler/main.py       # P1-B1
stratum/api/routers/inbox.py 等             # P1-B4 changefeed event 补
stratum-web/src/components/AgentRunPanel.tsx  # 改, 接 detail endpoint
stratum-web/src/app/(app)/agents/runs/[id]/page.tsx  # P1-B3 新建
tests/service_layer/test_*.py                # 测试补
data/platform_content_seed/                  # 灌入数据 (markdown)
scripts/seed_platform_content.py            # 灌入脚本 (新建)
```

### R-6 破坏性操作
- 不删 PG volume (R6-6 1 周后再确认)
- 不改任何已 ship 的 endpoint 行为 (向后兼容)
- 灌入 platform_content 操作 = 写表, 不动 schema

---

## §2 Wave 1 — P1-A 体验黑洞 (1 周)

### 2.1 A1: AI Agent 真触发

#### 当前问题

`POST /api/v1/agents/:agent_name/run` 返:
```json
{"status": "pending", "findings": null}
```

预期: 真返回 Agent 结果 (omodul 的 daily_digest / reading_companion / knowledge_curator)。

#### 实施

文件: `src/stratum/api/routers/agents.py` (SPEC 2 §R2.2 当时已写 90%, 现在补真触发):

```python
import asyncio
from fastapi import APIRouter, Depends, HTTPException

from stratum.common import jwt_auth, user_agent_runs_dir, ensure_dir, generate_ulid, now_utc
from stratum.db import insert, read

# 6 Agent 全注册 (P1-A3)
from omodul import (
    daily_digest_workflow, DailyDigestConfig, DailyDigestInput,
    process_inbox_batch, InboxBatchConfig, InboxBatchInput,
    translate_substrate_workflow, TranslateConfig, TranslateInput,
    reading_companion_workflow, ReadingCompanionConfig, ReadingCompanionInput,
    weekly_review_workflow, WeeklyReviewConfig, WeeklyReviewInput,
    lint_knowledge_base_workflow, LintConfig, LintInput,
)

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])

AGENT_REGISTRY = {
    "daily_digest": (daily_digest_workflow, DailyDigestConfig, DailyDigestInput),
    "knowledge_curator": (process_inbox_batch, InboxBatchConfig, InboxBatchInput),
    "translation_worker": (translate_substrate_workflow, TranslateConfig, TranslateInput),
    "reading_companion": (reading_companion_workflow, ReadingCompanionConfig, ReadingCompanionInput),
    "weekly_review": (weekly_review_workflow, WeeklyReviewConfig, WeeklyReviewInput),
    "lint_bot": (lint_knowledge_base_workflow, LintConfig, LintInput),
}


@router.post("/{agent_name}/run")
async def agent_run(agent_name: str, params: dict = {}, user_id: str = Depends(jwt_auth)):
    if agent_name not in AGENT_REGISTRY:
        raise HTTPException(404, f"Unknown agent: {agent_name}. Available: {list(AGENT_REGISTRY.keys())}")

    omodul_fn, cfg_cls, inp_cls = AGENT_REGISTRY[agent_name]
    out_dir = ensure_dir(user_agent_runs_dir(user_id))

    # 创建 agent_run record (started)
    run_id = generate_ulid()
    insert("agent_runs", {
        "id": run_id, "user_id": user_id, "agent_name": agent_name,
        "params": params, "status": "running",
        "started_at": now_utc(),
    })

    try:
        config = cfg_cls(
            **(params.get("config") or {}),
            llm_provider="qwen3", llm_model="qwen3-max",
        )
        input_data = inp_cls(**(params.get("input") or {}))

        result = await asyncio.to_thread(
            omodul_fn, config=config, input_data=input_data, output_dir=out_dir,
        )

        # 更新 agent_run record (completed/failed)
        from stratum.db import update
        update("agent_runs", run_id, {
            "status": result.get("status", "failed"),
            "completed_at": now_utc(),
            "trace": result.get("trace"),
            "citations": result.get("citations"),
            "files_generated": result.get("files_generated"),
            "error": result.get("error", {}).get("error_message") if result.get("error") else None,
        })

    except Exception as e:
        from stratum.db import update
        update("agent_runs", run_id, {
            "status": "failed", "completed_at": now_utc(),
            "error": str(e),
        })
        raise HTTPException(500, f"Agent {agent_name} failed: {e}")

    return {
        "run_id": run_id,
        "agent_name": agent_name,
        "status": result["status"],
        "findings": result["findings"].model_dump() if result.get("findings") else None,
        "report_fingerprint": result.get("fingerprint"),
        "citations": result.get("citations"),
        "error": result.get("error"),
    }


# P1-B3: GET /api/v1/agents/runs (list) + GET /api/v1/agents/runs/{run_id} (detail)

@router.get("/runs")
async def list_runs(agent: str | None = None, user_id: str = Depends(jwt_auth)):
    from stratum.db import query
    if agent:
        rows = query(
            "SELECT * FROM agent_runs WHERE user_id = $uid AND agent_name = $agent ORDER BY started_at DESC",
            {"uid": user_id, "agent": agent},
            limit=20,
        )
    else:
        rows = query(
            "SELECT * FROM agent_runs WHERE user_id = $uid ORDER BY started_at DESC",
            {"uid": user_id},
            limit=20,
        )
    return {"items": rows, "total": len(rows)}


@router.get("/runs/{run_id}")
async def get_run(run_id: str, user_id: str = Depends(jwt_auth)):
    run = read("agent_runs", run_id)
    if not run or run.get("user_id") != user_id:
        raise HTTPException(404, "Agent run not found")
    return run
```

#### 测试

```python
# tests/service_layer/test_agents_run.py
def test_agent_run_returns_completed(client_with_jwt):
    """POST /api/v1/agents/daily_digest/run 真返回 completed, 非 pending"""
    resp = client_with_jwt.post("/api/v1/agents/daily_digest/run", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("completed", "failed"), f"got {data['status']}"  # 不接受 pending
    # findings 可能 None (alpha 期 corpus 空, daily_digest 没东西可 digest), 但 status 必须真终态

def test_agent_unknown_returns_404(client_with_jwt):
    resp = client_with_jwt.post("/api/v1/agents/foo/run", json={})
    assert resp.status_code == 404

def test_agent_run_persisted(client_with_jwt):
    """agent_runs 表真写入 record"""
    resp = client_with_jwt.post("/api/v1/agents/daily_digest/run", json={})
    run_id = resp.json()["run_id"]
    
    # GET detail
    detail = client_with_jwt.get(f"/api/v1/agents/runs/{run_id}")
    assert detail.status_code == 200
    assert detail.json()["status"] in ("completed", "failed")
```

#### 风险 + fallback

⚠️ R-1: 如果 omodul Agent 实施跟 SPEC 2 不一致 (函数签名差 / Pydantic 模型缺), CC 必须报告:
- 报告: 缺失的 Agent / 函数签名差异 / Stratum 服务层期望的 vs 真实施的
- 不擅自适配 (R-4)
- 等 advisor 决策 (跟 omodul owner 协调 / Stratum 服务层降级 / 推 v1.1)

### 2.2 A2: 灌入平台内容 (Stratum 任务书)

#### 实施

新建脚本: `scripts/seed_platform_content.py`

```python
"""灌入 3-5 个平台内容到 DuckDB platform_content 表.
内容来源: Stratum 自己的任务书 markdown (build in public).
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from stratum.common import generate_ulid, now_utc
from stratum.db import insert
import duckdb

SEED_ITEMS = [
    {
        "title": "Phase 14: stratum-web SaaS Alpha 完整实施过程",
        "type": "article",
        "author": "wiki",
        "body_markdown_path": "docs/PHASE_14_PART1_BACKEND_CC_v1.0.md",
        "domain": ["engineering", "knowledge_management"],
        "tags": ["phase14", "saas", "build_in_public"],
    },
    {
        "title": "Phase 14.5: 前端装配 (后端有前端缺补全)",
        "type": "article",
        "author": "wiki",
        "body_markdown_path": "docs/PHASE_14_5_FRONTEND_WIRING_CC_v1.0.md",
        "domain": ["engineering", "frontend"],
        "tags": ["phase14.5", "frontend", "build_in_public"],
    },
    {
        "title": "STRATUM SL SPEC v1.1: DB 合并 PG → DuckDB",
        "type": "article",
        "author": "wiki",
        "body_markdown_path": "docs/design/STRATUM_SL_SPEC_v1.1.md",
        "domain": ["engineering", "architecture"],
        "tags": ["spec", "database", "build_in_public"],
    },
    {
        "title": "Stratum 全 API 规约 v1",
        "type": "reference",
        "author": "wiki",
        "body_markdown_path": "docs/STRATUM_API_v1.md",
        "domain": ["engineering", "api"],
        "tags": ["api", "openapi", "reference"],
    },
]


def seed():
    for item in SEED_ITEMS:
        path = Path(item["body_markdown_path"])
        if not path.exists():
            print(f"⚠️ skip {path}: not found")
            continue
        
        body = path.read_text(encoding="utf-8")
        
        record_id = generate_ulid()
        insert("platform_content", {
            "id": record_id,
            "type": item["type"],
            "title": item["title"],
            "author": item["author"],
            "body_markdown": body,
            "body_html": None,  # 渲染在前端
            "published_at": now_utc(),
            "version": 1,
            "domain": item["domain"],
            "tags": item["tags"],
            "access_tier": "free",
        })
        print(f"✅ seeded: {item['title']} ({record_id})")


if __name__ == "__main__":
    seed()
```

执行:
```bash
cd ~/projects/stratum
python3 scripts/seed_platform_content.py
```

#### 验证

```bash
# 公网 e2e
curl -s https://stratum.kanpan.co/api/v1/content/feed | jq '.items | length'
# 期待 ≥4

# 浏览器: 登录 → /discover 真显示 4 篇内容
# 点击某篇 → /content/:id 渲染 markdown
```

### 2.3 A3: AGENT_REGISTRY 补全 (跟 A1 一起做)

A1 §2.1 实施时已经包含 reading_companion / weekly_review / lint_bot (3 个新加)。

剩余:
- `audio_generator` — TTS 暂缓 (Phase 11B 决策), endpoint 返 not_implemented
- `concept_illustrator` — v2.0 (alpha 不必)
- `deep_researcher` — v2.0 (alpha 不必)

补 audio_generator stub:

```python
@router.post("/audio_generator/run")
async def audio_generator_run(params: dict = {}, user_id: str = Depends(jwt_auth)):
    """TTS Agent — alpha v0.7 暂缓 (Phase 11B 决策, TECHNICAL_DEBT 已登记)"""
    raise HTTPException(501, "audio_generator (TTS) 暂缓, v1.1 评估 F5-TTS 替代")
```

### 2.4 Wave 1 Gate

```bash
cd ~/projects/stratum
pytest tests/service_layer/test_agents_run.py -v --tb=short
pytest tests/ 2>&1 | tail -10  # 期待 226 + ≥3 新 = ≥229 pass

# seed 内容
python3 scripts/seed_platform_content.py

# 公网验证
curl -s https://stratum.kanpan.co/api/v1/content/feed | jq '.items | length'
curl -s -X POST https://stratum.kanpan.co/api/v1/agents/daily_digest/run -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{}' | jq

# 前端 e2e (Playwright)
cd stratum-web && pnpm test:e2e --grep "Phase 15 Wave 1"

git add -A && git commit -m "Phase 15 Wave 1 (P1-A): AI Agent 真触发 + 6 Agent 注册 + 平台内容 seed"
```

Wave 1 完工报告:
- AGENT_REGISTRY 6 个 + audio_generator stub
- platform_content 灌入 ≥4 条 + /discover 真显示
- agent_runs 表持久化记录
- 测试通过 + 公网 e2e
- commit hash

---

## §3 Wave 2 — P1-B 后端覆盖 (3-5 天)

### 3.1 B1: Scheduler 注册 6 builtin_jobs

文件: `src/stratum/services/scheduler/main.py`

```python
# 现状: 只注册 daily_digest

# 修改: 6 个 builtin_jobs 全注册
BUILTIN_JOBS = [
    {"name": "daily_digest", "cron": "0 8 * * *", "config": {}},
    {"name": "weekly_review", "cron": "0 9 * * 1", "config": {}},
    {"name": "knowledge_curator", "cron": "0 */6 * * *", "config": {}},
    {"name": "translation_worker", "cron": "0 2 * * *", "config": {}},
    {"name": "lint_bot", "cron": "0 3 * * *", "config": {}},
    {"name": "reading_companion", "cron": None, "config": {}},  # 用户手动触发
]

async def main():
    scheduler = AsyncIOScheduler()
    
    # 读 DB 中用户自定义 jobs
    user_jobs = load_jobs()  # SELECT * FROM scheduled_jobs WHERE enabled = TRUE
    
    # 加 builtin (硬编码, 不入 DB)
    for builtin in BUILTIN_JOBS:
        if builtin["cron"]:
            scheduler.add_job(
                execute_builtin_job, 
                CronTrigger.from_crontab(builtin["cron"]),
                args=[builtin],
                id=f"builtin_{builtin['name']}",
            )
    
    # 加用户 jobs (沿用现有逻辑)
    for job in user_jobs:
        ...
    
    scheduler.start()
    print(f"Scheduler started: {len(BUILTIN_JOBS)} builtin + {len(user_jobs)} user jobs")
```

### 3.2 B2: Scheduler CRUD API

新文件: `src/stratum/api/routers/scheduled_jobs.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from stratum.common import jwt_auth, generate_ulid, now_utc
from stratum.db import insert, read, query, update, soft_delete

router = APIRouter(prefix="/api/v1/scheduled-jobs", tags=["scheduled_jobs"])


class JobCreate(BaseModel):
    name: str
    agent_name: str
    cron_expression: str
    timezone: str = "Asia/Shanghai"
    enabled: bool = True
    max_items: int = 20


class JobUpdate(BaseModel):
    name: str | None = None
    cron_expression: str | None = None
    enabled: bool | None = None


@router.post("")
async def create_job(body: JobCreate, user_id: str = Depends(jwt_auth)):
    jid = generate_ulid()
    insert("scheduled_jobs", {
        "id": jid, "user_id": user_id,
        "name": body.name, "agent_name": body.agent_name,
        "cron_expression": body.cron_expression,
        "timezone": body.timezone, "enabled": body.enabled,
        "max_items": body.max_items,
        "created_at": now_utc(),
    })
    return {"job_id": jid, "status": "created"}


@router.get("")
async def list_jobs(user_id: str = Depends(jwt_auth)):
    return query(
        "SELECT * FROM scheduled_jobs WHERE user_id = $uid ORDER BY created_at DESC",
        {"uid": user_id},
    )


@router.put("/{job_id}")
async def update_job(job_id: str, body: JobUpdate, user_id: str = Depends(jwt_auth)):
    existing = read("scheduled_jobs", job_id)
    if not existing or existing.get("user_id") != user_id:
        raise HTTPException(404)
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    if changes:
        update("scheduled_jobs", job_id, changes)
    return {"job_id": job_id, "status": "updated"}


@router.delete("/{job_id}")
async def delete_job(job_id: str, user_id: str = Depends(jwt_auth)):
    existing = read("scheduled_jobs", job_id)
    if not existing or existing.get("user_id") != user_id:
        raise HTTPException(404)
    soft_delete("scheduled_jobs", job_id)
    return {"job_id": job_id, "status": "deleted"}


@router.post("/{job_id}/run-now")
async def run_job_now(job_id: str, user_id: str = Depends(jwt_auth)):
    """手动触发 — 调 agents/:agent_name/run 同步"""
    job = read("scheduled_jobs", job_id)
    if not job or job.get("user_id") != user_id:
        raise HTTPException(404)
    
    # 复用 agent_run 逻辑
    from stratum.api.routers.agents import agent_run
    return await agent_run(job["agent_name"], {}, user_id)


@router.get("/{job_id}/runs")
async def list_job_runs(job_id: str, user_id: str = Depends(jwt_auth)):
    """job 历史 runs"""
    job = read("scheduled_jobs", job_id)
    if not job or job.get("user_id") != user_id:
        raise HTTPException(404)
    
    return query(
        "SELECT * FROM scheduled_job_runs WHERE job_id = $jid ORDER BY started_at DESC",
        {"jid": job_id},
        limit=50,
    )
```

注册到 main.py:
```python
from stratum.api.routers import scheduled_jobs
app.include_router(scheduled_jobs.router)
```

### 3.3 B3: GET /api/v1/agents/runs/:run_id (已在 §2.1 一起实施)

### 3.4 B4: changefeed 补 10 event types

当前 3 种: `note_create`, `note_update`, `note_delete`

补 10 种:
```
substrate_create / substrate_delete / substrate_pin / substrate_unpin
concept_create / concept_update / concept_delete
agent_run_completed / agent_run_failed
highlight_create / highlight_delete
share_create / share_revoke
view_create / view_default_changed
profile_update
```

修改 routes:
- `substrate.py` pin/unpin → 加 changefeed_producer
- `concepts.py` create/update/delete → 加
- `agents.py` run 完成时 → 加 (status=completed/failed 各对应)
- `highlights.py` create/delete → 加
- `share.py` create/revoke → 加 (Phase 14 旧 endpoint, 也要补)
- `views.py` create/set-default → 加
- `profile.py` update → 加

每个 endpoint 加 1-2 行:
```python
from oprim import changefeed_producer

# 在 mutation 操作后:
changefeed_producer(event={
    "user_id": user_id, "device_id": "server",
    "timestamp": now_utc(), "event_type": "<event_name>",
    "payload": {"<entity>_id": <id>, ...},
})
```

### 3.5 Wave 2 Gate

```bash
pytest tests/service_layer/test_scheduled_jobs.py -v
pytest tests/service_layer/test_agents_run_detail.py -v
pytest tests/ 2>&1 | tail -10

# 端到端
curl -s -X POST https://stratum.kanpan.co/api/v1/scheduled-jobs -H "Authorization: Bearer $T" -d '{"name":"test","agent_name":"daily_digest","cron_expression":"0 8 * * *"}'

git add -A && git commit -m "Phase 15 Wave 2 (P1-B): Scheduler CRUD + Agent run detail + changefeed 13 events"
```

---

## §4 Wave 3 — P1-C 同步深度 (2-3 天)

### 4.1 C1: 同步范围加 substrates/highlights/concepts

文件: `src/stratum/api/routers/sync.py`

```python
@router.get("/changefeed")
async def pull_changefeed(
    since: int = 0, limit: int = 50,
    scope: list[str] = Query(default=["notes", "substrates", "highlights", "concepts"]),
    user_id: str = Depends(jwt_auth),
):
    # 按 scope 过滤 event_type
    event_types_by_scope = {
        "notes": ["note_create", "note_update", "note_delete"],
        "substrates": ["substrate_create", "substrate_delete", "substrate_pin", "substrate_unpin"],
        "highlights": ["highlight_create", "highlight_delete"],
        "concepts": ["concept_create", "concept_update", "concept_delete"],
    }
    
    allowed_types = []
    for s in scope:
        allowed_types.extend(event_types_by_scope.get(s, []))
    
    rows = query(
        "SELECT * FROM changefeed WHERE user_id = $uid AND seq > $since AND event_type IN $types ORDER BY seq ASC",
        {"uid": user_id, "since": since, "types": allowed_types},
        limit=limit,
    )
    
    return {
        "events": rows,
        "latest_seq": rows[-1]["seq"] if rows else since,
        "has_more": len(rows) == limit,
    }
```

### 4.2 C2: WebSocket 广播 changefeed events

文件: `src/stratum/api/ws.py` + `oprim.changefeed_producer` 接口集成

```python
# 修改 oprim 调用方式: 不只是写 DB, 也广播

# 在每个 changefeed_producer 调用点附近加:
from stratum.api.ws import broadcast_to_user

async def emit_event(user_id: str, event_type: str, payload: dict):
    """统一事件发布: 写 changefeed 表 + WebSocket 广播 (如有在线连接)"""
    # 1. 写 DB
    event_id = generate_ulid()
    insert("changefeed", {
        "event_id": event_id, "user_id": user_id, "device_id": "server",
        "event_type": event_type, "payload": payload, "timestamp": now_utc(),
    })
    
    # 2. 广播到 user 的 WebSocket 连接
    await broadcast_to_user(user_id, {
        "event_id": event_id, "event_type": event_type,
        "payload": payload, "timestamp": now_utc(),
    })
```

替换 routes 中的 `changefeed_producer(...)` → `await emit_event(user_id, event_type, payload)`

### 4.3 Wave 3 Gate

```bash
pytest tests/service_layer/test_sync_scope.py -v
pytest tests/service_layer/test_ws_broadcast.py -v

# WS 真测试: 2 terminal 模拟
# Terminal A: websocat ws://localhost:9304/ws?token=$T
# Terminal B: 触发一个 note create
# Terminal A 应看到 JSON event 推送

git add -A && git commit -m "Phase 15 Wave 3 (P1-C): sync scope 扩展 + WS 广播 changefeed"
```

---

## §5 Wave 4 — 前端 + 文档 + ship (2-3 天)

### 5.1 前端联动 P1 后端

- AgentRunPanel: 显示真 findings (现 mock 显示), 加 run history (调 /api/v1/agents/runs?agent=X)
- Agent run detail page `/agents/runs/[id]` 新建
- Scheduled Jobs Manager: 调 P1-B2 真 CRUD (现 mock)
- /discover 显示真 platform_content (P1-A2 seed 完已自动可看)

### 5.2 STRATUM_API_v1.md + OpenAPI 更新

补 P1 新 endpoint:
- /api/v1/agents/runs/:run_id (B3)
- /api/v1/scheduled-jobs/* CRUD (B2)
- /api/v1/scheduled-jobs/:id/run-now (B2)
- /api/v1/scheduled-jobs/:id/runs (B2)
- /api/v1/sync/changefeed?scope=... (C1)

### 5.3 CHANGELOG 更新

```markdown
## [0.7.0] - 2026-06-XX

### Added (Phase 15 P1)
- AI Agent 真触发: 6 omodul workflow 全注册 (daily_digest/knowledge_curator/translation_worker/reading_companion/weekly_review/lint_bot)
- Agent run history + detail endpoint
- Scheduler CRUD API + builtin_jobs 全部注册 (6 个)
- changefeed event types 扩到 13 种 (substrate/concept/agent/highlight/share/view/profile)
- 同步范围扩展 (notes/substrates/highlights/concepts)
- WebSocket 真广播 changefeed events
- 平台内容 seed (4 篇 Stratum 任务书, build in public)

### Deferred to v1.0+
- access_tier 拦截 (alpha 期免费)
- Agent trace 可视化 (复杂数据)
- 平台内容版本一致性 (highlights 位移)
```

### 5.4 Wave 4 Gate

```bash
# 全套测试
cd ~/projects/stratum && pytest tests/ 2>&1 | tail -5  # 期待 ≥240 pass
cd stratum-web && pnpm test --run 2>&1 | tail -3
pnpm test:e2e 2>&1 | tail -10

# 公网验证 (alpha v0.7 ready)
curl -s https://stratum.kanpan.co/api/v1/health
curl -s https://stratum.kanpan.co/api/v1/content/feed | jq '.items | length'  # ≥4

# tag
git tag phase15-v0.7-alpha
git push --tags

git add -A && git commit -m "Phase 15 Wave 4: 前端联动 + 文档更新 + alpha v0.7 ship"
git push
```

---

## §6 完工标志

```
🎉 alpha v0.7 ship (Phase 15 完工后)

✅ AI Agent 真触发 (6 omodul workflow)
✅ Scheduler CRUD + builtin_jobs 全注册
✅ changefeed 13 events + WS 真广播
✅ 同步范围: notes / substrates / highlights / concepts 全覆盖
✅ /discover 显示 ≥4 篇真内容 (Stratum 任务书 build in public)
✅ Agent run history + detail UI

公网: https://stratum.kanpan.co
版本: v0.7-alpha (phase15-v0.7-alpha tag)
测试: ≥240 pytest + ≥84 vitest + ≥48 e2e

待 Wiki: 决定引流时机 + 100+ 注册开放
```

---

## §7 异常处理

立即停 + 报告:
- omodul Agent 函数签名 / Pydantic 模型跟 SPEC 2 不一致 (R-4 不擅自适配)
- AI Agent 真触发返 error 但 error_message=null (omodul bug, 报告 omodul owner)
- changefeed_producer / WS broadcast 真触发 race condition (修代码不删事件)
- 公网 stratum-sl rebuild 后启动失败

非阻塞继续:
- Agent 触发返 findings=null (alpha corpus 空, 合理)
- /discover seed 内容渲染样式不漂亮 (Phase 14.5 装配后样式 v1.1+ 优化)

---

## §8 时间预算

| Wave | 工作 | 天 |
|---|---|---|
| 1 | P1-A AI Agent + 平台内容 seed | 7 |
| 2 | P1-B Scheduler CRUD + changefeed events | 3-5 |
| 3 | P1-C sync scope + WS broadcast | 2-3 |
| 4 | 前端联动 + 文档 + ship | 2-3 |
| **总** | | **14-18 天 ≈ 2-3 周** |

---

**End Phase 15**

— Stratum 经理人 Claude
2026-06-01
