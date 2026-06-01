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

    result = await asyncio.to_thread(
        cross_layer_search,
        query=req.query,
        mode=req.mode,
        top_k=req.top_k,
        pinned_boost=req.pinned_boost,
        medium_filter=req.medium_filter,
        domain_filter=req.domain_filter,
        date_range=req.date_range,
        lancedb_mgr=None,
        tantivy_mgr=None,
        pgvector_mgr=None,
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
            for r in result.results[: req.top_k]
        ],
        "citations": [c.model_dump() for c in (result.citations or [])],
        "search_time_ms": result.search_time_ms,
        "scope_hits": getattr(result, "scope_hit_counts", {}),
    }
