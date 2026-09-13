"""Ownership-enforced writers for derived translation projections."""

from __future__ import annotations

from typing import Any, Iterable

from stratum.common import generate_ulid
from stratum.db import get_conn
from stratum.utils.user_id_hash import hash_user_id


def create_translation_projection(
    user_id: str,
    *,
    source_id: str,
    source_version: str,
    target_language: str,
    provider: str,
    model: str | None,
    translated_artifact_uri: str | None,
    artifact_hash: str | None,
    alignment_version: str = "v1",
) -> dict[str, Any]:
    """Create or reuse one projection for an authenticated source owner."""
    owner = hash_user_id(user_id)
    with get_conn() as conn:
        source = conn.execute(
            "SELECT id FROM substrates WHERE id=? AND user_id=?", (source_id, owner)
        ).fetchone()
        if not source:
            raise PermissionError("source is not owned by authenticated user")
        existing = conn.execute(
            """SELECT id FROM translation_projection
               WHERE user_id=? AND source_id=? AND source_version=?
                 AND target_language=? AND provider=?""",
            (owner, source_id, source_version, target_language, provider),
        ).fetchone()
        if existing:
            return {"id": existing[0], "status": "reused", "owner_hash": owner}
        projection_id = generate_ulid()
        conn.execute(
            """INSERT INTO translation_projection
               (id,user_id,source_id,source_version,target_language,provider,model,
                translated_artifact_uri,artifact_hash,alignment_version,status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                projection_id,
                owner,
                source_id,
                source_version,
                target_language,
                provider,
                model,
                translated_artifact_uri,
                artifact_hash,
                alignment_version,
                "completed",
            ),
        )
    return {"id": projection_id, "status": "created", "owner_hash": owner}


def persist_translation_mappings(
    user_id: str,
    translation_id: str,
    mappings: Iterable[dict[str, Any]],
) -> int:
    """Persist validated pair-to-fragment mappings under one owner scope."""
    owner = hash_user_id(user_id)
    rows = list(mappings)
    with get_conn() as conn:
        projection = conn.execute(
            "SELECT source_id FROM translation_projection WHERE id=? AND user_id=?",
            (translation_id, owner),
        ).fetchone()
        if not projection:
            raise PermissionError("translation is not owned by authenticated user")
        source_id = projection[0]
        written = 0
        for item in rows:
            fragment_id = item["original_fragment_id"]
            fragment = conn.execute(
                """SELECT c.id FROM substrate_chunk c
                   JOIN substrates s ON s.id=c.substrate_id
                   WHERE c.id=? AND c.substrate_id=? AND s.user_id=?""",
                (fragment_id, source_id, owner),
            ).fetchone()
            if not fragment:
                raise PermissionError("fragment is not owned by authenticated source")
            conn.execute(
                """INSERT INTO translation_pair_mapping
                   (translation_id,pair_ordinal,original_fragment_id,
                    fragment_overlap_start,fragment_overlap_end,pair_overlap_start,
                    pair_overlap_end,alignment_method,alignment_score)
                   VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING""",
                (
                    translation_id,
                    int(item["pair_ordinal"]),
                    fragment_id,
                    int(item.get("fragment_overlap_start", 0)),
                    int(item.get("fragment_overlap_end", 0)),
                    int(item.get("pair_overlap_start", 0)),
                    int(item.get("pair_overlap_end", 0)),
                    str(item.get("alignment_method", "recorded_source_exact")),
                    item.get("alignment_score"),
                ),
            )
            written += 1
    return written
