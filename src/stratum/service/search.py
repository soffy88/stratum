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
    *, query: str, corpus_id: str, user_id: str, top_k: int = 10, **kwargs
) -> List[SearchResult]:
    """Wrapper for oskill.hybrid_search with mandatory corpus isolation post-filter.

    corpus_id is passed to oskill (its interface); user_id is used to post-filter
    results against the substrates table (Phase 14 DB merge schema).
    """
    if hybrid_search is None:
        raise ImportError("oskill is not installed")

    raw_results = await hybrid_search(query=query, corpus_id=corpus_id, top_k=top_k * 3, **kwargs)

    from stratum.db import get_conn
    with get_conn() as conn:
        dao = SubstrateDAO(conn)
        filtered_results = [
            res for res in raw_results if dao.get_substrate(substrate_id=res.id, user_id=user_id)
        ]
        return filtered_results[:top_k]
