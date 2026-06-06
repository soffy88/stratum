from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

from stratum.utils.user_id_hash import hash_user_id


@dataclass
class Substrate:
    id: str
    user_id: str
    title: Optional[str]
    mime: Optional[str]
    source_path: Optional[str]
    file_hash: Optional[str]
    byte_size: Optional[int]
    page_count: Optional[int]
    parser: Optional[str]
    language: Optional[str]
    has_cjk: Optional[bool]
    is_scanned: Optional[bool]
    is_pinned: Optional[bool]
    pinned_at: Optional[datetime]
    pin_priority: Optional[int]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    meta_json: Optional[str]


class SubstrateDAO:
    # Matches the substrates table after Phase 14 DB merge (plural, user_id, no ulid/corpus_id)
    _COLS = (
        "id, user_id, title, mime, source_path, file_hash, byte_size, page_count, "
        "parser, language, has_cjk, is_scanned, is_pinned, pinned_at, pin_priority, "
        "created_at, updated_at, meta_json"
    )

    def __init__(self, db_conn):
        self.conn = db_conn

    def list_substrates(
        self,
        *,
        user_id: str,
        medium: Optional[str] = None,
        limit: int = 50,
        view_filter: Optional[dict] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> List[Substrate]:
        import json as _json
        uid_hash = hash_user_id(user_id)
        sql = f"SELECT {self._COLS} FROM substrates WHERE user_id = ?"
        params: list = [uid_hash]

        # Merge view_filter into query conditions
        if view_filter:
            mediums = view_filter.get("medium") or []
            tags = view_filter.get("tags") or []
            languages = view_filter.get("language") or []
            if mediums:
                placeholders = ", ".join("?" for _ in mediums)
                # medium maps to mime prefix: "paper"→"application/pdf", else LIKE %medium%
                mime_conditions = []
                for m in mediums:
                    mime_conditions.append("mime LIKE ?")
                    params.append(f"%{m}%")
                sql += f" AND ({' OR '.join(mime_conditions)})"
            if tags:
                for t in tags:
                    sql += " AND (meta_json->>'$.tags' LIKE ? OR meta_json LIKE ?)"
                    params.extend([f'%"{t}"%', f'%{t}%'])
            if languages:
                placeholders = ", ".join("?" for _ in languages)
                sql += f" AND language IN ({placeholders})"
                params.extend(languages)
        elif medium:
            sql += " AND mime LIKE ?"
            params.append(f"%{medium}%")

        allowed_sorts = {"created_at", "updated_at", "title", "pin_priority"}
        col = sort_by if sort_by in allowed_sorts else "created_at"
        order = "ASC" if sort_order.lower() == "asc" else "DESC"
        sql += f" ORDER BY {col} {order} LIMIT ?"
        params.append(limit)
        return [Substrate(*r) for r in self.conn.execute(sql, params).fetchall()]

    def get_substrate(self, *, substrate_id: str, user_id: str) -> Optional[Substrate]:
        res = self.conn.execute(
            f"SELECT {self._COLS} FROM substrates WHERE id = ? AND user_id = ?",
            (substrate_id, hash_user_id(user_id)),
        ).fetchone()
        return Substrate(*res) if res else None
