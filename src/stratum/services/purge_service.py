"""True delete (hard purge) — MVP: 删除即真删.

Cascades known child tables. Soft-delete remains available via soft=True flags
on API for recovery workflows, but default user DELETE is hard.
"""

from __future__ import annotations

import logging
from typing import Any

from stratum.db import execute, query, read
from stratum.utils.user_id_hash import hash_user_id

log = logging.getLogger(__name__)

# Child tables keyed by substrate_id (best-effort; missing tables ignored)
_SUBSTRATE_CHILDREN = (
    "derivative",
    "substrate_layers",
    "cornell_notes",
    "highlights",
)


def hard_delete_row(table: str, rid: str) -> None:
    execute(f"DELETE FROM {table} WHERE id = %(rid)s", {"rid": rid})


def purge_note(note_id: str, user_id: str) -> dict[str, Any]:
    row = read("notes_sl", note_id)
    if not row or row.get("user_id") != user_id:
        return {"status": "not_found", "note_id": note_id}
    hard_delete_row("notes_sl", note_id)
    log.info("purge_note %s user=%s", note_id, user_id[:12])
    return {"status": "purged", "note_id": note_id, "mode": "hard"}


def purge_concept(concept_id: str, user_id: str) -> dict[str, Any]:
    row = read("concepts", concept_id)
    if not row or row.get("user_id") != user_id:
        return {"status": "not_found", "concept_id": concept_id}
    hard_delete_row("concepts", concept_id)
    return {"status": "purged", "concept_id": concept_id, "mode": "hard"}


def purge_substrate(substrate_id: str, user_id: str) -> dict[str, Any]:
    """Hard-delete substrate + derivatives/layers. Ownership via user_id or hash."""
    uh = hash_user_id(user_id)
    rows = query(
        "SELECT id, user_id FROM substrates WHERE id = %(sid)s LIMIT 1",
        {"sid": substrate_id},
    )
    if not rows:
        return {"status": "not_found", "substrate_id": substrate_id}
    owner = rows[0].get("user_id")
    if owner not in (user_id, uh):
        return {"status": "forbidden", "substrate_id": substrate_id}

    deleted_children: dict[str, int] = {}
    for table in _SUBSTRATE_CHILDREN:
        try:
            before = query(
                f"SELECT count(*) AS n FROM {table} WHERE substrate_id = %(sid)s",
                {"sid": substrate_id},
            )
            n = int((before[0]["n"] if before else 0) or 0)
            if n:
                execute(
                    f"DELETE FROM {table} WHERE substrate_id = %(sid)s",
                    {"sid": substrate_id},
                )
            deleted_children[table] = n
        except Exception as e:
            log.debug("purge child %s skip: %s", table, e)
            deleted_children[table] = -1

    # directory nodes / search index best-effort
    for sql in (
        "DELETE FROM directory_nodes WHERE ref_id = %(sid)s",
        "DELETE FROM search_documents WHERE substrate_id = %(sid)s",
    ):
        try:
            execute(sql, {"sid": substrate_id})
        except Exception:
            pass

    hard_delete_row("substrates", substrate_id)
    log.info("purge_substrate %s children=%s", substrate_id, deleted_children)
    return {
        "status": "purged",
        "substrate_id": substrate_id,
        "mode": "hard",
        "children": deleted_children,
    }


def purge_user_notes_soft_marked(user_id: str, limit: int = 500) -> dict[str, Any]:
    """Permanently remove notes already soft-deleted (grace cleanup)."""
    rows = query(
        "SELECT id FROM notes_sl WHERE user_id = %(uid)s AND deleted_at IS NOT NULL "
        "ORDER BY deleted_at ASC LIMIT %(lim)s",
        {"uid": user_id, "lim": limit},
    )
    n = 0
    for r in rows:
        hard_delete_row("notes_sl", r["id"])
        n += 1
    return {"status": "ok", "purged_notes": n}
