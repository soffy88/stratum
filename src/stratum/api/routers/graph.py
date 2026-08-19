"""B 仓概念图遍历端点 — graphify 模式(graphify 启发②)。

  GET /graph/explain?concept=income+elasticity&max_hops=3
  GET /graph/path?src=elasticity&dst=demand+curve&max_hops=8

纯图遍历(零 LLM, 零向量): explain=seed BFS 扩散; path=双向 BFS 最短路径。
数据源: B 仓概念图(rf schema, 收敛终点, 权威)。
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from stratum.services.graph_query import get_graph

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/explain")
async def graph_explain(
    concept: str = Query(..., description="概念名"),
    max_hops: int = Query(3, ge=1, le=6),
    top_k: int = Query(20, ge=1, le=50),
) -> dict:
    """BFS hop 扩散: seed 概念 → 层级邻居(按 KU 挂载数排序)。"""
    return get_graph().explain(concept, max_hops=max_hops, top_k=top_k)


@router.get("/path")
async def graph_path(
    src: str = Query(..., description="起点概念"),
    dst: str = Query(..., description="终点概念"),
    max_hops: int = Query(8, ge=1, le=12),
) -> dict:
    """最短路径(双向 BFS): hop-by-hop 概念链, 可解释。"""
    return get_graph().path(src, dst, max_hops=max_hops)
