"""Small, durable provenance API; deliberately not an agent/notebook runtime."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from stratum.common import generate_ulid
from stratum.db import get_conn
from stratum.utils.user_id_hash import hash_user_id


def content_hash(data: bytes | str) -> str:
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


def create_artifact(
    user_id: str,
    *,
    artifact_type: str,
    content_uri: str,
    output_hash: str,
    producer_type: str,
    producer_name: str,
    producer_version: str | None = None,
    model: str | None = None,
    prompt_hash: str | None = None,
    environment_hash: str | None = None,
    config: dict[str, Any] | None = None,
    inputs: Iterable[dict[str, str | None]] = (),
    supersedes_id: str | None = None,
) -> str:
    aid, owner = generate_ulid(), hash_user_id(user_id)
    input_rows = [dict(item) for item in inputs]
    with get_conn() as conn:
        # Validate every provenance edge before writing the artifact.  The
        # authenticated owner is authoritative; caller-supplied hashes are
        # never accepted as an ownership assertion.
        for item in input_rows:
            source_id = item.get("source_id")
            fragment_id = item.get("fragment_id")
            parent_id = item.get("artifact_parent_id")
            if source_id:
                if not conn.execute(
                    "SELECT 1 FROM substrates WHERE id=? AND user_id=?",
                    (source_id, owner),
                ).fetchone():
                    raise PermissionError(
                        "artifact input source is not owned by authenticated user"
                    )
            if fragment_id:
                if not conn.execute(
                    """SELECT 1 FROM substrate_chunk c JOIN substrates s
                       ON s.id=c.substrate_id
                       WHERE c.id=? AND s.user_id=?""",
                    (fragment_id, owner),
                ).fetchone():
                    raise PermissionError(
                        "artifact input fragment is not owned by authenticated user"
                    )
            if parent_id:
                if not conn.execute(
                    "SELECT 1 FROM derived_artifact WHERE id=? AND user_id=?",
                    (parent_id, owner),
                ).fetchone():
                    raise PermissionError("artifact parent is not owned by authenticated user")
        if (
            supersedes_id
            and not conn.execute(
                "SELECT 1 FROM derived_artifact WHERE id=? AND user_id=?",
                (supersedes_id, owner),
            ).fetchone()
        ):
            raise PermissionError("superseded artifact is not owned by authenticated user")
        # Replays of the same immutable output are idempotent.  A changed
        # output hash is a new artifact/version, never an in-place mutation.
        existing = conn.execute(
            """SELECT id FROM derived_artifact
               WHERE user_id=? AND artifact_type=? AND content_hash=?
                 AND producer_name=? AND COALESCE(producer_version,'')=COALESCE(?, '')
                 AND COALESCE(supersedes_id,'')=COALESCE(?, '')""",
            (owner, artifact_type, output_hash, producer_name, producer_version, supersedes_id),
        ).fetchone()
        if existing:
            aid = str(existing[0])
        else:
            conn.execute(
                """INSERT INTO derived_artifact
                (id,user_id,artifact_type,content_uri,content_hash,producer_type,producer_name,producer_version,model,prompt_hash,environment_hash,config,supersedes_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    aid,
                    owner,
                    artifact_type,
                    content_uri,
                    output_hash,
                    producer_type,
                    producer_name,
                    producer_version,
                    model,
                    prompt_hash,
                    environment_hash,
                    json.dumps(config or {}),
                    supersedes_id,
                ),
            )
        for item in input_rows:
            # artifact_input is a typed union row.  PostgreSQL UNIQUE/PK
            # semantics do not deduplicate NULL values, so compare nullable
            # dimensions explicitly before inserting a replay.
            duplicate_input = conn.execute(
                """SELECT 1 FROM artifact_input
                   WHERE artifact_id=?
                     AND source_id IS NOT DISTINCT FROM ?
                     AND fragment_id IS NOT DISTINCT FROM ?
                     AND evidence_id IS NOT DISTINCT FROM ?
                     AND claim_id IS NOT DISTINCT FROM ?
                     AND artifact_parent_id IS NOT DISTINCT FROM ?""",
                (
                    aid,
                    item.get("source_id"),
                    item.get("fragment_id"),
                    item.get("evidence_id"),
                    item.get("claim_id"),
                    item.get("artifact_parent_id"),
                ),
            ).fetchone()
            if duplicate_input:
                continue
            conn.execute(
                """INSERT INTO artifact_input
                (artifact_id,source_id,fragment_id,evidence_id,claim_id,artifact_parent_id)
                VALUES (?,?,?,?,?,?) ON CONFLICT DO NOTHING""",
                (
                    aid,
                    item.get("source_id"),
                    item.get("fragment_id"),
                    item.get("evidence_id"),
                    item.get("claim_id"),
                    item.get("artifact_parent_id"),
                ),
            )
    return aid


def attach_translation_artifact(user_id: str, translation_id: str, artifact_id: str) -> None:
    """Link an owned TranslationProjection to its derived translation artifact."""
    owner = hash_user_id(user_id)
    with get_conn() as conn:
        row = conn.execute(
            """SELECT t.source_id, a.user_id, a.artifact_type
               FROM translation_projection t
               JOIN derived_artifact a ON a.id=?
               WHERE t.id=? AND t.user_id=?""",
            (artifact_id, translation_id, owner),
        ).fetchone()
        if not row or row[1] != owner or row[2] != "translation":
            raise PermissionError("translation/artifact ownership or type mismatch")
        conn.execute(
            "UPDATE translation_projection SET artifact_id=? WHERE id=? AND user_id=?",
            (artifact_id, translation_id, owner),
        )


def list_artifacts(user_id: str) -> list[dict[str, Any]]:
    """List artifacts through the owner-scoped production read boundary."""
    owner = hash_user_id(user_id)
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT id,user_id,artifact_type,content_uri,content_hash,
                      producer_type,producer_name,producer_version,supersedes_id
               FROM derived_artifact WHERE user_id=? ORDER BY created_at""",
            (owner,),
        ).fetchall()
    keys = (
        "id",
        "user_id",
        "artifact_type",
        "content_uri",
        "content_hash",
        "producer_type",
        "producer_name",
        "producer_version",
        "supersedes_id",
    )
    return [dict(zip(keys, row)) for row in rows]


def get_artifact_lineage(user_id: str, artifact_id: str) -> dict[str, list[dict[str, Any]]]:
    """Return owner-scoped direct inputs and downstream artifacts."""
    owner = hash_user_id(user_id)
    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM derived_artifact WHERE id=? AND user_id=?", (artifact_id, owner)
        ).fetchone():
            return {"parents": [], "children": []}
        parents = conn.execute(
            """SELECT i.source_id,i.fragment_id,i.evidence_id,i.claim_id,i.artifact_parent_id
               FROM artifact_input i JOIN derived_artifact a ON a.id=i.artifact_id
               WHERE i.artifact_id=? AND a.user_id=?""",
            (artifact_id, owner),
        ).fetchall()
        children = conn.execute(
            """SELECT a.id,a.artifact_type FROM derived_artifact a
               JOIN artifact_input i ON i.artifact_id=a.id
               WHERE i.artifact_parent_id=? AND a.user_id=?""",
            (artifact_id, owner),
        ).fetchall()
    return {
        "parents": [
            dict(
                zip(
                    ("source_id", "fragment_id", "evidence_id", "claim_id", "artifact_parent_id"), r
                )
            )
            for r in parents
        ],
        "children": [dict(zip(("id", "artifact_type"), r)) for r in children],
    }


def get_artifact(user_id: str, artifact_id: str) -> dict[str, Any] | None:
    """Owner predicate is part of the SQL query (not response post-filtering)."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id,user_id,artifact_type,content_uri,content_hash,producer_type,producer_name,producer_version,model,prompt_hash,environment_hash,config,created_at,supersedes_id FROM derived_artifact WHERE id=? AND user_id=?",
            (artifact_id, hash_user_id(user_id)),
        ).fetchone()
        if not row:
            return None
        return dict(
            zip(
                (
                    "id",
                    "user_id",
                    "artifact_type",
                    "content_uri",
                    "content_hash",
                    "producer_type",
                    "producer_name",
                    "producer_version",
                    "model",
                    "prompt_hash",
                    "environment_hash",
                    "config",
                    "created_at",
                    "supersedes_id",
                ),
                row,
            )
        )
