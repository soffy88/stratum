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
    cross_layer_search = None  # stable module surface for tests/patching


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

    # Ownership enforcement at the boundary. User-scoped managers (incl. the
    # shared tantivy/lance managers in search_utils) attach user_id to every
    # result — resolved from substrates.user_id, i.e. the HASHED id, so both
    # the raw JWT subject and its hash count as "self". Shared content and
    # backends that don't attach it (user_id=None) pass through.
    from stratum.utils.user_id_hash import hash_user_id as _hash_uid

    _self_ids = {user_id, _hash_uid(user_id)}
    own = [r for r in pool if getattr(r, "user_id", None) in (None, *_self_ids)]

    # LLM-judge rerank (opt-in). Runs on the candidate pool before truncation.
    if req.rerank and own:
        from stratum.service.rerank import rerank_results

        own = await asyncio.to_thread(
            rerank_results, req.query, own, top_k=req.top_k
        )

    # Enrich with paragraph anchors + unified sources[] (MVP 检索出处)
    from stratum.db import query as db_query
    from stratum.services.search_anchors import enrich_result_with_anchor

    top = own[: req.top_k]
    ids = [r.id for r in top]
    content_map: dict[str, str] = {}
    if ids:
        try:
            rows = db_query(
                """
                SELECT DISTINCT ON (substrate_id) substrate_id, content
                FROM derivative
                WHERE substrate_id = ANY(%(ids)s)
                  AND content IS NOT NULL AND content <> ''
                ORDER BY substrate_id,
                  CASE WHEN kind='markdown' THEN 0
                       WHEN kind LIKE 'translation%%zh%%' THEN 1
                       ELSE 2 END
                """,
                {"ids": ids},
            )
            content_map = {r["substrate_id"]: r["content"] or "" for r in rows}
        except Exception:
            content_map = {}

    results_out = []
    sources = []
    for r in top:
        cit = r.citation.model_dump() if getattr(r, "citation", None) else None
        full = content_map.get(r.id, "")
        anchored = enrich_result_with_anchor(
            substrate_id=r.id,
            title=r.title,
            highlight=getattr(r, "highlight", None),
            full_text=full,
            score=round(getattr(r, "score", 0) or 0, 4),
        )
        results_out.append(
            {
                "id": r.id,
                "type": r.type,
                "title": r.title,
                "score": round(r.score, 4),
                "highlight": r.highlight,
                "citation": cit,
                "paragraph_index": anchored["paragraph_index"],
                "char_start": anchored["char_start"],
                "char_end": anchored["char_end"],
                "snippet": anchored["snippet"],
                "anchor_status": anchored["anchor_status"],
                "deep_link": anchored["deep_link"],
            }
        )
        sources.append(
            {
                "substrate_id": r.id,
                "title": r.title,
                "snippet": anchored["snippet"],
                "paragraph_index": anchored["paragraph_index"],
                "char_start": anchored["char_start"],
                "char_end": anchored["char_end"],
                "deep_link": anchored["deep_link"],
                "score": round(r.score, 4),
            }
        )

    return {
        "results": results_out,
        "sources": sources,
        "citations": [c.model_dump() for c in (result.citations or [])],
        "search_time_ms": result.search_time_ms,
        "scope_hits": getattr(result, "scope_hit_counts", {}),
    }
