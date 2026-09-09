"""Retrieval Engine — 目录递归分层检索 (对标 OpenViking Directory-Recursive Retrieval).

核心算法:
  Step 1: 粗筛 — 对所有 L0 做向量搜索, 找到 top-N 相关目录/节点
  Step 2: 钻取 — 对命中目录的子节点 L1 做二次搜索
  Step 3: 加载 — 对最终命中节点加载 L2 全文

关键特性:
  - trajectory: 每步记录 (候选数, 命中数, 得分分布) — 可观测性核心
  - depth_control: 可指定检索深度 (L0-only, L0+L1, L0+L1+L2)
  - hybrid_search: 向量搜索 + BM25 关键词
  - rerank: 复用现有 LLM rerank (aii/service/retrieval.py)
"""

from __future__ import annotations

import sys

_OPRIM_ROOT = "/data/soffy/projects/platform/3O/oprim"
if _OPRIM_ROOT not in sys.path:
    sys.path.insert(0, _OPRIM_ROOT)

import logging
import json
import re
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

import httpx
import numpy as np

from stratum.db import get_conn

logger = logging.getLogger(__name__)


def _user_owner_ids(user_id: str | None) -> tuple[str | None, str | None]:
    """Return (raw_user_id, hashed_user_id) for substrate ownership filters."""
    if not user_id or user_id == "default":
        return None, None
    from stratum.utils.user_id_hash import hash_user_id

    return user_id, hash_user_id(user_id)


_LLM_MODEL = "qwen3-8b"

# BGE-M3 embedder — must match substrate_layers.embedding space (1024-dim, cosine)
_bge: Any | None = None


def _get_bge():
    global _bge
    if _bge is None:
        from oprim.embedding.bge_m3 import BgeM3Embedder

        _bge = BgeM3Embedder()
    return _bge


# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class RetrievalStep:
    """Single step in the retrieval trajectory."""

    phase: str  # "coarse", "drill", "load", "rerank"
    candidates: int
    hits: int
    scores: list[float] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalResult:
    """Single retrieval result."""

    uri: str
    node_type: str
    ref_id: str | None
    layer: str  # "L0", "L1", "L2"
    content: str
    score: float
    token_count: int = 0
    namespace: str = "global"  # global=权威库(B仓/项目) | personal=个人草稿


@dataclass
class RetrievalResponse:
    """Complete retrieval response with trajectory."""

    query: str
    results: list[RetrievalResult]
    trajectory: list[RetrievalStep]
    total_ms: int
    trajectory_id: str | None = None


# ── Embedding ────────────────────────────────────────────────────────────────

_EMBED_DIM = 1024  # Must match substrate_layers.embedding vector dimension


def get_embedding(text: str) -> list[float] | None:
    """Get embedding vector for text using BGE-M3 — same space as substrate_layers.

    Truncates to _EMBED_DIM (1024) to match pgvector column.
    """
    try:
        text = text[:8000] if len(text) > 8000 else text
        emb = _get_bge().embed([text], dim=1024)
        if not emb or not emb[0]:
            return None
        vec = emb[0]
        return vec[:_EMBED_DIM] if len(vec) > _EMBED_DIM else vec
    except Exception as exc:
        logger.warning("retrieval_engine: BGE-M3 embedding failed: %s", exc)
        return None


# ── Vector search ────────────────────────────────────────────────────────────


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    a_np = np.array(a)
    b_np = np.array(b)
    dot = np.dot(a_np, b_np)
    norm_a = np.linalg.norm(a_np)
    norm_b = np.linalg.norm(b_np)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def _vector_search_layers(
    query_embedding: list[float],
    layer: str = "L0",
    top_k: int = 50,
    scope_uri: str | None = None,
    user_id: str | None = None,
) -> list[dict]:
    """Search substrate_layers by vector similarity using pgvector.

    When user_id is set, only returns layers for substrates owned by that user
    (raw JWT sub or hash_user_id). Returns list of {substrate_id, content, token_count, score}.
    """
    if not query_embedding:
        return []

    emb_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
    uid, uh = _user_owner_ids(user_id)
    owner_sql = ""
    owner_params: tuple = ()
    if uid is not None:
        owner_sql = " AND (s.user_id = ? OR s.user_id = ?)"
        owner_params = (uid, uh)

    with get_conn() as conn:
        try:
            rows = conn.execute(
                f"""SELECT sl.substrate_id, sl.content, sl.token_count,
                          1 - (sl.embedding <=> ?::vector) as score
                   FROM substrate_layers sl
                   JOIN substrates s ON s.id = sl.substrate_id
                   WHERE sl.layer = ? AND sl.embedding IS NOT NULL
                   {owner_sql}
                   ORDER BY sl.embedding <=> ?::vector
                   LIMIT ?""",
                (emb_str, layer, *owner_params, emb_str, top_k),
            ).fetchall()
            logger.debug("vector_search_layers: pgvector returned %d rows", len(rows))
            return [
                {"substrate_id": r[0], "content": r[1], "token_count": r[2], "score": float(r[3])}
                for r in rows
            ]
        except Exception as exc:
            logger.warning("vector_search_layers pgvector failed: %s — falling back to Python", exc)

    # Fallback: get embeddings (user-scoped when possible) and compute cosine in Python
    with get_conn() as conn:
        rows = conn.execute(
            f"""SELECT sl.substrate_id, sl.content, sl.token_count, sl.embedding
                FROM substrate_layers sl
                JOIN substrates s ON s.id = sl.substrate_id
                WHERE sl.layer = ? AND sl.embedding IS NOT NULL
                {owner_sql}""",
            (layer, *owner_params),
        ).fetchall()

    results = []
    for r in rows:
        sid, content, tc, emb = r
        try:
            emb_list = list(emb) if not isinstance(emb, list) else emb
            score = _cosine_similarity(query_embedding, emb_list)
            results.append(
                {"substrate_id": sid, "content": content, "token_count": tc, "score": score}
            )
        except Exception:
            continue

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


# ── Text search (BM25-like) ─────────────────────────────────────────────────


def _text_search_layers(
    query: str, layer: str = "L0", top_k: int = 50, user_id: str | None = None
) -> list[dict]:
    """Simple text search using ILIKE (case-insensitive LIKE).

    When user_id is set, only searches layers owned by that user.
    Returns list of {substrate_id, content, token_count, score}.
    """
    if not query:
        return []

    # Split query into terms
    terms = [t.strip() for t in query.split() if len(t.strip()) > 1]
    if not terms:
        return []

    uid, uh = _user_owner_ids(user_id)
    owner_sql = ""
    owner_params: list = []
    if uid is not None:
        owner_sql = " AND (s.user_id = ? OR s.user_id = ?)"
        owner_params = [uid, uh]

    with get_conn() as conn:
        # Build ILIKE conditions on sl.content
        conditions = " AND ".join("sl.content ILIKE ?" for _ in terms)
        params = [f"%{t}%" for t in terms] + [layer] + owner_params

        try:
            rows = conn.execute(
                f"""SELECT sl.substrate_id, sl.content, sl.token_count
                    FROM substrate_layers sl
                    JOIN substrates s ON s.id = sl.substrate_id
                    WHERE {conditions} AND sl.layer = ?
                    {owner_sql}
                    LIMIT ?""",
                tuple(params + [top_k]),
            ).fetchall()
        except Exception as exc:
            logger.warning("text_search failed: %s", exc)
            return []

    # Score by number of term matches
    results = []
    for r in rows:
        sid, content, tc = r
        content_lower = content.lower()
        matches = sum(1 for t in terms if t.lower() in content_lower)
        score = matches / len(terms) if terms else 0
        results.append(
            {
                "substrate_id": sid,
                "content": content,
                "token_count": tc,
                "score": score,
            }
        )

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


# ── Directory-aware retrieval ────────────────────────────────────────────────


def _search_personal_notes(query: str, top_k: int = 5) -> list[RetrievalResult]:
    """个人草稿区检索(~/.stratum/notes/*.md) — 关键词匹配 + 简单评分。

    设计(P3): 低门槛碎片区, 不做向量/不做图谱; 结果标注 namespace=personal,
    权重上限 0.6(低于 global 权威命中), 防污染核心库。
    """
    notes_dir = Path.home() / ".stratum" / "notes"
    if not notes_dir.is_dir():
        return []
    terms = [t.lower() for t in re.findall(r"[\w\u4e00-\u9fff]{2,}", query or "")]
    if not terms:
        return []
    hits: list[RetrievalResult] = []
    for f in sorted(notes_dir.glob("*.md"))[:200]:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")[:20000]
        except OSError:
            continue
        low = text.lower()
        matched = sum(1 for t in terms if t in low)
        if matched == 0:
            continue
        score = min(0.6, 0.25 + 0.07 * matched + 0.01 * min(len(text) // 500, 3))
        snippet = text[:400].replace("\n", " ")[:300]
        hits.append(
            RetrievalResult(
                uri=f"pnote://{f.stem}",
                node_type="note",
                ref_id=f.stem,
                layer="L0",
                content=snippet,
                score=score,
                token_count=len(snippet) // 4,
                namespace="personal",
            )
        )
    hits.sort(key=lambda r: r.score, reverse=True)
    return hits[:top_k]


def _get_directory_context(substrate_id: str) -> dict[str, Any] | None:
    """Get directory context for a substrate."""
    with get_conn() as conn:
        row = conn.execute(
            """SELECT cd.uri, cd.parent_id, pd.uri as parent_uri, pd.l0_content as dir_l0
               FROM context_directory cd
               LEFT JOIN context_directory pd ON cd.parent_id = pd.id
               WHERE cd.ref_id = ? AND cd.node_type = 'substrate'""",
            (substrate_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "uri": row[0],
        "parent_uri": row[2],
        "dir_l0": row[3],
    }


def _get_sibling_kus(parent_uri: str, limit: int = 5) -> list[dict]:
    """Get sibling KUs in the same directory."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT cd.uri, cd.ref_id, cd.l0_content
               FROM context_directory cd
               JOIN context_directory pd ON cd.parent_id = pd.id
               WHERE pd.uri = ? AND cd.node_type = 'ku'
               LIMIT ?""",
            (parent_uri, limit),
        ).fetchall()
    return [{"uri": r[0], "ku_id": r[1], "l0": r[2]} for r in rows]


def _get_directory_siblings(parent_uri: str, exclude_ids: set[str], limit: int = 5) -> list[dict]:
    """Get sibling substrate L0 summaries from the same directory.

    Used for directory-recursive retrieval: when a substrate matches,
    include its neighbors for richer context.
    """
    if not parent_uri:
        return []
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT cd.uri, cd.ref_id, cd.l0_content
               FROM context_directory cd
               JOIN context_directory pd ON cd.parent_id = pd.id
               WHERE pd.uri = ? AND cd.node_type = 'substrate'
               ORDER BY cd.uri
               LIMIT ?""",
            (parent_uri, limit + len(exclude_ids)),
        ).fetchall()
    results = []
    for uri, ref_id, l0 in rows:
        if ref_id not in exclude_ids and l0:
            results.append({"uri": uri, "substrate_id": ref_id, "l0": l0})
            if len(results) >= limit:
                break
    return results


# ── LLM Rerank ──────────────────────────────────────────────────────────────


def _llm_rerank(
    query: str, candidates: list[RetrievalResult], top_k: int = 10
) -> list[RetrievalResult]:
    """Re-rank candidates using Ollama LLM.

    Asks LLM to score each candidate's relevance to query, returns re-sorted list.
    Falls back to original order on any failure.
    """
    if not candidates:
        return []
    if len(candidates) <= 1:
        return candidates

    import json as _json

    # Build candidate list for LLM
    items = []
    for i, r in enumerate(candidates[:20]):  # Limit to 20 for LLM context
        snippet = r.content[:200].replace("\n", " ").strip()
        items.append(f"[{i}] {r.uri.split('/')[-1][:50]}: {snippet}")

    items_text = "\n".join(items)
    prompt = (
        f"Query: {query}\n\n"
        f"Candidates:\n{items_text}\n\n"
        f"Score each candidate's relevance to the query (0-10, 10=perfect match). "
        f'Return ONLY valid JSON: {{"scores":[{{"id":<int>,"score":<float>}}]}}'
    )

    try:
        resp = httpx.post(
            f"{_OLLAMA_BASE}/api/chat",
            json={
                "model": _LLM_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a precise retrieval re-ranker. Output valid JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        result = resp.json().get("message", {}).get("content", "").strip()

        # Strip thinking tags from qwen3
        if "" in result:
            result = re.sub(r"", "", result, flags=re.DOTALL).strip()

        # Parse JSON response
        match = re.search(r"\{.*\}", result, re.DOTALL)
        if not match:
            logger.warning("rerank: no JSON found in LLM response")
            return candidates[:top_k]

        data = _json.loads(match.group(0))
        scores_list = data.get("scores", [])

        # Build id→score mapping
        score_map = {}
        for entry in scores_list:
            try:
                idx = int(entry["id"])
                score = float(entry.get("score", 0))
                if 0 <= idx < len(candidates):
                    score_map[idx] = score
            except (KeyError, ValueError, TypeError):
                continue

        if not score_map:
            logger.warning("rerank: no valid scores parsed")
            return candidates[:top_k]

        # Create re-ranked list with updated scores
        reranked = []
        for idx in sorted(score_map.keys(), key=lambda i: score_map[i], reverse=True):
            r = candidates[idx]
            # Update score (normalize to 0-1 range)
            r.score = score_map[idx] / 10.0
            reranked.append(r)

        # Append candidates not scored by LLM (at the end)
        scored_ids = set(score_map.keys())
        for i, r in enumerate(candidates):
            if i not in scored_ids:
                reranked.append(r)

        logger.debug("rerank: re-sorted %d candidates", len(reranked))
        return reranked[:top_k]

    except Exception as exc:
        logger.warning("rerank failed: %s", exc)
        return candidates[:top_k]


# ── Main retrieval ──────────────────────────────────────────────────────────


def retrieve(
    query: str,
    max_depth: int = 2,
    top_k: int = 10,
    layers: list[str] | None = None,
    rerank: bool = False,
    user_id: str = "default",
    namespace: str = "global",
    budget_tokens: int | None = None,
) -> RetrievalResponse:
    """Directory-recursive retrieval with trajectory tracking.

    Args:
        query: Search query
        max_depth: Max retrieval depth (1=L0 only, 2=L0+L1, 3=L0+L1+L2)
        top_k: Number of results to return
        layers: Specific layers to retrieve (overrides max_depth)
        rerank: Whether to apply LLM reranking
        user_id: User ID for trajectory logging
        namespace: "global"(权威库) | "personal"(个人草稿) | "all"(联邦合并)
        budget_tokens: 结果 token 预算(book-to-skill 启发: 查询成本与答案成正比,
            默认 None=不限制; 超预算截断低分项)

    Returns:
        RetrievalResponse with results and trajectory
    """
    start_time = time.time()
    trajectory: list[RetrievalStep] = []

    if layers is None:
        if max_depth == 1:
            layers = ["L0"]
        elif max_depth == 2:
            layers = ["L0", "L1"]
        else:
            layers = ["L0", "L1", "L2"]

    # Step 1: Get query embedding
    query_emb = get_embedding(query)

    # Step 2: Coarse search — vector + text on L0
    vector_results = (
        _vector_search_layers(query_emb, "L0", top_k=50, user_id=user_id) if query_emb else []
    )
    text_results = _text_search_layers(query, "L0", top_k=50, user_id=user_id)

    # Merge and deduplicate
    seen_ids = set()
    merged: dict[str, dict] = {}
    for r in vector_results:
        sid = r["substrate_id"]
        if sid not in seen_ids:
            seen_ids.add(sid)
            merged[sid] = r
    for r in text_results:
        sid = r["substrate_id"]
        if sid in merged:
            merged[sid]["score"] = max(merged[sid]["score"], r["score"])
        else:
            merged[sid] = r

    coarse_results = sorted(merged.values(), key=lambda x: x["score"], reverse=True)[:30]

    trajectory.append(
        RetrievalStep(
            phase="coarse",
            candidates=len(vector_results) + len(text_results),
            hits=len(coarse_results),
            scores=[r["score"] for r in coarse_results[:10]],
            details={"vector_hits": len(vector_results), "text_hits": len(text_results)},
        )
    )

    # Step 2b: Directory-recursive expansion — boost siblings of top hits
    expanded_ids = set()
    for r in coarse_results[:5]:
        sid = r["substrate_id"]
        dir_ctx = _get_directory_context(sid)
        if dir_ctx and dir_ctx.get("parent_uri"):
            parent_uri = dir_ctx["parent_uri"]
            # Get sibling L0 summaries (exclude already-matched substrates)
            exclude = {c["substrate_id"] for c in coarse_results}
            siblings = _get_directory_siblings(parent_uri, exclude, limit=3)
            for sib in siblings:
                sib_id = sib["substrate_id"]
                if sib_id not in expanded_ids and sib_id not in exclude:
                    expanded_ids.add(sib_id)
                    # Boost sibling with discounted score
                    boosted_score = r["score"] * 0.7
                    merged[sib_id] = {
                        "substrate_id": sib_id,
                        "content": sib["l0"],
                        "token_count": len(sib["l0"]) // 4,
                        "score": boosted_score,
                        "uri": sib["uri"],
                        "is_sibling": True,
                    }

    if expanded_ids:
        # Re-sort with expanded results
        coarse_results = sorted(merged.values(), key=lambda x: x["score"], reverse=True)[:30]
        trajectory.append(
            RetrievalStep(
                phase="expand",
                candidates=len(expanded_ids),
                hits=len(expanded_ids),
                scores=[merged[sid]["score"] for sid in list(expanded_ids)[:5]],
                details={"siblings_added": len(expanded_ids)},
            )
        )

    # Step 3: Drill down — get directory context + L1 for top results
    enriched_results: list[RetrievalResult] = []
    for r in coarse_results[:15]:
        sid = r["substrate_id"]
        dir_ctx = _get_directory_context(sid)

        # Add L0 result
        enriched_results.append(
            RetrievalResult(
                uri=dir_ctx["uri"] if dir_ctx else f"viking://resources/其他/{sid}",
                node_type="substrate",
                ref_id=sid,
                layer="L0",
                content=r["content"],
                score=r["score"],
                token_count=r["token_count"],
            )
        )

        # If L1 requested, get it
        if "L1" in layers:
            with get_conn() as conn:
                l1_row = conn.execute(
                    "SELECT content, token_count FROM substrate_layers WHERE substrate_id=? AND layer='L1'",
                    (sid,),
                ).fetchone()
            if l1_row:
                enriched_results.append(
                    RetrievalResult(
                        uri=dir_ctx["uri"] if dir_ctx else f"viking://resources/其他/{sid}",
                        node_type="substrate",
                        ref_id=sid,
                        layer="L1",
                        content=l1_row[0],
                        score=r["score"] * 0.9,  # slight discount for deeper layer
                        token_count=l1_row[1],
                    )
                )

    trajectory.append(
        RetrievalStep(
            phase="drill",
            candidates=len(coarse_results[:15]),
            hits=len(enriched_results),
            scores=[r.score for r in enriched_results[:10]],
        )
    )

    # Step 4: Load L2 if requested (only for top-k)
    if "L2" in layers:
        top_substrate_ids = [r.ref_id for r in enriched_results if r.layer == "L0"][:top_k]
        for sid in top_substrate_ids:
            with get_conn() as conn:
                l2_row = conn.execute(
                    "SELECT content, token_count FROM substrate_layers WHERE substrate_id=? AND layer='L2'",
                    (sid,),
                ).fetchone()
            if l2_row:
                dir_ctx = _get_directory_context(sid)
                enriched_results.append(
                    RetrievalResult(
                        uri=dir_ctx["uri"] if dir_ctx else f"viking://resources/其他/{sid}",
                        node_type="substrate",
                        ref_id=sid,
                        layer="L2",
                        content=l2_row[0][:3000],  # Truncate L2 to save tokens
                        score=next(
                            (
                                r.score
                                for r in enriched_results
                                if r.ref_id == sid and r.layer == "L0"
                            ),
                            0.5,
                        )
                        * 0.8,
                        token_count=min(l2_row[1], 750),
                    )
                )

        trajectory.append(
            RetrievalStep(
                phase="load",
                candidates=len(top_substrate_ids),
                hits=len([r for r in enriched_results if r.layer == "L2"]),
                scores=[r.score for r in enriched_results if r.layer == "L2"][:10],
            )
        )

    # Step 5: Optional rerank (using Ollama LLM)
    if rerank and len(enriched_results) > 5:
        l0_results = [r for r in enriched_results if r.layer == "L0"]
        reranked = _llm_rerank(query, l0_results, top_k=min(top_k, len(l0_results)))
        if reranked:
            # Reorder: reranked L0s first, then other layers
            rerank_ids = {r.ref_id for r in reranked}
            other_results = [
                r for r in enriched_results if r.ref_id not in rerank_ids or r.layer != "L0"
            ]
            enriched_results = reranked + other_results
            trajectory.append(
                RetrievalStep(
                    phase="rerank",
                    candidates=len(l0_results),
                    hits=len(reranked),
                    scores=[r.score for r in reranked[:10]],
                )
            )

    # Step 5b: Personal 层联邦检索(P3) — namespace ∈ {personal, all}
    # 个人草稿(~/.stratum/notes/*.md)低门槛碎片区: 只做关键词匹配, 结果标注
    # namespace=personal 且权重打折(global 权威优先); 永不进入图谱/规范构建。
    if namespace in ("personal", "all"):
        personal_hits = _search_personal_notes(query, top_k=5)
        if personal_hits:
            trajectory.append(
                RetrievalStep(
                    phase="personal",
                    candidates=len(personal_hits),
                    hits=len(personal_hits),
                    scores=[r.score for r in personal_hits[:10]],
                    details={"namespace": "personal"},
                )
            )
            enriched_results.extend(personal_hits)
    if namespace == "personal":
        enriched_results = [r for r in enriched_results if r.namespace == "personal"]

    # Sort by score and limit (global 权威 + personal 草稿混排时 global 权重已内建)
    enriched_results.sort(key=lambda r: r.score, reverse=True)
    final_results = enriched_results[: top_k * len(layers)]
    # ★Token 预算(book-to-skill 启发 P1): 查询成本与答案成正比
    # 按 score 顺序累计 token_count, 超预算截断低分项(保高分权威内容)
    if budget_tokens and budget_tokens > 0:
        used = 0
        kept: list[RetrievalResult] = []
        for r in final_results:
            if used + (r.token_count or 0) > budget_tokens and kept:
                trajectory.append(
                    RetrievalStep(
                        phase="budget",
                        candidates=len(final_results),
                        hits=len(kept),
                        details={
                            "budget_tokens": budget_tokens,
                            "used_tokens": used,
                            "truncated": len(final_results) - len(kept),
                        },
                    )
                )
                break
            used += r.token_count or 0
            kept.append(r)
        final_results = kept

    total_ms = int((time.time() - start_time) * 1000)

    # Store trajectory
    trajectory_id = _store_trajectory(
        query, query_emb, final_results, trajectory, total_ms, user_id
    )

    return RetrievalResponse(
        query=query,
        results=final_results,
        trajectory=trajectory,
        total_ms=total_ms,
        trajectory_id=trajectory_id,
    )


# ── Trajectory storage ────────────────────────────────────────────────────────


def _store_trajectory(
    query: str,
    query_emb: list[float] | None,
    results: list[RetrievalResult],
    trajectory: list[RetrievalStep],
    total_ms: int,
    user_id: str,
) -> str:
    """Store retrieval trajectory in DB."""
    import hashlib

    traj_id = hashlib.sha256(f"{query}-{time.time()}".encode()).hexdigest()[:24]

    results_json = [
        {
            "uri": r.uri,
            "layer": r.layer,
            "score": round(r.score, 4),
            "content_preview": r.content[:200],
            "token_count": r.token_count,
        }
        for r in results
    ]
    trajectory_json = [
        {
            "phase": s.phase,
            "candidates": s.candidates,
            "hits": s.hits,
            "scores": [round(x, 4) for x in s.scores[:10]],
            "details": s.details,
        }
        for s in trajectory
    ]

    try:
        with get_conn() as conn:
            conn.execute(
                """INSERT INTO retrieval_trajectories
                   (id, user_id, query, query_embedding, results, trajectory, total_ms, result_count)
                   VALUES (?, ?, ?, ?, ?::jsonb, ?::jsonb, ?, ?)""",
                (
                    traj_id,
                    user_id,
                    query,
                    query_emb,  # psycopg2 should handle float[] → vector
                    json.dumps(results_json, ensure_ascii=False),
                    json.dumps(trajectory_json, ensure_ascii=False),
                    total_ms,
                    len(results),
                ),
            )
    except Exception as exc:
        logger.warning("store_trajectory failed: %s", exc)
        return ""

    return traj_id


def get_trajectory(trajectory_id: str, user_id: str | None = None) -> dict[str, Any] | None:
    """Get stored trajectory by ID. When user_id set, only return own trajectories."""
    with get_conn() as conn:
        if user_id is not None:
            row = conn.execute(
                """SELECT query, results, trajectory, total_ms, result_count, created_at
                   FROM retrieval_trajectories WHERE id = ? AND user_id = ?""",
                (trajectory_id, user_id),
            ).fetchone()
        else:
            row = conn.execute(
                """SELECT query, results, trajectory, total_ms, result_count, created_at
                   FROM retrieval_trajectories WHERE id = ?""",
                (trajectory_id,),
            ).fetchone()
    if not row:
        return None
    return {
        "query": row[0],
        "results": row[1],
        "trajectory": row[2],
        "total_ms": row[3],
        "result_count": row[4],
        "created_at": str(row[5]),
    }


def get_recent_trajectories(user_id: str = "default", limit: int = 10) -> list[dict]:
    """Get recent retrieval trajectories."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT id, query, total_ms, result_count, created_at
               FROM retrieval_trajectories
               WHERE user_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
    return [
        {"id": r[0], "query": r[1], "total_ms": r[2], "result_count": r[3], "created_at": str(r[4])}
        for r in rows
    ]
