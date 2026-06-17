# 后端 Layer 4 恢复指令书 — Views/Highlights + DB 初始化

**To**: 后端 CC
**From**: Stratum advisor
**日期**: 2026-06-12
**模式**: FULL AUTO（无中途提问，自决推进，失败停，完工逐字报告）
**前置**: oprim v2.37.0 / oskill v3.16.0 / omodul v1.22.1 / obase v0.11.0 / oservice v0.4.3 已 ship；_HAS_INBOX True

---

## §0 范围（§20 严守）

✅ 允许（全 Layer 4，Stratum repo 内）:
- migration 023（捡回 main）+ 024（新建）
- views.py / highlights.py 重写
- /documents endpoint 接 view_id
- main.py 注册 router + migration 启动钩子
- 后端测试

❌ 禁止:
- 改 3O 主库（oskill/oprim/omodul/obase/oservice）
- 改 Dockerfile --no-deps 策略（恢复稳定后单独处理）

---

## §1 数据库初始化（最优先 — 当前 0 表）

### 1.1 问题

容器启动不自动跑 migration，DuckDB 白纸。先让 migration 能跑。

### 1.2 核查 migration runner

```bash
# 找现有 runner:
find ~/projects/stratum/src/stratum -name "run_migrations*.py" -o -name "*migrat*.py" | head
cat ~/projects/stratum/src/stratum/db/run_migrations.py 2>/dev/null | head -50
```

### 1.3 main.py 加启动钩子（lifespan）

```python
# src/stratum/api/main.py lifespan
from stratum.db.run_migrations import run_migrations

@asynccontextmanager
async def lifespan(app):
    run_migrations()  # 启动时自动建表（idempotent，CREATE TABLE IF NOT EXISTS）
    # ... 现有 _feed_tracker_loop 等
    yield
```

如果 run_migrations 不存在或不 idempotent → 先修 runner（读 migrations/ 目录所有 .sql 顺序执行，记录 schema_migrations 表防重跑）。

---

## §2 Migration 023 — Views（捡回 main 适配）

### 2.1 处理 user_saved_views vs user_views 冲突

020 有旧 `user_views`，023 引入 `user_saved_views`（更丰富）。决策：

```
023 用 user_saved_views（Phase 17.12 权威），旧 user_views 弃用。
- 如果 020 的 user_views 没被任何代码引用 → 023 只建 user_saved_views，user_views 留着不管（idempotent）
- 后端 views.py 全部用 user_saved_views
```

### 2.2 migration 023 文件（捡回 + 适配当前 DuckDB）

```sql
-- src/stratum/db/migrations/023_views_table.sql
CREATE TABLE IF NOT EXISTS user_saved_views (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    description VARCHAR,
    is_preset BOOLEAN DEFAULT FALSE,
    icon VARCHAR,
    filter_json JSON DEFAULT '{}',
    sort_by VARCHAR DEFAULT 'created_at',
    sort_order VARCHAR DEFAULT 'desc',
    display_mode VARCHAR DEFAULT 'list',
    position INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_saved_views_user ON user_saved_views(user_id);
CREATE INDEX IF NOT EXISTS idx_saved_views_pos ON user_saved_views(user_id, position);
```

注意 DuckDB：UNIQUE(user_id, name) 约束 DuckDB 支持，但如果 runner 报错可改为应用层去重。

---

## §3 Migration 024 — Highlights（新建，逆向 Phase 15 升级）

### 3.1 核查 Phase 15 highlights 旧表

```bash
grep -rn "CREATE TABLE.*highlight\|highlights" ~/projects/stratum/src/stratum/db/migrations/0*.sql
cat ~/projects/stratum/src/stratum/api/routers/highlights.py  # 78 行旧版，看它查什么表/列
```

### 3.2 migration 024 文件

```sql
-- src/stratum/db/migrations/024_highlights_table.sql
CREATE TABLE IF NOT EXISTS highlights (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    substrate_id VARCHAR NOT NULL,
    color VARCHAR DEFAULT 'yellow',
    text VARCHAR NOT NULL,           -- 高亮原文
    note VARCHAR,                    -- 用户笔记
    location_json JSON DEFAULT '{}', -- 位置信息（页码/偏移）
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_highlights_user ON highlights(user_id);
CREATE INDEX IF NOT EXISTS idx_highlights_substrate ON highlights(substrate_id);
```

如果 Phase 15 旧 highlights 表已在 020 建过且列不同 → 024 用 ALTER 补列，或确认旧表无数据直接 DROP + 重建。CC 核查后决定，R-1 报告冲突。

---

## §4 views.py 重写（覆盖 111 行旧版）

### 4.1 完整实现（参照 PHASE_17_12_CC_v1.0.md §3）

```python
# src/stratum/api/routers/views.py
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from stratum.utils.user_id_hash import hash_user_id
from stratum.utils.ulid import generate_ulid  # 或现有 ULID util
from stratum.db import get_conn
from stratum.api.deps import get_current_user

router = APIRouter(prefix="/api/v1/views", tags=["views"])

DEFAULT_PRESETS = [
    {"name": "通用", "description": "默认全局检索", "icon": "📚",
     "filter_json": {}, "sort_by": "updated_at", "sort_order": "desc", "position": 0},
    {"name": "量化金融", "description": "金融论文+量化资料", "icon": "📈",
     "filter_json": {"medium": ["paper", "book", "epub"], "tags": ["finance", "quant", "trading", "investment"]},
     "sort_by": "created_at", "sort_order": "desc", "position": 1},
    {"name": "技术阅读", "description": "技术论文+文档", "icon": "💻",
     "filter_json": {"medium": ["paper", "webpage"], "tags": ["tech", "programming", "engineering", "ai"]},
     "sort_by": "created_at", "sort_order": "desc", "position": 2},
    {"name": "中文文学", "description": "中文书籍+散文", "icon": "📖",
     "filter_json": {"medium": ["book", "epub"], "language": ["zh", "zh-CN"]},
     "sort_by": "created_at", "sort_order": "desc", "position": 3},
    {"name": "归档", "description": "归档/不活跃内容", "icon": "📦",
     "filter_json": {"tags": ["archived"]}, "sort_by": "updated_at", "sort_order": "asc", "position": 4},
]

class ViewCreate(BaseModel):
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    filter_json: Dict[str, Any] = {}
    sort_by: str = "created_at"
    sort_order: str = "desc"
    display_mode: str = "list"
    position: int = 0

class ViewUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    filter_json: Optional[Dict[str, Any]] = None
    sort_by: Optional[str] = None
    sort_order: Optional[str] = None
    display_mode: Optional[str] = None
    position: Optional[int] = None

def _row_to_view(r) -> dict:
    # 按 SELECT 列顺序映射，filter_json 解析为 dict
    return {
        "id": r[0], "user_id": r[1], "name": r[2], "description": r[3],
        "is_preset": r[4], "icon": r[5], "filter_json": json.loads(r[6]) if r[6] else {},
        "sort_by": r[7], "sort_order": r[8], "display_mode": r[9], "position": r[10],
        "created_at": str(r[11]), "updated_at": str(r[12]),
    }

def _ensure_presets(user_hash: str):
    with get_conn() as conn:
        n = conn.execute("SELECT COUNT(*) FROM user_saved_views WHERE user_id=? AND is_preset=TRUE", (user_hash,)).fetchone()[0]
        if n > 0:
            return
        for p in DEFAULT_PRESETS:
            conn.execute("""
                INSERT INTO user_saved_views (id, user_id, name, description, icon, is_preset,
                    filter_json, sort_by, sort_order, display_mode, position)
                VALUES (?,?,?,?,?,TRUE,?,?,?,'list',?)
            """, (generate_ulid(), user_hash, p["name"], p["description"], p["icon"],
                  json.dumps(p["filter_json"]), p["sort_by"], p["sort_order"], p["position"]))

_COLS = "id, user_id, name, description, is_preset, icon, filter_json, sort_by, sort_order, display_mode, position, created_at, updated_at"

@router.get("")
async def list_views(user=Depends(get_current_user)):
    uh = hash_user_id(user.user_id)
    _ensure_presets(uh)
    with get_conn() as conn:
        rows = conn.execute(f"SELECT {_COLS} FROM user_saved_views WHERE user_id=? ORDER BY position, created_at", (uh,)).fetchall()
    return [_row_to_view(r) for r in rows]

@router.post("", status_code=201)
async def create_view(body: ViewCreate, user=Depends(get_current_user)):
    uh = hash_user_id(user.user_id)
    vid = generate_ulid()
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO user_saved_views (id, user_id, name, description, icon, is_preset,
                filter_json, sort_by, sort_order, display_mode, position)
            VALUES (?,?,?,?,?,FALSE,?,?,?,?,?)
        """, (vid, uh, body.name, body.description, body.icon, json.dumps(body.filter_json),
              body.sort_by, body.sort_order, body.display_mode, body.position))
        r = conn.execute(f"SELECT {_COLS} FROM user_saved_views WHERE id=?", (vid,)).fetchone()
    return _row_to_view(r)

@router.put("/{view_id}")
async def update_view(view_id: str, body: ViewUpdate, user=Depends(get_current_user)):
    uh = hash_user_id(user.user_id)
    with get_conn() as conn:
        v = conn.execute("SELECT is_preset, user_id FROM user_saved_views WHERE id=?", (view_id,)).fetchone()
        if not v or v[1] != uh:
            raise HTTPException(404, "View not found")
        if v[0]:
            raise HTTPException(403, "Cannot modify preset views")
        updates = {k: val for k, val in body.dict().items() if val is not None}
        if "filter_json" in updates:
            updates["filter_json"] = json.dumps(updates["filter_json"])
        if updates:
            set_clause = ", ".join(f"{k}=?" for k in updates) + ", updated_at=NOW()"
            conn.execute(f"UPDATE user_saved_views SET {set_clause} WHERE id=?", (*updates.values(), view_id))
        r = conn.execute(f"SELECT {_COLS} FROM user_saved_views WHERE id=?", (view_id,)).fetchone()
    return _row_to_view(r)

@router.delete("/{view_id}", status_code=204)
async def delete_view(view_id: str, user=Depends(get_current_user)):
    uh = hash_user_id(user.user_id)
    with get_conn() as conn:
        v = conn.execute("SELECT is_preset, user_id FROM user_saved_views WHERE id=?", (view_id,)).fetchone()
        if not v or v[1] != uh:
            raise HTTPException(404, "View not found")
        if v[0]:
            raise HTTPException(403, "Cannot delete preset views")
        conn.execute("DELETE FROM user_saved_views WHERE id=?", (view_id,))
```

---

## §5 /documents endpoint 接 view_id

```python
# src/stratum/api/routers/substrates.py (或 documents 对应 router)

@router.get("/api/v1/documents")  # 或现有路径
async def list_documents(
    view_id: Optional[str] = None,
    medium: Optional[List[str]] = Query(None),
    tags: Optional[List[str]] = Query(None),
    tag_exclude: Optional[List[str]] = Query(None),
    sort_by: str = "created_at",
    sort_order: str = "desc",
    limit: int = 50, offset: int = 0,
    user=Depends(get_current_user),
):
    uh = hash_user_id(user.user_id)
    # view_id 传入 → load view filter 覆盖
    if view_id:
        with get_conn() as conn:
            v = conn.execute("SELECT filter_json, sort_by, sort_order FROM user_saved_views WHERE id=? AND user_id=?", (view_id, uh)).fetchone()
            if v:
                vf = json.loads(v[0]) if v[0] else {}
                medium = vf.get("medium") or medium
                tags = vf.get("tags") or tags
                tag_exclude = vf.get("tag_exclude") or tag_exclude
                sort_by = v[1] or sort_by
                sort_order = v[2] or sort_order
    # build SQL with filter (现有 list 逻辑扩展)
    # medium 用 json_extract_string(meta_json,'$.medium') 或 substrates.medium 列（按当前 schema）
    # tag filter JOIN substrate_tags
    # ...
```

注意：substrates 的 medium 来源（meta_json vs 独立列）按 §6 核查结果对齐。

---

## §6 highlights.py 重写（覆盖 78 行旧版）

```python
# src/stratum/api/routers/highlights.py
from fastapi import APIRouter, Depends, HTTPException
from stratum.utils.user_id_hash import hash_user_id
from stratum.db import get_conn
from stratum.api.deps import get_current_user

router = APIRouter(prefix="/api/v1/highlights", tags=["highlights"])

@router.get("")
async def list_highlights(user=Depends(get_current_user)):
    uh = hash_user_id(user.user_id)
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT h.id, h.color, h.text, h.note, h.substrate_id, s.title, h.created_at
            FROM highlights h
            LEFT JOIN substrates s ON h.substrate_id = s.id
            WHERE h.user_id = ?
            ORDER BY h.created_at DESC
        """, (uh,)).fetchall()
    return [{"id": r[0], "color": r[1], "text": r[2], "note": r[3],
             "substrate_id": r[4], "substrate_title": r[5], "created_at": str(r[6])} for r in rows]

@router.delete("/{highlight_id}", status_code=204)
async def delete_highlight(highlight_id: str, user=Depends(get_current_user)):
    uh = hash_user_id(user.user_id)
    with get_conn() as conn:
        h = conn.execute("SELECT user_id FROM highlights WHERE id=?", (highlight_id,)).fetchone()
        if not h or h[0] != uh:
            raise HTTPException(404, "Highlight not found")
        conn.execute("DELETE FROM highlights WHERE id=?", (highlight_id,))
```

---

## §7 注册 router

```python
# src/stratum/api/main.py
from stratum.api.routers import views as views_router, highlights as highlights_router
app.include_router(views_router.router)
app.include_router(highlights_router.router)
```

---

## §8 测试

```python
# tests/http_api/test_views_routes.py + test_highlights_routes.py
# 真 DuckDB fixture（SPEC v1.2 陷阱 16），含 023/024 DDL
# 测: list seed 5 预设 / create / update / delete / 预设403 / view filter apply
# highlights: list / delete / 404
```

---

## §9 重跑 migration + 验证

```bash
docker compose restart stratum-sl stratum-api
sleep 10

# 验证表建立:
docker exec stratum-sl python3 -c "
from stratum.db import get_conn
with get_conn() as conn:
    t = conn.execute(\"SELECT table_name FROM information_schema.tables WHERE table_schema='main'\").fetchall()
    print(sorted([x[0] for x in t]))
"
# 期待含 substrates, user_saved_views, highlights, ...

# 端到端（R-3 完整往返）:
TOKEN=<注册测试账号取 token>
# 1. 上传 PDF → substrate_id
# 2. /documents → 列表显示真文件名（不是 ULID）
# 3. /api/v1/views → 5 预设
# 4. /documents?view={量化金融 id} → filter 生效
# 5. derivative.content 非 NULL（主库已修，应自动）

git add -A
git commit -m "Layer 4 恢复: migration 023/024 + views/highlights 重写 + DB 自动 migration + 端到端验证"
git push
```

---

## §10 R-1 / R-3 / §20

- R-1: 任何 migration 冲突 / import fail / 端到端 fail → 停报告
- R-3: 端到端往返（上传→查→返同一条），不接受 build pass + curl 200
- §20: 不改主库

---

**完工逐字报告**:
- §1 DB 自动 migration 钩子
- §2/§3 migration 023/024 建表确认
- §4/§6 views.py / highlights.py 重写行数
- §5 /documents view_id 接入
- §8 测试数
- §9 端到端 5 步结果 + 表清单
- commit hash

---

**End**

— Stratum advisor
2026-06-12
