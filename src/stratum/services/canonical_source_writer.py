"""The single ownership-enforced canonical Source creation boundary."""

from __future__ import annotations

import json
from typing import Any

from stratum.common import generate_ulid
from stratum.db import get_conn
from stratum.utils.user_id_hash import hash_user_id


class CanonicalSourceOwnershipError(PermissionError):
    """Raised when a caller attempts to inject a different Source owner."""


class CanonicalSourceWriter:
    def __init__(self, conn: Any | None = None) -> None:
        self._conn = conn

    def create(
        self,
        *,
        authenticated_user: str,
        source_type: str,
        title: str,
        mime: str | None,
        original_binary_uri: str | None,
        file_hash: str | None,
        metadata: dict[str, Any] | None = None,
        byte_size: int | None = None,
        page_count: int | None = None,
        owner_hash: str | None = None,
        source_id: str | None = None,
    ) -> dict[str, Any]:
        derived_owner = hash_user_id(authenticated_user)
        if owner_hash is not None and owner_hash != derived_owner:
            raise CanonicalSourceOwnershipError("owner_hash does not match authenticated user")
        if not authenticated_user or not title or not source_type:
            raise ValueError("authenticated_user, source_type, and title are required")
        meta = dict(metadata or {})
        meta.setdefault("source_type", source_type)
        if original_binary_uri:
            meta.setdefault("original_binary_uri", original_binary_uri)
        if self._conn is not None:
            conn = self._conn
            if source_id:
                owned = conn.execute(
                    "SELECT id,user_id FROM substrates WHERE id=? LIMIT 1",
                    (source_id,),
                ).fetchone()
                if owned:
                    if owned[1] != derived_owner:
                        raise CanonicalSourceOwnershipError(
                            "source_id is not owned by authenticated user"
                        )
                    return {"id": owned[0], "status": "reused", "owner_hash": derived_owner}
            if file_hash:
                existing = conn.execute(
                    "SELECT id,title,mime,source_path,file_hash FROM substrates WHERE user_id=? AND file_hash=? LIMIT 1",
                    (derived_owner, file_hash),
                ).fetchone()
                if existing:
                    return {"id": existing[0], "status": "reused", "owner_hash": derived_owner}
            source_id = source_id or generate_ulid()
            conn.execute(
                """INSERT INTO substrates
                (id,user_id,title,mime,source_path,file_hash,byte_size,page_count,
                 meta_json,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,NOW(),NOW())""",
                (
                    source_id,
                    derived_owner,
                    title,
                    mime,
                    original_binary_uri,
                    file_hash,
                    byte_size,
                    page_count,
                    json.dumps(meta, ensure_ascii=False),
                ),
            )
        else:
            with get_conn() as conn:
                if source_id:
                    owned = conn.execute(
                        "SELECT id,user_id FROM substrates WHERE id=? LIMIT 1",
                        (source_id,),
                    ).fetchone()
                    if owned:
                        if owned[1] != derived_owner:
                            raise CanonicalSourceOwnershipError(
                                "source_id is not owned by authenticated user"
                            )
                        return {"id": owned[0], "status": "reused", "owner_hash": derived_owner}
                if file_hash:
                    existing = conn.execute(
                        "SELECT id FROM substrates WHERE user_id=? AND file_hash=? LIMIT 1",
                        (derived_owner, file_hash),
                    ).fetchone()
                    if existing:
                        return {"id": existing[0], "status": "reused", "owner_hash": derived_owner}
                source_id = source_id or generate_ulid()
                conn.execute(
                    """INSERT INTO substrates
                    (id,user_id,title,mime,source_path,file_hash,byte_size,page_count,
                     meta_json,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,NOW(),NOW())""",
                    (
                        source_id,
                        derived_owner,
                        title,
                        mime,
                        original_binary_uri,
                        file_hash,
                        byte_size,
                        page_count,
                        json.dumps(meta, ensure_ascii=False),
                    ),
                )
        return {"id": source_id, "status": "created", "owner_hash": derived_owner}
