from typing import Any
from pathlib import Path
from oprim.fulltext import open_fulltext_index
from oprim.vector_db import open_vector_db
from oskill.knowledge._context import tantivy_path, lancedb_path

import logging

logger = logging.getLogger(__name__)

from stratum.db import get_conn

import json
import re

_SNIPPET_CHARS = 400  # snippet length fed to rerank + shown as preview


def _fetch_meta(ids: list[str]) -> dict[str, dict[str, Any]]:
    """Batch-fetch title + user_id + a markdown-content snippet for substrate ids.

    Returns {id: {"title", "user_id", "snippet"}}. Title falls back to the first
    markdown heading / first non-empty line when substrates.title is just the ULID
    (failed ingest-time extraction). Snippet gives rerank real text to score on,
    since oprim's tantivy highlight comes back empty.
    """
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    with get_conn() as conn:
        # Prefer markdown, else the longest non-empty derivative of any kind, so
        # substrates without a markdown derivative still get a usable snippet.
        rows = conn.execute(
            f"SELECT s.id, s.title, s.user_id, ("
            f"  SELECT substr(d.content, 1, 2000) FROM derivative d "
            f"  WHERE d.substrate_id = s.id AND d.content IS NOT NULL AND length(d.content) > 0 "
            f"  ORDER BY (d.kind = 'markdown') DESC, length(d.content) DESC LIMIT 1"
            f") AS snippet "
            f"FROM substrates s WHERE s.id IN ({placeholders})",
            ids,
        ).fetchall()
    meta: dict[str, dict[str, Any]] = {}
    for sid, title, user_id, content in rows:
        content = content or ""
        # Title fallback when stored title is just the ULID.
        display_title = title
        if not title or title == sid:
            display_title = _derive_title(content) or sid
        snippet = _clean_snippet(content)[:_SNIPPET_CHARS]
        meta[sid] = {"title": display_title, "user_id": user_id, "snippet": snippet}
    return meta


def _derive_title(content: str) -> str | None:
    """First markdown heading, else first non-trivial line."""
    for line in content.splitlines():
        m = re.match(r"^\s{0,3}#{1,6}\s+(.*\S)", line)
        if m:
            return m.group(1).strip()[:120]
    for line in content.splitlines():
        s = line.strip()
        if len(s) >= 4:
            return s[:120]
    return None


def _clean_snippet(content: str) -> str:
    """Collapse whitespace/markdown noise into a compact preview string."""
    s = re.sub(r"[#>*`_\-]{1,}", " ", content)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def get_tantivy_mgr():
    def tantivy_mgr(*, query: str, top_k: int, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        path = tantivy_path()
        if not path.exists():
            logger.warning(f"Tantivy path {path} does not exist")
            return []
        try:
            idx = open_fulltext_index(path)
            # Over-fetch: the index is polluted with stale entries (deleted
            # substrates). Pull extra so enough survive ghost-filtering below.
            hits = idx.search(query, top_k=max(top_k * 5, 50))
            logger.info(f"Tantivy search for '{query}' returned {len(hits)} hits")
            
            # Fetch titles + content snippets from DB
            ids = [h.id for h in hits]
            if not ids: return []

            meta_map = _fetch_meta(ids)

            # Drop stale index entries whose substrate no longer exists in the DB
            # (orphaned tantivy rows left by deletes/merges → ghost results).
            return [
                {
                    "id": h.id,
                    "type": "user_substrate",
                    "title": meta_map[h.id].get("title") or h.id,
                    # oprim tantivy highlight is empty → fall back to content snippet
                    "highlight": (h.highlight or "").strip() or meta_map[h.id].get("snippet", ""),
                    "user_id": meta_map[h.id].get("user_id")
                } for h in hits if h.id in meta_map
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
            
            # Over-fetch to survive ghost-filtering of stale vector entries.
            hits = tbl.search(query_embedding).limit(max(top_k * 5, 50)).to_list()
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
            
            # Fetch titles + content snippets from DB for substrate_id in metadata
            sub_ids = list(set([h["metadata"].get("substrate_id") for h in processed_hits if h["metadata"] and h["metadata"].get("substrate_id")]))
            if not sub_ids: return []

            meta_map = _fetch_meta(sub_ids)

            results = []
            for h in processed_hits:
                sid = h["metadata"].get("substrate_id")
                if sid not in meta_map:  # stale vector entry, substrate deleted
                    continue
                # Prefer the matched chunk text; fall back to content snippet.
                hl = (h.get("text") or "").strip() or meta_map[sid].get("snippet", "")
                results.append({
                    "id": sid,
                    "type": "user_substrate",
                    "title": meta_map[sid].get("title") or sid,
                    "highlight": hl,
                    "user_id": meta_map[sid].get("user_id")
                })
            return results
        except Exception as e:
            logger.error(f"LanceDB search failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    return lancedb_mgr
