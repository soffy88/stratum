"""分层检索 API — 目录递归检索 + 轨迹可观测 (对标 OpenViking Retrieval)."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Query
from fastapi import Path as FPath
from pydantic import BaseModel

from stratum.common import jwt_auth

router = APIRouter(prefix="/api/v1", tags=["retrieval"])


class RetrieveRequest(BaseModel):
    query: str
    max_depth: int = 2  # 1=L0, 2=L0+L1, 3=L0+L1+L2
    top_k: int = 10
    layers: list[str] | None = None  # 覆盖 max_depth
    rerank: bool = False
    namespace: str = "global"  # global | personal | all(联邦)
    budget_tokens: int | None = None  # 结果 token 预算(超预算截断低分项)
    use_planner: bool = True


@router.post("/retrieve/plan")
async def retrieve_plan(req: RetrieveRequest, user_id: str = Depends(jwt_auth)):
    """Return the inspectable A-RAG-compatible tool plan without running search."""
    from stratum.services.query_intent_planner import plan_query

    return {"query": req.query, "plan": plan_query(req.query).to_dict()}


@router.post("/retrieve")
async def retrieve_endpoint(req: RetrieveRequest, user_id: str = Depends(jwt_auth)):
    """分层检索 — 目录递归 + 轨迹追踪."""
    from stratum.services.query_intent_planner import plan_query
    from stratum.services.knowledge_view import KnowledgeView, KnowledgeViewRequest

    query_plan = plan_query(req.query) if req.use_planner else None
    effective_depth = max(req.max_depth, query_plan.max_depth) if query_plan else req.max_depth
    effective_rerank = req.rerank or (query_plan.rerank if query_plan else False)
    result = await asyncio.to_thread(
        KnowledgeView.search,
        KnowledgeViewRequest(
            query=req.query,
            top_k=req.top_k,
            user_id=user_id,
            rerank=effective_rerank,
            scopes=["learning"] if effective_depth >= 3 else ["lexical", "dense"],
            channels=["metadata", "lexical", "dense", "graph"],
        ),
    )
    return {
        **result,
        "query_plan": query_plan.to_dict() if query_plan else None,
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
    from stratum.services.knowledge_view import KnowledgeView, KnowledgeViewRequest

    response = KnowledgeView.search(
        KnowledgeViewRequest(
            query=q,
            top_k=top_k,
            user_id=user_id,
            scopes=["learning"] if depth >= 3 else ["lexical", "dense"],
        )
    )

    return {
        "query": response.query,
        "total_ms": response["total_ms"],
        "trajectory_id": response["trajectory_id"],
        "results": response["results"],
        "trajectory": response.get("trajectory", []),
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


# ── Mix Retrieval (KG + Vector + Chunks) ───────────────────────────────────


class MixRetrieveRequest(BaseModel):
    query: str
    mode: str = "mix"  # "vector" | "kg" | "chunk" | "mix"
    top_k: int = 10


@router.post("/retrieve/mix")
async def mix_retrieve_endpoint(
    req: MixRetrieveRequest,
    user_id: str = Depends(jwt_auth),
):
    """Mix Retrieval - KG + Vector + Chunks full fusion.

    Combines:
      - Vector search (L0 pgvector)
      - KG entity expansion (graph_entities + graph_relations)
      - Chunk search (substrate_chunk pgvector)

    Uses RRF (Reciprocal Rank Fusion) for weighted merging.
    Includes call chain tracking to prevent infinite loops.
    """
    from stratum.services.knowledge_view import KnowledgeView, KnowledgeViewRequest

    result = await asyncio.to_thread(
        KnowledgeView.search,
        KnowledgeViewRequest(
            query=req.query,
            top_k=req.top_k,
            user_id=user_id,
            scopes=["lexical", "dense", "graph"],
        ),
    )
    return {**result, "mode": req.mode, "chain": []}


# ── Document Deletion ───────────────────────────────────────────────────────


@router.delete("/substrate/{substrate_id}")
async def delete_substrate(
    substrate_id: str,
    hard: bool = Query(False, description="Hard delete (default: soft delete)"),
    cascade_graph: bool = Query(True, description="Also clean up graph references"),
    reason: str = Query("manual", description="Deletion reason"),
    user_id: str = Depends(jwt_auth),
):
    """Delete a substrate (document-level deletion with cascade)."""
    from stratum.services.document_deletion import (
        analyze_substrate_impact,
        soft_delete_substrate,
        hard_delete_substrate,
    )
    from fastapi import HTTPException

    impact = analyze_substrate_impact(substrate_id, user_id=user_id)
    if "error" in impact:
        raise HTTPException(404, f"Substrate not found: {substrate_id}")

    if hard:
        result = hard_delete_substrate(
            substrate_id, reason=reason, cascade_graph=cascade_graph, user_id=user_id
        )
    else:
        result = soft_delete_substrate(substrate_id, reason=reason, user_id=user_id)

    if result["errors"]:
        return {
            "substrate_id": substrate_id,
            "mode": "hard" if hard else "soft",
            "success": False,
            "errors": result["errors"],
            "deleted_records": result["deleted_records"],
        }

    return {
        "substrate_id": substrate_id,
        "mode": "hard" if hard else "soft",
        "success": True,
        "deleted_records": result["deleted_records"],
        "graph_cleaned": result.get("graph_cleaned", []),
    }


@router.get("/substrate/{substrate_id}/impact")
async def substrate_impact(
    substrate_id: str,
    user_id: str = Depends(jwt_auth),
):
    """Analyze what would be affected by deleting a substrate (dry-run)."""
    from stratum.services.document_deletion import analyze_substrate_impact
    from fastapi import HTTPException

    impact = analyze_substrate_impact(substrate_id, user_id=user_id)
    if "error" in impact:
        raise HTTPException(404, f"Substrate not found: {substrate_id}")
    return impact


@router.post("/substrate/delete-by-anchor")
async def delete_by_anchor(
    anchor: str = Query(..., description="Anchor value (path/hash/title)"),
    anchor_type: str = Query("source_path", description="source_path | file_hash | title"),
    soft: bool = Query(True, description="Soft delete"),
    user_id: str = Depends(jwt_auth),
):
    """Delete substrates by anchor match."""
    from stratum.services.document_deletion import delete_by_anchor as _delete_by_anchor

    result = _delete_by_anchor(anchor, anchor_type=anchor_type, soft=soft, user_id=user_id)
    return result


@router.post("/substrate/restore/{substrate_id}")
async def restore_substrate(
    substrate_id: str,
    user_id: str = Depends(jwt_auth),
):
    """Restore a soft-deleted substrate."""
    from stratum.services.document_deletion import restore_substrate as _restore
    from fastapi import HTTPException

    result = _restore(substrate_id, user_id=user_id)
    if result["errors"]:
        raise HTTPException(400, result["errors"])
    return result


# ── Multimodal Search ───────────────────────────────────────────────────────


@router.get("/multimodal/search")
async def search_multimodal(
    q: str = Query(..., description="Search query"),
    asset_type: str | None = Query(None, description="image | table | formula"),
    top_k: int = Query(10, ge=1, le=50),
    user_id: str = Depends(jwt_auth),
):
    """Search multimodal assets (images, tables, formulas) by semantic similarity."""
    from stratum.services.knowledge_view import KnowledgeView, KnowledgeViewRequest

    result = await asyncio.to_thread(
        KnowledgeView.search,
        KnowledgeViewRequest(query=q, top_k=top_k, user_id=user_id, channels=["visual"]),
    )
    return result


# ── Graph Health Scoring ─────────────────────────────────────────────────────


@router.get("/graph/health")
async def graph_health(
    include_clusters: bool = Query(
        True, description="Compute cluster connectivity (expensive BFS)"
    ),
    user_id: str = Depends(jwt_auth),
):
    """计算知识图谱健康评分 (0-100 分).

    对标 My Brain Is Full Crew Connector Agent 的图谱健康评分公式.

    评分维度:
      - 孤立率 (25%) — 没有关系的实体比例
      - 链接密度 (20%) — 每个实体的平均关系数
      - MOC 覆盖率 (20%) — 可从目录索引到达的实体比例
      - 聚类连通性 (15%) — 图的连通分量数
      - 死端率 (10%) — 只有入边没有出边的实体比例
      - 双向链接率 (10%) — 双向关系的比例
    """
    from stratum.services.graph_health_scorer import compute_graph_health_dict

    return compute_graph_health_dict(include_clusters=include_clusters)


# ── Vault Audit (7-Phase) ───────────────────────────────────────────────────


@router.post("/vault/audit")
async def run_vault_audit(
    include_graph_health: bool = Query(True, description="Include graph health scoring"),
    user_id: str = Depends(jwt_auth),
):
    """执行 7 阶段结构化审计.

    对标 My Brain Is Full Crew /vault-audit Skill.

    Phase 1: 结构扫描 — schema 一致性
    Phase 2: 重复检测 — 同名、(updated)/(copy)、内容相似度
    Phase 3: 链接完整性 — 坏链、孤立 KU
    Phase 4: 元数据审计 — 必填字段、值格式
    Phase 5: 目录索引 — MOC 可达性、过期索引
    Phase 6: 跨 Agent 集成 — 各子系统状态汇总
    Phase 7: 健康报告 — 月度趋势、可操作建议
    """
    from stratum.services.vault_audit import run_vault_audit_api

    return run_vault_audit_api()


@router.get("/vault/audit/latest")
async def get_latest_audit_report(user_id: str = Depends(jwt_auth)):
    """获取最近保存的健康报告."""
    from pathlib import Path
    import json

    reports_dir = Path.home() / ".stratum" / "Meta" / "health-reports"
    if not reports_dir.exists():
        return {"error": "No reports found", "path": str(reports_dir)}

    report_files = sorted(reports_dir.glob("*.json"), reverse=True)
    if not report_files:
        return {"error": "No reports found"}

    latest = report_files[0]
    try:
        report = json.loads(latest.read_text())
        return {
            "file": latest.name,
            "timestamp": report.get("timestamp", ""),
            "health_percentage": report.get("summary", {}).get("health_percentage", 0),
            "total_issues": report.get("summary", {}).get("total_issues", 0),
            "phases": report.get("phases", []),
            "recommendations": report.get("recommendations", []),
        }
    except Exception as e:
        return {"error": str(e)}


# ── Knowledge Gap Analysis ─────────────────────────────────────────────────


@router.get("/knowledge/gaps")
async def analyze_knowledge_gaps(
    topic: str | None = Query(None, description="Specific topic to analyze (None = all topics)"),
    top_k: int = Query(20, ge=1, le=50, description="Number of topics to analyze"),
    user_id: str = Depends(jwt_auth),
):
    """分析知识库在特定主题领域的覆盖缺口.

    对标 My Brain Is Full Crew Seeker Agent 的 Missing Knowledge Mode.

    功能:
      - 领域覆盖分析 — 某主题下 KU 数量、深度、多样性
      - 知识缺口发现 — 基于 L0/L1 层内容和 KG 关系推断缺失知识
      - 过时内容标记 — 超过 90 天未更新的 KU 标记为过时
      - 跨领域连接发现 — 识别可以建立桥梁的知识孤岛
    """
    from stratum.services.knowledge_gap_analyzer import analyze_all_gaps

    return analyze_all_gaps(
        topic_filter=topic,
        top_k=top_k,
        include_suggestions=True,
    )


# ── Agent State Management ─────────────────────────────────────────────────


@router.get("/agent/states")
async def list_agent_states(user_id: str = Depends(jwt_auth)):
    """列出当前用户的 Agent Post-it 状态(安全审计 🔴4: 按用户隔离)."""
    from stratum.services.agent_state import get_user_manager

    return {"states": get_user_manager(user_id).list_states()}


@router.get("/agent/states/{agent_name}")
async def get_agent_state(
    agent_name: str = FPath(..., pattern=r"^[A-Za-z0-9_.-]{1,64}$"),
    user_id: str = Depends(jwt_auth),
):
    """获取当前用户单个 Agent 的状态摘要."""
    from stratum.services.agent_state import get_user_manager

    return get_user_manager(user_id).get_state_summary(agent_name)


@router.post("/agent/states/{agent_name}/clear")
async def clear_agent_state(
    agent_name: str = FPath(..., pattern=r"^[A-Za-z0-9_.-]{1,64}$"),
    user_id: str = Depends(jwt_auth),
):
    """清除当前用户的 Agent 状态 (重置); 不再能清除全局/他人状态."""
    from stratum.services.agent_state import get_user_manager

    deleted = get_user_manager(user_id).clear_state(agent_name)
    return {"agent_name": agent_name, "deleted": deleted}


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
