# PHASE_13_VIEWS_IMPLEMENTATION_INSTRUCTIONS_v0.1.md

**任务**: Stratum Phase 13 — Views (检索视角)
**执行者**: 任一空闲 CC (推荐 Phase 11A 完工后续 CC)
**执行模式**: Claude Code FULL AUTO
**SPEC 依据**:
- SPEC v0.6 PATCH §16 (Views)
- 4O v0.3 PATCH §G

**Phase 13 不依赖**: GPU / 外挂 / 主机准备 → 立即可启动

**预期产物**:
- omodul.knowledge.views (CRUD + applier + preset_loader)
- 5 个预置 view: 通用 / 中文文学 / 量化金融 / 技术阅读 / 工作日志
- hybrid_search 接口加 view_id 参数 (Phase 1.5 已预留, 现真正实施)
- omodul version: 1.6.0 → 1.7.0
- oskill version 视 hybrid_search 改动而定 (大概率 2.7.0 → 2.8.0)

**工程量**: 1-2 周

---

## §0 FULL AUTO 规则

### R-4 严格范围

✅ 允许:
- omodul.knowledge.views.* (新建)
- oskill.knowledge.hybrid_search 修订 (加 view_id 真正实施)
- migration: views 表
- 5 个预置 view yaml + loader
- MCP tools: list_views / set_default_view

❌ 禁止:
- Agent / Scheduler 改动 (Phase 11A 完工)
- 外挂相关 (Phase 11B)
- 用户自定义 view 复杂功能 (v1.0 用户可编辑预置, 但不做拖拽编辑器)
- workspace 隔离 (Stratum 哲学不同, View 是聚合不是隔离)

### R-5 namespace 隔离
- 不动 oprim/* (除 import)
- 不动 oskill/sync / oskill/knowledge 其他 skill (除 hybrid_search)
- 不动 omodul/sync / omodul/knowledge/agents / omodul/knowledge/scheduler / omodul/knowledge/browser_extension

只动:
- omodul/knowledge/views/* (新建)
- oskill/knowledge/hybrid_search.py (修订, view_id 真正生效)
- pyproject.toml (version + deps)
- migration: views 表

---

## §1 工作流程

```
Wave 0: 准入检查
Wave 1: omodul.knowledge.views 实施
Wave 2: hybrid_search view_id 真正生效
Wave 3: 5 预置 view + MCP tools
Wave 4: 端到端 + Gate
```

---

## §2 Wave 1 — omodul.knowledge.views

### 2.1 目录结构

```
platform/omodul/omodul/knowledge/views/
├── __init__.py
├── crud.py              # CRUD 操作
├── applier.py           # 把 view filter 应用到 search 参数
├── preset_loader.py     # 加载 yaml 预置 view
├── presets/             # 5 预置 view yaml
│   ├── default.yaml
│   ├── chinese_literature.yaml
│   ├── quant_finance.yaml
│   ├── tech_reading.yaml
│   └── work_log.yaml
└── tests/
```

### 2.2 数据库 migration

```sql
-- migrations/v1_7_views.sql
CREATE TABLE IF NOT EXISTS views (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    default_filter TEXT,           -- JSON: {"medium": [...], "domain": [...]}
    default_llm TEXT,              -- JSON: {"provider": "...", "model": "..."}
    default_system_prompt TEXT,
    icon TEXT,
    is_default BOOLEAN DEFAULT FALSE,
    is_builtin BOOLEAN DEFAULT FALSE,    -- 预置 vs 用户自建
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE INDEX idx_views_user_default ON views(user_id, is_default DESC);
```

### 2.3 crud.py

```python
# omodul/knowledge/views/crud.py
import uuid, json
from datetime import datetime
from oprim.meta_db import get_db


async def create_view(user_id: str, spec: dict) -> dict:
    db = get_db()
    view_id = str(uuid.uuid4())
    await db.execute(
        """INSERT INTO views
        (id, user_id, name, description, default_filter, default_llm,
         default_system_prompt, icon, is_default, is_builtin,
         created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        view_id, user_id, spec["name"], spec.get("description"),
        json.dumps(spec.get("default_filter", {})),
        json.dumps(spec.get("default_llm", {})),
        spec.get("default_system_prompt"),
        spec.get("icon"),
        spec.get("is_default", False),
        spec.get("is_builtin", False),
        datetime.utcnow(), datetime.utcnow(),
    )
    return await get_view(view_id)


async def get_view(view_id: str) -> dict | None:
    db = get_db()
    row = await db.fetchone("SELECT * FROM views WHERE id = ?", view_id)
    return _row_to_view(row) if row else None


async def list_views(user_id: str) -> list[dict]: ...
async def update_view(view_id: str, updates: dict) -> dict: ...
async def delete_view(view_id: str): ...

async def set_default(user_id: str, view_id: str):
    """切换 default view (单一 default 约束)"""
    db = get_db()
    async with db.transaction():
        await db.execute("UPDATE views SET is_default = FALSE WHERE user_id = ?", user_id)
        await db.execute("UPDATE views SET is_default = TRUE WHERE id = ?", view_id)


async def get_default_view(user_id: str) -> dict | None: ...


def _row_to_view(row) -> dict:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "name": row["name"],
        "description": row["description"],
        "default_filter": json.loads(row["default_filter"]) if row["default_filter"] else {},
        "default_llm": json.loads(row["default_llm"]) if row["default_llm"] else {},
        "default_system_prompt": row["default_system_prompt"],
        "icon": row["icon"],
        "is_default": row["is_default"],
        "is_builtin": row["is_builtin"],
    }
```

### 2.4 applier.py

```python
# omodul/knowledge/views/applier.py
from .crud import get_view


async def apply_view_to_search(
    view_id: str | None,
    search_params: dict,
) -> dict:
    """
    合并 View 默认参数 + 用户传入 params (后者优先).
    """
    if not view_id:
        return search_params
    
    view = await get_view(view_id)
    if not view:
        return search_params
    
    merged = {}
    
    # filter 合并 (view default 跟用户传入合并, 用户优先)
    view_filter = view.get("default_filter", {})
    user_filter = search_params.get("filter", {})
    merged["filter"] = {**view_filter, **user_filter}
    
    # LLM 配置: 用户优先, fallback view
    if "llm_provider" not in search_params and view.get("default_llm", {}).get("provider"):
        merged["llm_provider"] = view["default_llm"]["provider"]
    if "llm_model" not in search_params and view.get("default_llm", {}).get("model"):
        merged["llm_model"] = view["default_llm"]["model"]
    
    # system_prompt: 用户优先
    if "system_prompt" not in search_params and view.get("default_system_prompt"):
        merged["system_prompt"] = view["default_system_prompt"]
    
    # 其他参数透传
    for k, v in search_params.items():
        if k not in merged:
            merged[k] = v
    
    return merged
```

### 2.5 preset_loader.py

```python
# omodul/knowledge/views/preset_loader.py
import yaml
from pathlib import Path
from .crud import create_view, get_view


PRESETS_DIR = Path(__file__).parent / "presets"


async def install_builtin_views(user_id: str):
    """安装 5 个预置 view (幂等)"""
    from .crud import list_views
    existing = await list_views(user_id)
    existing_names = {v["name"] for v in existing}
    
    for preset_file in PRESETS_DIR.glob("*.yaml"):
        spec = yaml.safe_load(preset_file.read_text())
        if spec["name"] in existing_names:
            continue
        spec["user_id"] = user_id
        spec["is_builtin"] = True
        await create_view(user_id, spec)
```

### 2.6 5 预置 view yaml

**presets/default.yaml**:
```yaml
name: "通用"
description: "默认全局检索, 不限 medium / domain"
default_filter: {}
default_llm:
  provider: deepseek
  model: deepseek-chat
icon: "🌐"
is_default: true
```

**presets/chinese_literature.yaml**:
```yaml
name: "中文文学"
description: "适合阅读中文文学作品和文学评论"
default_filter:
  medium: [book, article]
  language: [zh, zh-CN]
default_llm:
  provider: claude
  model: claude-sonnet-4-5
default_system_prompt: "你是文学评论助手, 善于品鉴中文文学."
icon: "📖"
```

**presets/quant_finance.yaml**:
```yaml
name: "量化金融"
description: "量化交易 + 金融研究"
default_filter:
  medium: [paper, article, book]
  domain: [quant, finance, trading]
default_llm:
  provider: deepseek
  model: deepseek-chat
default_system_prompt: "你是量化研究助手, 精通统计 / 金融数学 / 交易策略."
icon: "📊"
```

**presets/tech_reading.yaml**:
```yaml
name: "技术阅读"
description: "技术论文 / 工程文档"
default_filter:
  medium: [paper, article]
  domain: [tech, cs, engineering]
default_llm:
  provider: claude
  model: claude-sonnet-4-5
default_system_prompt: "你是技术阅读助手, 严谨准确."
icon: "💻"
```

**presets/work_log.yaml**:
```yaml
name: "工作日志"
description: "最近 30 天的笔记和思考"
default_filter:
  medium: [note]
  time_range: last_30d
default_llm:
  provider: qwen3
  model: qwen-max
default_system_prompt: "你是个人工作复盘助手."
icon: "📝"
```

---

## §3 Wave 2 — hybrid_search view_id 真正生效

### 3.1 修订 oskill.knowledge.hybrid_search

```python
# oskill/knowledge/hybrid_search.py 修订

async def hybrid_search(
    query: str,
    user_id: str,
    limit: int = 10,
    mode: str = "augmented",
    pinned_boost: float = 1.5,
    return_citations: bool = True,
    view_id: str | None = None,           # Phase 1.5 已加, Phase 13 真正生效
    filter: dict | None = None,
    ...
) -> list[SearchResult]:
    # NEW: 如果 view_id 传了, 用 applier 合并
    if view_id:
        from omodul.knowledge.views import apply_view_to_search
        merged_params = await apply_view_to_search(view_id, {
            "filter": filter or {},
            "llm_provider": kwargs.get("llm_provider"),
            "llm_model": kwargs.get("llm_model"),
        })
        filter = merged_params.get("filter", filter)
        # ... 其他参数应用
    
    # 既有逻辑
    ...
```

注意: oskill 调 omodul, 反向依赖。如果 R-3 完整调用链原则不允许, 可以反过来让 omodul.views 暴露纯函数被 oskill 调用 (apply_view_to_search 不需要 DB, 只要 view dict + search params)。

**实施时 CC 自己判断方向**, 优先保持依赖方向 oskill ← omodul (omodul 在上层). 可能需要把 apply_view_to_search 重构为接收 view dict 而不是 view_id, view 加载放 omodul 调 hybrid_search 之前.

---

## §4 Wave 3 — MCP tools + 端到端

### 4.1 新 MCP tools (在 start_mcp_server 加)

```python
@mcp_tool(name="stratum.list_views")
async def list_views_tool() -> dict:
    from omodul.knowledge.views import list_views
    user_id = get_current_user_id()
    views = await list_views(user_id)
    return {"views": views}


@mcp_tool(name="stratum.set_default_view")
async def set_default_view_tool(view_id: str) -> dict:
    from omodul.knowledge.views import set_default
    user_id = get_current_user_id()
    await set_default(user_id, view_id)
    return {"success": True, "view_id": view_id}
```

### 4.2 端到端 demo

```bash
# 1. 安装预置 view
python -c "
import asyncio
from omodul.knowledge.views import install_builtin_views
asyncio.run(install_builtin_views('demo_user'))
"

# 2. 列出 view
python -c "
import asyncio
from omodul.knowledge.views import list_views
views = asyncio.run(list_views('demo_user'))
for v in views:
    print(f'{v[\"icon\"]} {v[\"name\"]}: {v[\"description\"]}')
"

# 期待输出 5 个 view, default 有 ✓ 标记

# 3. search 应用 view filter
python -c "
import asyncio
from oskill.knowledge.hybrid_search import hybrid_search
from omodul.knowledge.views import list_views

views = asyncio.run(list_views('demo_user'))
quant_view = next(v for v in views if v['name'] == '量化金融')

# 用量化金融 view 搜索 — 期待 filter 自动应用
results = asyncio.run(hybrid_search(
    query='夏普比率', user_id='demo_user',
    view_id=quant_view['id'], limit=5,
))
print(f'Results: {len(results)}')
# 期待 results 都满足 medium in [paper, article, book] AND domain in [quant, finance, trading]
"

# 4. 切换 default view
python -c "
import asyncio
from omodul.knowledge.views import set_default
asyncio.run(set_default('demo_user', '<quant_view_id>'))

# 验证: 不传 view_id 的 search 自动应用量化金融 view filter
"
```

---

## §5 Wave 4 — Gate 验收

### 5.1 验收矩阵

| 项 | 标准 |
|---|---|
| 5 个预置 view 加载 | install_builtin_views 幂等 |
| CRUD | create / get / list / update / delete / set_default |
| 单一 default 约束 | set_default 自动 unset 其他 |
| applier 合并逻辑 | 用户传入 > view default |
| hybrid_search view_id 生效 | filter 正确应用 |
| MCP tools | list_views / set_default_view |
| 端到端 demo 跑通 | 6 步真实数据 |
| 单元测试 ≥ 80% | omodul.knowledge.views |
| 全量回归 0 regressions | |
| version bump | omodul 1.6.0 → 1.7.0, oskill 视情况 |
| tag | v1.7.0-views (oskill 视情况) |

### 5.2 完工报告格式

(参考之前 Phase 完工报告)

---

## §6 异常处理

立即停止 + 报告:
- baseline 状态异常
- view 跟 hybrid_search 集成 R-3 调用链方向矛盾
- 单一 default 约束在并发场景失效

非阻塞:
- yaml 解析个别字段不一致 (例如 medium / domain 命名)

---

**预估**: 1-2 周 FULL AUTO

Wave 0: 0.5 天
Wave 1: 3-4 天 (views CRUD + applier + preset)
Wave 2: 1-2 天 (hybrid_search 集成)
Wave 3: 1-2 天 (MCP tools + 端到端)
Wave 4: 0.5 天 (Gate)

---

**End**
