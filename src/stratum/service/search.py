from typing import List, Optional
from oskill.hybrid_search import hybrid_search, SearchResult
from stratum.dao.substrate import SubstrateDAO
import duckdb
import os

async def stratum_search(*, query: str, corpus_id: str, top_k: int = 10, **kwargs) -> List[SearchResult]:
    """Wrapper for oskill.hybrid_search with mandatory corpus isolation post-filter."""
    
    # 1. Call oskill hybrid_search
    # Note: oskill.hybrid_search takes corpus_id but currently doesn't enforce it in index search.
    raw_results = await hybrid_search(query=query, corpus_id=corpus_id, top_k=top_k * 3, **kwargs)
    
    # 2. Post-filter by corpus_id in Stratum service layer
    db_path = os.path.expanduser("~/.stratum/meta.duckdb")
    conn = duckdb.connect(db_path)
    try:
        dao = SubstrateDAO(conn)
        filtered_results = []
        for res in raw_results:
            # Verify each result belongs to the requested corpus
            substrate = dao.get_substrate(substrate_id=res.id, corpus_id=corpus_id)
            if substrate:
                filtered_results.append(res)
        
        return filtered_results[:top_k]
    finally:
        conn.close()
