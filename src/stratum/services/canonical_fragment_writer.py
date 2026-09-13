"""Canonical fragment persistence from an already-created Source derivative."""

from __future__ import annotations

import json
from typing import Any

from stratum.db import get_conn
from stratum.services.paragraph_chunking import paragraph_chunk
from stratum.utils.user_id_hash import hash_user_id


def ensure_canonical_fragments(
    source_id: str, user_id: str, *, content: str, parser_version: str = "paragraph_chunking-v1"
) -> int:
    """Materialize parser output as canonical fragments for an owned Source.

    This is the normal parser persistence boundary, not a translation repair:
    it only accepts content produced by the Source parser and is owner-scoped
    in SQL. Existing logical IDs are upserted, so re-ingest is idempotent.
    """
    if not content or not content.strip():
        return 0
    owner = hash_user_id(user_id)
    chunks = paragraph_chunk(content, min_chars=400, max_chars=2000)
    with get_conn() as conn:
        owned = conn.execute(
            "SELECT id FROM substrates WHERE id=? AND user_id=?", (source_id, owner)
        ).fetchone()
        if not owned:
            raise PermissionError("source is not owned by authenticated user")
        for item in chunks:
            idx = int(item["chunk_idx"])
            anchor: dict[str, Any] = {
                "start_pos": item.get("start_pos"),
                "end_pos": item.get("end_pos"),
                "heading_path": item.get("heading_path", ""),
                "block_types": item.get("block_types", []),
            }
            conn.execute(
                """INSERT INTO substrate_chunk
                (id,substrate_id,chunk_idx,text,version,anchor_json,parser_version)
                VALUES (?,?,?,?,?,?,?)
                ON CONFLICT (id) DO UPDATE SET text=EXCLUDED.text,
                  chunk_idx=EXCLUDED.chunk_idx, anchor_json=EXCLUDED.anchor_json,
                  parser_version=EXCLUDED.parser_version""",
                (
                    f"{source_id}#{idx}",
                    source_id,
                    idx,
                    item["content"],
                    1,
                    json.dumps(anchor),
                    parser_version,
                ),
            )
        conn.execute(
            "UPDATE substrates SET parser=?, parse_quality=?, quality_reason=?, updated_at=NOW() WHERE id=? AND user_id=?",
            (parser_version, "ok", None, source_id, owner),
        )
    return len(chunks)
