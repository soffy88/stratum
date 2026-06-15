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
        return [n["target"] for n in get_entity_neighbors(uh, [node_id])]

    result = graph_traversal(
        start_nodes=[entity_id],
        get_neighbors=get_neighbors,
        mode="bfs",
        max_depth=max_hops,
        max_nodes=100,
    )

    node_ids = result.get("visited", [])
    nodes = query_entities_by_ids(uh, node_ids)
    edges = get_entity_neighbors(uh, node_ids)

    return {"nodes": nodes, "edges": edges, "seed": entity_id}


class _Edge:
    """Minimal edge object satisfying oprim.entity_graph_search protocol."""
    __slots__ = ("dst_id",)

    def __init__(self, dst_id: str) -> None:
        self.dst_id = dst_id


@router.post("/query")
async def graphrag_query(
    body: dict,
    user=Depends(get_current_user),
):
    """
    GraphRAG 查询: question → entity link → graph traverse → context → LLM answer.
    """
    import asyncio
    from oprim import entity_graph_search, llm_call

    question = body.get("question", "")
    max_hops = body.get("max_hops", 2)
    top_k = body.get("top_k", 5)
    uh = hash_user_id(user.user_id)

    # 1. 从 graph_entities 取 seed（按 mention_count 排序）
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

    # 2. entity_graph_search（oprim BFS，edge objects need .dst_id）
    def list_edges(node_id: str) -> list[_Edge]:
        return [_Edge(n["target"]) for n in get_entity_neighbors(uh, [node_id])]

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

    # 5. LLM 综合（sync call in thread）
    prompt = f"""根据以下知识库内容回答问题。

问题: {question}

相关内容:
{context}

请基于内容给出准确、简洁的回答。如果内容不足以回答，请说明。"""

    resp = await asyncio.to_thread(llm_call, prompt, "qwen3_dashscope")
    answer = resp.text

    return {
        "answer": answer,
        "sources": substrate_ids,
        "entities_used": [all_entity_names.get(eid, eid) for eid in top_entity_ids],
    }
