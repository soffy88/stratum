"""Fused search — cross_layer_search from oskill."""

import asyncio

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from stratum.common import jwt_auth

router = APIRouter(prefix="/api/v1", tags=["search"])

try:
    from oskill.cross_layer_search import cross_layer_search

    _HAS_SEARCH = True
except ImportError:
    _HAS_SEARCH = False


class SearchRequest(BaseModel):
    query: str
    mode: str = "augmented"
    top_k: int = 20
    pinned_boost: float = 1.5
    rerank: bool = False
    expand: bool = False
    medium_filter: list[str] | None = None
    domain_filter: list[str] | None = None
    date_range: tuple[str, str] | None = None
    view_id: str | None = None


@router.post("/search")
async def search(req: SearchRequest, user_id: str = Depends(jwt_auth)):
    if not _HAS_SEARCH:
        return {"results": [], "citations": [], "search_time_ms": 0, "scope_hits": {}}

    from stratum.api.search_utils import get_tantivy_mgr, get_lancedb_mgr

    lancedb_mgr = get_lancedb_mgr()
    tantivy_mgr = get_tantivy_mgr()

    async def _run(q: str):
        return await asyncio.to_thread(
            cross_layer_search,
            query=q,
            mode=req.mode,
            top_k=req.top_k,
            pinned_boost=req.pinned_boost,
            medium_filter=req.medium_filter,
            domain_filter=req.domain_filter,
            date_range=req.date_range,
            lancedb_mgr=lancedb_mgr,
            tantivy_mgr=tantivy_mgr,
            pgvector_mgr=None,
        )

    # Multi-query retrieval: when expand=True, fan out over LLM query variants and
    # union results (best score per id). The first run keeps citations/scope_hits.
    if req.expand:
        from stratum.service.rerank import expand_query

        queries = await asyncio.to_thread(expand_query, req.query, num_variants=3)
        first = await _run(queries[0])
        merged: dict[str, object] = {r.id: r for r in first.results}
        for q in queries[1:]:
            extra = await _run(q)
            for r in extra.results:
                prev = merged.get(r.id)
                if prev is None or getattr(r, "score", 0) > getattr(prev, "score", 0):
                    merged[r.id] = r
        result = first
        pool = sorted(
            merged.values(), key=lambda r: getattr(r, "score", 0), reverse=True
        )
    else:
        result = await _run(req.query)
        pool = list(result.results)

    # Defensive post-filter: when a result carries user_id (set by user-scoped
    # backends), reject rows that don't belong to the authenticated user.
    # Rows without user_id pass through — isolation is then the manager's job.
    own = [r for r in pool if getattr(r, "user_id", None) in (None, user_id)]

    # LLM-judge rerank (opt-in). Runs on the candidate pool before truncation.
    if req.rerank and own:
        from stratum.service.rerank import rerank_results

        own = await asyncio.to_thread(
            rerank_results, req.query, own, top_k=req.top_k
        )

    return {
        "results": [
            {
                "id": r.id,
                "type": r.type,
                "title": r.title,
                "score": round(r.score, 4),
                "highlight": r.highlight,
                "citation": r.citation.model_dump() if r.citation else None,
            }
            for r in own[: req.top_k]
        ],
        "citations": [c.model_dump() for c in (result.citations or [])],
        "search_time_ms": result.search_time_ms,
        "scope_hits": getattr(result, "scope_hit_counts", {}),
    }
