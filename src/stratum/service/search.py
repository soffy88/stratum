from typing import List, Optional

try:
    from oskill.hybrid_search import hybrid_search, SearchResult
except ImportError:
    hybrid_search = None  # type: ignore[assignment]
    SearchResult = None  # type: ignore[assignment,misc]
from stratum.dao.substrate import SubstrateDAO
import duckdb
import os


async def stratum_search(
    *,
    query: str,
    corpus_id: str,
    user_id: str,
    top_k: int = 10,
    rerank: bool = False,
    expand: bool = False,
    view_id: Optional[str] = None,
    filter_medium: Optional[List[str]] = None,
    **kwargs,
) -> List[SearchResult]:
    """Wrapper for oskill.hybrid_search with mandatory corpus isolation post-filter.

    corpus_id is passed to oskill (its interface); user_id is used to post-filter
    results against the substrates table (Phase 14 DB merge schema).

    rerank/expand are booleans at the API boundary but oskill.hybrid_search wants
    actual Reranker/QueryExpander callables — construct the LLM-backed adapters
    from search_reranker only when requested (skip the LLM round-trip otherwise).
    """
    if hybrid_search is None:
        raise ImportError("oskill is not installed")

    rerank_fn = None
    expand_fn = None
    if rerank:
        from stratum.service.search_reranker import llm_rerank

        rerank_fn = llm_rerank
    if expand:
        from stratum.service.search_reranker import llm_expand

        expand_fn = llm_expand

    raw_results = await hybrid_search(
        query=query,
        corpus_id=corpus_id,
        top_k=top_k * 3,
        rerank=rerank_fn,
        expand=expand_fn,
        view_id=view_id,
        filter_medium=filter_medium,
        **kwargs,
    )

    from stratum.db import get_conn

    with get_conn() as conn:
        dao = SubstrateDAO(conn)
        filtered_results = [
            res for res in raw_results if dao.get_substrate(substrate_id=res.id, user_id=user_id)
        ]
        return filtered_results[:top_k]
