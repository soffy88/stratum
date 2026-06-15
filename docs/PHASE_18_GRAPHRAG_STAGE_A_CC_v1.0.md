# PHASE 18 — GraphRAG Stage A 实施指令书

**To**: CC (FULL AUTO)
**From**: Stratum advisor
**日期**: 2026-06-15
**模式**: FULL AUTO，失败停，完工逐字报告
**前置确认**:
- oprim v3.10.3: entity_graph_search / graph_traversal / embed_text / structural_chunk / open_vector_db ✅
- oskill v3.17.0: hybrid_retrieve / hybrid_search ✅
- oservi v1.1.0: 容器内就绪 ✅
- DuckDB: graph_entities / graph_relations 表不存在（待建）

---

## §0 范围（§20 严守）

✅ 允许（全 Layer 4，Stratum repo 内）:
- migration 029/030（graph_entities / graph_relations 表）
- src/stratum/services/graph_builder_service.py（新建）
- src/stratum/dao/graph.py（新建）
- src/stratum/api/routers/graph.py（新建，GraphRAG 查询 endpoint）
- inbox.py 加 graph 构建钩子（入库后触发）
- 测试（真 DuckDB fixture）

❌ 禁止:
- 改 oprim / oskill / oservi / omodul / obase 主库
- 改现有 hybrid_search 链路（只是在旁边加 graph 路径，不替换）

---

## §1 DB Schema（migration 029 + 030）

### migration 029 — graph_entities

```sql
-- src/stratum/db/migrations/029_graph_entities.sql
CREATE TABLE IF NOT EXISTS graph_entities (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    entity_type VARCHAR DEFAULT 'concept',
    description VARCHAR,
    aliases JSON DEFAULT '[]',
    source_substrate_ids JSON DEFAULT '[]',
    mention_count INTEGER DEFAULT 1,
    embedding_id VARCHAR,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_graph_entities_user ON graph_entities(user_id);
CREATE INDEX IF NOT EXISTS idx_graph_entities_name ON graph_entities(user_id, name);
```

### migration 030 — graph_relations

```sql
-- src/stratum/db/migrations/030_graph_relations.sql
CREATE TABLE IF NOT EXISTS graph_relations (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    source_entity_id VARCHAR NOT NULL,
    target_entity_id VARCHAR NOT NULL,
    relation_type VARCHAR DEFAULT 'related',
    description VARCHAR,
    weight FLOAT DEFAULT 1.0,
    source_substrate_ids JSON DEFAULT '[]',
    confidence FLOAT DEFAULT 0.5,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_graph_relations_user ON graph_relations(user_id);
CREATE INDEX IF NOT EXISTS idx_graph_relations_source ON graph_relations(user_id, source_entity_id);
CREATE INDEX IF NOT EXISTS idx_graph_relations_target ON graph_relations(user_id, target_entity_id);
```

---

## §2 Graph DAO（Layer 4）

```python
# src/stratum/dao/graph.py
import json
from stratum.db import get_conn
from stratum.utils.ulid import generate_ulid


def upsert_entity(user_id: str, name: str, entity_type: str,
                  description: str | None, substrate_id: str) -> str:
    """Insert or merge entity. Returns entity id."""
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id, mention_count, source_substrate_ids FROM graph_entities "
            "WHERE user_id=? AND name=?",
            (user_id, name)
        ).fetchone()
        if existing:
            eid, count, sids = existing
            sids_list = json.loads(sids) if sids else []
            if substrate_id not in sids_list:
                sids_list.append(substrate_id)
            conn.execute(
                "UPDATE graph_entities SET mention_count=?, source_substrate_ids=?, "
                "updated_at=NOW() WHERE id=?",
                (count + 1, json.dumps(sids_list), eid)
            )
            return eid
        else:
            eid = generate_ulid()
            conn.execute(
                "INSERT INTO graph_entities "
                "(id, user_id, name, entity_type, description, source_substrate_ids) "
                "VALUES (?,?,?,?,?,?)",
                (eid, user_id, name, entity_type, description,
                 json.dumps([substrate_id]))
            )
            return eid


def upsert_relation(user_id: str, source_id: str, target_id: str,
                    relation_type: str, description: str | None,
                    substrate_id: str, confidence: float = 0.5) -> str:
    """Insert or merge relation."""
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id, source_substrate_ids FROM graph_relations "
            "WHERE user_id=? AND source_entity_id=? AND target_entity_id=? AND relation_type=?",
            (user_id, source_id, target_id, relation_type)
        ).fetchone()
        if existing:
            rid, sids = existing
            sids_list = json.loads(sids) if sids else []
            if substrate_id not in sids_list:
                sids_list.append(substrate_id)
            conn.execute(
                "UPDATE graph_relations SET source_substrate_ids=? WHERE id=?",
                (json.dumps(sids_list), rid)
            )
            return rid
        else:
            rid = generate_ulid()
            conn.execute(
                "INSERT INTO graph_relations "
                "(id, user_id, source_entity_id, target_entity_id, relation_type, "
                "description, source_substrate_ids, confidence) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (rid, user_id, source_id, target_id, relation_type,
                 description, json.dumps([substrate_id]), confidence)
            )
            return rid


def get_entity_neighbors(user_id: str, entity_ids: list[str]) -> list[dict]:
    """Return adjacency list for graph_traversal injection."""
    if not entity_ids:
        return []
    placeholders = ",".join("?" * len(entity_ids))
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT source_entity_id, target_entity_id, relation_type, weight "
            f"FROM graph_relations "
            f"WHERE user_id=? AND source_entity_id IN ({placeholders})",
            (user_id, *entity_ids)
        ).fetchall()
    return [{"source": r[0], "target": r[1], "type": r[2], "weight": r[3]}
            for r in rows]


def query_entities_by_ids(user_id: str, entity_ids: list[str]) -> list[dict]:
    """Fetch entity details by ids."""
    if not entity_ids:
        return []
    placeholders = ",".join("?" * len(entity_ids))
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT id, name, entity_type, description, source_substrate_ids "
            f"FROM graph_entities WHERE user_id=? AND id IN ({placeholders})",
            (user_id, *entity_ids)
        ).fetchall()
    return [{"id": r[0], "name": r[1], "type": r[2],
             "description": r[3], "substrate_ids": json.loads(r[4] or "[]")}
            for r in rows]
```

---

## §3 Graph Builder Service（Layer 4）

```python
# src/stratum/services/graph_builder_service.py
"""
GraphRAG Stage A: 入库后从 derivative.content 抽实体+关系写入 graph_entities/graph_relations.

调用链（全 3O 主库元素，不动主库）:
  derivative.content (markdown)
  → oprim.structural_chunk → chunks
  → oprim.llm_call (抽实体+关系 JSON)
  → dao.graph.upsert_entity / upsert_relation
"""
import json
import logging
from stratum.db import get_conn
from stratum.dao.graph import upsert_entity, upsert_relation
from stratum.utils.user_id_hash import hash_user_id

log = logging.getLogger(__name__)

_EXTRACT_PROMPT = """从以下文本中抽取实体和关系。

要求:
- entities: 列出重要概念/方法/人物/系统，每个含 name(中英文均可), type(concept/method/person/system), description(一句话)
- relations: 列出实体间关系，每个含 source, target, relation_type(affects/defines/part_of/supports/contradicts/uses), description

返回严格 JSON，不加任何说明:
{
  "entities": [{"name": "...", "type": "...", "description": "..."}],
  "relations": [{"source": "...", "target": "...", "relation_type": "...", "description": "..."}]
}

文本:
"""

_MAX_CHUNK_CHARS = 2000
_MAX_ENTITIES_PER_SUBSTRATE = 30


async def build_graph_from_substrate(substrate_id: str, user_id_hash: str) -> dict:
    """
    Main entry: read derivative.content, chunk, extract entities+relations via LLM,
    write to graph tables.
    Returns {"entities_added": N, "relations_added": M}
    """
    from oprim import structural_chunk, llm_call

    # 1. 读 markdown derivative
    with get_conn() as conn:
        row = conn.execute(
            "SELECT content FROM derivative WHERE substrate_id=? AND kind='markdown'",
            (substrate_id,)
        ).fetchone()

    if not row or not row[0]:
        log.warning("graph_builder: no markdown derivative for %s", substrate_id)
        return {"entities_added": 0, "relations_added": 0}

    content = row[0]

    # 2. chunk（oprim.structural_chunk）
    chunks = structural_chunk(
        text=content,
        min_chars=500,
        max_chars=_MAX_CHUNK_CHARS,
    )
    if not chunks:
        chunks = [content[:_MAX_CHUNK_CHARS]]

    entities_added = 0
    relations_added = 0
    seen_entities: dict[str, str] = {}  # name → entity_id

    # 3. 每 chunk LLM 抽取
    for chunk in chunks[:5]:  # 最多 5 chunk，控制成本
        try:
            resp = await llm_call(
                messages=[{"role": "user", "content": _EXTRACT_PROMPT + chunk}],
                max_tokens=1000,
            )
            text = resp.get("content", [{}])[0].get("text", "")
            # 清理 markdown code block
            text = text.strip().strip("```json").strip("```").strip()
            data = json.loads(text)
        except Exception as e:
            log.warning("graph_builder: LLM extract failed for chunk: %s", e)
            continue

        # 4. upsert entities
        for ent in data.get("entities", [])[:_MAX_ENTITIES_PER_SUBSTRATE]:
            name = ent.get("name", "").strip()
            if not name:
                continue
            eid = upsert_entity(
                user_id=user_id_hash,
                name=name,
                entity_type=ent.get("type", "concept"),
                description=ent.get("description"),
                substrate_id=substrate_id,
            )
            seen_entities[name] = eid
            entities_added += 1

        # 5. upsert relations
        for rel in data.get("relations", []):
            src_name = rel.get("source", "").strip()
            tgt_name = rel.get("target", "").strip()
            if src_name not in seen_entities or tgt_name not in seen_entities:
                continue
            upsert_relation(
                user_id=user_id_hash,
                source_id=seen_entities[src_name],
                target_id=seen_entities[tgt_name],
                relation_type=rel.get("relation_type", "related"),
                description=rel.get("description"),
                substrate_id=substrate_id,
                confidence=0.7,
            )
            relations_added += 1

    log.info("graph_builder: substrate=%s entities=%d relations=%d",
             substrate_id, entities_added, relations_added)
    return {"entities_added": entities_added, "relations_added": relations_added}
```

---

## §4 inbox.py 加图构建钩子

```python
# src/stratum/api/routers/inbox.py
# 在 _fill_derivative_content() 调用之后加（不阻塞主流程，background task）:

from stratum.services.graph_builder_service import build_graph_from_substrate

# inbox_submit handler 末尾，response 返回前:
background_tasks.add_task(
    build_graph_from_substrate,
    substrate_id=substrate_id,
    user_id_hash=user_id_hash,
)
# 同样在 web_clip handler 末尾加
```

---

## §5 GraphRAG 查询 Endpoint

```python
# src/stratum/api/routers/graph.py
from fastapi import APIRouter, Depends, Query
from typing import Optional
from stratum.utils.user_id_hash import hash_user_id
from stratum.dao.graph import get_entity_neighbors, query_entities_by_ids
from stratum.api.deps import get_current_user
from stratum.db import get_conn

router = APIRouter(prefix="/api/v1/graph", tags=["graph"])


@router.get("/entities")
async def list_entities(
    q: Optional[str] = None,
    limit: int = 50,
    user=Depends(get_current_user),
):
    """List user's graph entities, optionally filter by name."""
    uh = hash_user_id(user.user_id)
    with get_conn() as conn:
        if q:
            rows = conn.execute(
                "SELECT id, name, entity_type, description, mention_count "
                "FROM graph_entities WHERE user_id=? AND name ILIKE ? "
                "ORDER BY mention_count DESC LIMIT ?",
                (uh, f"%{q}%", limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, name, entity_type, description, mention_count "
                "FROM graph_entities WHERE user_id=? "
                "ORDER BY mention_count DESC LIMIT ?",
                (uh, limit)
            ).fetchall()
    return [{"id": r[0], "name": r[1], "type": r[2],
             "description": r[3], "mention_count": r[4]} for r in rows]


@router.get("/subgraph/{entity_id}")
async def get_subgraph(
    entity_id: str,
    max_hops: int = Query(default=2, le=3),
    user=Depends(get_current_user),
):
    """BFS from entity_id, return subgraph (nodes + edges)."""
    from oprim import graph_traversal
    uh = hash_user_id(user.user_id)

    def get_neighbors(node_id: str) -> list[str]:
        neighbors = get_entity_neighbors(uh, [node_id])
        return [n["target"] for n in neighbors]

    visited = graph_traversal(
        start_nodes=[entity_id],
        get_neighbors=get_neighbors,
        mode="bfs",
        max_depth=max_hops,
        max_nodes=100,
    )

    node_ids = list(visited.keys()) if isinstance(visited, dict) else list(visited)
    nodes = query_entities_by_ids(uh, node_ids)
    edges = get_entity_neighbors(uh, node_ids)

    return {"nodes": nodes, "edges": edges, "seed": entity_id}


@router.post("/query")
async def graphrag_query(
    body: dict,
    user=Depends(get_current_user),
):
    """
    GraphRAG 查询: question → entity link → graph traverse → hybrid retrieve → LLM answer.
    """
    from oprim import entity_graph_search, llm_call
    from oskill import hybrid_retrieve
    import json

    question = body.get("question", "")
    max_hops = body.get("max_hops", 2)
    top_k = body.get("top_k", 5)
    uh = hash_user_id(user.user_id)

    # 1. 从 graph_entities 找 seed（名称模糊匹配）
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name FROM graph_entities WHERE user_id=? "
            "ORDER BY mention_count DESC LIMIT 20",
            (uh,)
        ).fetchall()

    all_entity_ids = [r[0] for r in rows]
    all_entity_names = {r[0]: r[1] for r in rows}

    if not all_entity_ids:
        return {"answer": "知识图谱为空，请先上传文档。", "sources": []}

    # 2. entity_graph_search（oprim BFS）
    def list_edges(node_id: str) -> list[tuple]:
        neighbors = get_entity_neighbors(uh, [node_id])
        return [(n["source"], n["target"], n["weight"]) for n in neighbors]

    ranked = entity_graph_search(
        seed_ids=all_entity_ids[:5],
        list_edges=list_edges,
        hops=max_hops,
        top_k=top_k * 2,
    )
    top_entity_ids = [r[0] for r in ranked] if ranked else all_entity_ids[:top_k]

    # 3. 取相关 substrate_ids
    entities = query_entities_by_ids(uh, top_entity_ids)
    substrate_ids = list({
        sid
        for ent in entities
        for sid in ent.get("substrate_ids", [])
    })[:top_k]

    # 4. 取 substrate 内容作为 context
    context_parts = []
    with get_conn() as conn:
        for sid in substrate_ids:
            row = conn.execute(
                "SELECT s.title, d.content FROM substrates s "
                "LEFT JOIN derivative d ON s.id=d.substrate_id AND d.kind='markdown' "
                "WHERE s.id=? AND s.user_id=?",
                (sid, uh)
            ).fetchone()
            if row and row[1]:
                context_parts.append(f"【{row[0]}】\n{row[1][:1000]}")

    if not context_parts:
        return {"answer": "未找到相关文档内容。", "sources": substrate_ids}

    context = "\n\n---\n\n".join(context_parts)

    # 5. LLM 综合
    prompt = f"""根据以下知识库内容回答问题。

问题: {question}

相关内容:
{context}

请基于内容给出准确、简洁的回答。如果内容不足以回答，请说明。"""

    resp = await llm_call(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000,
    )
    answer = resp.get("content", [{}])[0].get("text", "")

    return {
        "answer": answer,
        "sources": substrate_ids,
        "entities_used": [all_entity_names.get(eid, eid) for eid in top_entity_ids],
    }
```

注册到 main.py:
```python
from stratum.api.routers import graph as graph_router
app.include_router(graph_router.router)
```

---

## §6 测试

```python
# tests/http_api/test_graph_routes.py
# 真 DuckDB fixture 含 029/030 DDL
# 测: list_entities(空) / subgraph(seed) / graphrag_query
# graph_builder_service 单元测试: mock llm_call 返固定 JSON，验 upsert 调用
```

---

## §7 端到端验证

```bash
# 1. 重启容器（新 migration 自动跑）:
docker compose restart stratum-sl stratum-api
sleep 10

# 2. 验证表建立:
docker exec stratum-sl python3 -c "
from stratum.db import get_conn
with get_conn() as conn:
    for t in ['graph_entities','graph_relations']:
        c = conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
        print(t, c)
"

# 3. 上传一个 PDF（触发图构建 background task）:
TOKEN=<token>
curl -s -X POST https://stratum.uex.hk/api/v1/inbox/submit \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@<PDF>" | jq '{status, substrate_id}'

# 等 5-10 秒（background task）

# 4. 查 graph_entities:
docker exec stratum-sl python3 -c "
from stratum.db import get_conn
with get_conn() as conn:
    rows = conn.execute('SELECT name, entity_type, mention_count FROM graph_entities LIMIT 10').fetchall()
    for r in rows: print(r)
"
# 期待: 真实体出现（非空）

# 5. GraphRAG 查询:
curl -s -X POST https://stratum.uex.hk/api/v1/graph/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "这篇文档的核心方法是什么", "max_hops": 2}' | jq '{answer, entities_used}'
# 期待: 真实 LLM 答案 + 实体列表

# 6. 子图:
ENTITY_ID=$(curl -s https://stratum.uex.hk/api/v1/graph/entities \
  -H "Authorization: Bearer $TOKEN" | jq -r '.[0].id')
curl -s "https://stratum.uex.hk/api/v1/graph/subgraph/$ENTITY_ID" \
  -H "Authorization: Bearer $TOKEN" | jq '{nodes: [.nodes[].name], edges: (.edges | length)}'
# 期待: nodes 非空 + edges 数

git add -A
git commit -m "Phase 18 GraphRAG Stage A: migration 029/030 + graph_builder_service + graph router"
git push
```

---

## §8 R-1 / §20

- R-1: migration fail / LLM 抽取 JSON parse 报错（静默 log.warning，不 raise）/ graph 表不建 → 停
- R-3: 端到端 §7 步骤 1-6 全过才算完工
- §20: 不改主库

---

**完工逐字报告**:
- migration 029/030 建表确认
- inbox.py 钩子加入位置（行号）
- graph router 注册确认
- §7 端到端 6 步结果
- graph_entities 真实条数 + 示例实体名
- commit hash

**End of Phase 18 GraphRAG Stage A 指令书**
— Stratum advisor, 2026-06-15
