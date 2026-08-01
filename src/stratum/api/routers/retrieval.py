"""分层检索 API — 目录递归检索 + 轨迹可观测 (对标 OpenViking Retrieval)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from stratum.common import jwt_auth

router = APIRouter(prefix="/api/v1", tags=["retrieval"])


class RetrieveRequest(BaseModel):
    query: str
    max_depth: int = 2           # 1=L0, 2=L0+L1, 3=L0+L1+L2
    top_k: int = 10
    layers: list[str] | None = None  # 覆盖 max_depth
    rerank: bool = False


@router.post("/retrieve")
async def retrieve_endpoint(req: RetrieveRequest, user_id: str = Depends(jwt_auth)):
    """分层检索 — 目录递归 + 轨迹追踪."""
    from stratum.services.retrieval_engine import retrieve

    response = retrieve(
        query=req.query,
        max_depth=req.max_depth,
        top_k=req.top_k,
        layers=req.layers,
        rerank=req.rerank,
        user_id=user_id,
    )

    from stratum.services.search_anchors import locate_anchor

    results_out = []
    sources = []
    for r in response.results:
        anchor = locate_anchor(r.content or "", None)
        preview = r.content[:300] if len(r.content) > 300 else r.content
        item = {
            "uri": r.uri,
            "node_type": r.node_type,
            "ref_id": r.ref_id,
            "layer": r.layer,
            "score": round(r.score, 4),
            "token_count": r.token_count,
            "content_preview": preview,
            "paragraph_index": anchor.get("paragraph_index"),
            "char_start": anchor.get("char_start"),
            "char_end": anchor.get("char_end"),
            "snippet": anchor.get("snippet") or preview,
            "deep_link": (
                f"stratum://substrate/{r.ref_id}#p{anchor.get('paragraph_index')}"
                if r.ref_id is not None
                else r.uri
            ),
        }
        results_out.append(item)
        if r.ref_id:
            sources.append(
                {
                    "substrate_id": r.ref_id,
                    "title": r.uri,
                    "snippet": item["snippet"],
                    "paragraph_index": item["paragraph_index"],
                    "score": item["score"],
                    "deep_link": item["deep_link"],
                    "layer": r.layer,
                }
            )

    return {
        "query": response.query,
        "total_ms": response.total_ms,
        "trajectory_id": response.trajectory_id,
        "result_count": len(response.results),
        "results": results_out,
        "sources": sources,
        "trajectory": [
            {
                "phase": s.phase,
                "candidates": s.candidates,
                "hits": s.hits,
                "top_scores": [round(x, 4) for x in s.scores[:5]],
                "details": s.details,
            }
            for s in response.trajectory
        ],
    }


@router.get("/retrieve/search")
async def retrieve_search(
    q: str = Query(..., description="Search query"),
    depth: int = Query(2, ge=1, le=3),
    top_k: int = Query(10, ge=1, le=50),
    rerank: bool = Query(False),
    user_id: str = Depends(jwt_auth),
):
    """GET 快捷检索 — 与 POST /retrieve 同形，含段落锚点 + sources[]."""
    return await retrieve_endpoint(
        RetrieveRequest(query=q, max_depth=depth, top_k=top_k, rerank=rerank),
        user_id=user_id,
    )


@router.get("/retrieve/debug")
async def retrieve_debug(
    q: str = Query(..., description="Search query"),
    depth: int = Query(3, ge=1, le=3),
    top_k: int = Query(5, ge=1, le=20),
    user_id: str = Depends(jwt_auth),
):
    """调试模式 — 返回完整轨迹 + 全部内容."""
    from stratum.services.retrieval_engine import retrieve

    response = retrieve(query=q, max_depth=depth, top_k=top_k, user_id=user_id)

    return {
        "query": response.query,
        "total_ms": response.total_ms,
        "trajectory_id": response.trajectory_id,
        "results": [
            {
                "uri": r.uri,
                "node_type": r.node_type,
                "ref_id": r.ref_id,
                "layer": r.layer,
                "score": round(r.score, 4),
                "token_count": r.token_count,
                "content": r.content,  # Full content in debug mode
            }
            for r in response.results
        ],
        "trajectory": [
            {
                "phase": s.phase,
                "candidates": s.candidates,
                "hits": s.hits,
                "scores": [round(x, 4) for x in s.scores],
                "details": s.details,
            }
            for s in response.trajectory
        ],
    }


@router.get("/trajectory/{trajectory_id}")
async def get_trajectory(trajectory_id: str, user_id: str = Depends(jwt_auth)):
    """获取检索轨迹详情 (仅本人)."""
    from stratum.services.retrieval_engine import get_trajectory
    from fastapi import HTTPException

    traj = get_trajectory(trajectory_id, user_id=user_id)
    if not traj:
        raise HTTPException(404, "Trajectory not found")
    return traj


@router.get("/trajectories")
async def list_trajectories(
    limit: int = Query(10, ge=1, le=50),
    user_id: str = Depends(jwt_auth),
):
    """列出最近的检索轨迹."""
    from stratum.services.retrieval_engine import get_recent_trajectories

    return {
        "trajectories": get_recent_trajectories(user_id=user_id, limit=limit),
    }


# ── Context Window (build_context for agents) ────────────────────────────────

class ContextRequest(BaseModel):
    query: str
    session_id: str | None = None
    max_retrieval: int = 5
    max_memories: int = 5
    include_conversation: bool = True
    format: str = "dict"  # "dict" or "prompt"


@router.post("/context")
async def build_context_window(
    req: ContextRequest,
    user_id: str = Depends(jwt_auth),
):
    """Build a context window for an agent (retrieval + WM + memories + conversation).

    对标 OpenViking build_context — 将所有上下文源组装成结构化 prompt.
    """
    from stratum.services.context_assembler import build_context

    ctx = build_context(
        query=req.query,
        session_id=req.session_id,
        user_id=user_id,
        max_retrieval=req.max_retrieval,
        max_memories=req.max_memories,
        include_conversation=req.include_conversation,
    )

    if req.format == "prompt":
        return {"prompt": ctx.to_prompt()}
    return ctx.to_dict()
