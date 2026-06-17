from typing import Any
from pathlib import Path
from oprim.fulltext import open_fulltext_index
from oprim.vector_db import open_vector_db
from oskill.knowledge._context import tantivy_path, lancedb_path

import logging

logger = logging.getLogger(__name__)

from stratum.db import get_conn

import json

def get_tantivy_mgr():
    def tantivy_mgr(*, query: str, top_k: int, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        path = tantivy_path()
        if not path.exists():
            logger.warning(f"Tantivy path {path} does not exist")
            return []
        try:
            idx = open_fulltext_index(path)
            hits = idx.search(query, top_k=top_k)
            logger.info(f"Tantivy search for '{query}' returned {len(hits)} hits")
            
            # Fetch titles from DB
            ids = [h.id for h in hits]
            if not ids: return []
            
            with get_conn() as conn:
                placeholders = ",".join(["?" for _ in ids])
                rows = conn.execute(f"SELECT id, title, user_id FROM substrates WHERE id IN ({placeholders})", ids).fetchall()
                meta_map = {r[0]: {"title": r[1], "user_id": r[2]} for r in rows}
            
            return [
                {
                    "id": h.id, 
                    "type": "user_substrate", 
                    "title": meta_map.get(h.id, {}).get("title", h.id), 
                    "highlight": h.highlight or "", 
                    "user_id": meta_map.get(h.id, {}).get("user_id")
                } for h in hits
            ]
        except Exception as e:
            logger.error(f"Tantivy search failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    return tantivy_mgr

def get_lancedb_mgr():
    def lancedb_mgr(*, query_embedding: list[float] | None, query: str, top_k: int, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        path = lancedb_path()
        if not path.exists():
            logger.warning(f"LanceDB path {path} does not exist")
            return []
        try:
            db = open_vector_db(path, "vectors_text", 1024)
            
            if query_embedding is None:
                from oprim.embedding import embed_text
                query_embedding = embed_text([query])[0]
                
            if hasattr(db, "_table"):
                tbl = db._table
            else:
                import lancedb
                ldb = lancedb.connect(path)
                tbl = ldb.open_table("vectors_text")
            
            hits = tbl.search(query_embedding).limit(top_k).to_list()
            logger.info(f"LanceDB search for '{query}' returned {len(hits)} hits")
            
            processed_hits = []
            for h in hits:
                m = h.get("metadata")
                if isinstance(m, str):
                    try:
                        m = json.loads(m)
                    except:
                        m = {}
                processed_hits.append({"id": h["id"], "metadata": m, "text": h.get("text", "")})
            
            # Fetch titles from DB for substrate_id in metadata
            sub_ids = list(set([h["metadata"].get("substrate_id") for h in processed_hits if h["metadata"] and h["metadata"].get("substrate_id")]))
            if not sub_ids: return []
            
            with get_conn() as conn:
                placeholders = ",".join(["?" for _ in sub_ids])
                rows = conn.execute(f"SELECT id, title, user_id FROM substrates WHERE id IN ({placeholders})", sub_ids).fetchall()
                meta_map = {r[0]: {"title": r[1], "user_id": r[2]} for r in rows}
            
            results = []
            for h in processed_hits:
                sid = h["metadata"].get("substrate_id")
                results.append({
                    "id": sid, 
                    "type": "user_substrate", 
                    "title": meta_map.get(sid, {}).get("title", sid), 
                    "highlight": h["text"] or "", 
                    "user_id": meta_map.get(sid, {}).get("user_id")
                })
            return results
        except Exception as e:
            logger.error(f"LanceDB search failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    return lancedb_mgr
