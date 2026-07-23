"""Substrate CRUD — documents listing with view integration."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from stratum.api.deps import get_current_user
from stratum.common import jwt_auth, now_utc
from stratum.db import get_conn, read, update
from stratum.utils.user_id_hash import hash_user_id

log = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

_MIME_TO_MEDIUM = {
    "application/pdf": "pdf",
    "application/epub+zip": "epub",
    "text/plain": "text",
    "text/markdown": "text",
    "text/html": "webpage",
}


def _mime_to_medium(mime: str) -> str:
    return _MIME_TO_MEDIUM.get(mime, "pdf")


# Same mapping as _mime_to_medium, as a SQL CASE expression — for filtering at
# the DB layer (medium isn't a stored column; meta_json.medium overrides it
# when set, same precedence as the Python-side computation in list_documents).
_MEDIUM_CASE_SQL = (
    "CASE mime "
    + " ".join(f"WHEN '{mime}' THEN '{medium}'" for mime, medium in _MIME_TO_MEDIUM.items())
    + " ELSE 'pdf' END"
)
_MEDIUM_SQL_EXPR = f"COALESCE(NULLIF(meta_json->>'medium', ''), {_MEDIUM_CASE_SQL})"


@router.get("")
async def list_documents(
    view_id: Optional[str] = None,
    view: Optional[str] = None,
    medium: Optional[List[str]] = Query(None),
    tags: Optional[List[str]] = Query(None),
    tag_exclude: Optional[List[str]] = Query(None),
    sort_by: str = "created_at",
    sort_order: str = "desc",
    limit: int = 50,
    offset: int = 0,
    q: Optional[str] = None,
    kind: Optional[str] = None,
    user=Depends(get_current_user),
):
    uh = hash_user_id(user.user_id)
    # Accept both view_id (backend) and view (frontend)
    effective_view_id = view_id or view

    if effective_view_id:
        with get_conn() as conn:
            v = conn.execute(
                "SELECT filter_json, sort_by, sort_order FROM user_saved_views WHERE id=? AND user_id=?",
                (effective_view_id, uh),
            ).fetchone()
            if v:
                vf = json.loads(v[0]) if v[0] else {}
                medium = vf.get("medium") or medium
                tags = vf.get("tags") or tags
                tag_exclude = vf.get("tag_exclude") or tag_exclude
                sort_by = v[1] or sort_by
                sort_order = v[2] or sort_order

    # user_id: support both hashed format and raw format (backward compat)
    base_cond = "user_id = ? OR user_id = ?"
    params: list = [uh, user.user_id]

    filters = f"({base_cond})"

    if q:
        filters += " AND title ILIKE ?"
        params.append(f"%{q}%")

    if kind:
        filters += " AND id IN (SELECT substrate_id FROM derivative WHERE kind = ?)"
        params.append(kind)

    if medium:
        filters += f" AND {_MEDIUM_SQL_EXPR} = ANY(?)"
        params.append(list(medium))

    # tags/tag_exclude: accepted (frontend + saved-view filters already send
    # them) but there is no tags storage anywhere in substrates.meta_json today
    # (verified against real data) — silently filtering on a non-existent field
    # would just return zero results, which is worse than doing nothing. Left
    # unimplemented on purpose until a real tags data model exists.

    # Count total
    with get_conn() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM substrates WHERE {filters}", params).fetchone()[
            0
        ]

        data_params = params + [limit, offset]
        cursor = conn.execute(
            f"SELECT id, user_id, title, mime, source_path, file_hash, "
            f"byte_size, page_count, language, is_pinned, created_at, updated_at, meta_json, parse_quality "
            f"FROM substrates WHERE {filters} "
            f"ORDER BY {sort_by} {sort_order} LIMIT ? OFFSET ?",
            data_params,
        )
        rows = cursor.fetchall()
        col_names = [d[0] for d in cursor.description]

    items = []
    for row in rows:
        d = dict(zip(col_names, row))
        meta = json.loads(d.get("meta_json") or "{}") if d.get("meta_json") else {}
        d["medium"] = meta.get("medium") or _mime_to_medium(d.get("mime", ""))
        raw_source = meta.get("source_type") or meta.get("source")
        d["source"] = raw_source if isinstance(raw_source, str) else "upload"
        items.append(d)

    return {"items": items, "total": total}


@router.get("/{substrate_id}")
async def get_document(substrate_id: str, user=Depends(get_current_user)):
    uh = hash_user_id(user.user_id)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, title, mime, byte_size, page_count, language, "
            "is_pinned, created_at, meta_json, source_path "
            "FROM substrates WHERE id=? AND (user_id=? OR user_id=?)",
            (substrate_id, uh, user.user_id),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Document not found")
    meta = json.loads(row[8] or "{}") if row[8] else {}
    return {
        "id": row[0],
        "title": row[1],
        "mime": row[2] or "",
        "byte_size": row[3],
        "page_count": row[4],
        "language": row[5],
        "is_pinned": bool(row[6]),
        "created_at": str(row[7]),
        "medium": meta.get("medium") or _mime_to_medium(row[2] or ""),
        "source": (lambda s: s if isinstance(s, str) else "upload")(
            meta.get("source_type") or meta.get("source")
        ),
        "source_path": row[9],
    }


@router.get("/{substrate_id}/file")
async def get_document_file(substrate_id: str, user=Depends(get_current_user)):
    uh = hash_user_id(user.user_id)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT source_path, title, mime FROM substrates "
            "WHERE id=? AND (user_id=? OR user_id=?)",
            (substrate_id, uh, user.user_id),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Document not found")
    file_path, title, mime = row
    if not file_path:
        raise HTTPException(404, "File path not found in database")
    p = Path(file_path)
    if not p.exists():
        log.error(f"File not found on disk: {file_path}")
        raise HTTPException(404, "File not found on disk")
    return FileResponse(
        path=str(p),
        media_type=mime or "application/octet-stream",
        filename=title,
        headers={"Content-Disposition": "inline"},
    )


async def _run_generate(substrate_id: str, user_id_hash: str, kind: str):
    log.info("generate_derivative: %s kind=%s", substrate_id, kind)
    try:
        if kind == "translation":
            from oskill.translate_substrate import translate_substrate

            await translate_substrate(
                substrate_id=substrate_id,
                target_lang="zh-CN",
                embed_translation=False,
                overwrite=True,
            )
            # translate_substrate writes kind='translation_zh-CN'; normalize for UI
            with get_conn() as conn:
                conn.execute(
                    "UPDATE derivative SET kind='translation' "
                    "WHERE substrate_id=? AND kind='translation_zh-CN'",
                    (substrate_id,),
                )
            log.info("generate_derivative: translation done %s", substrate_id)
        else:
            log.info("generate_derivative: kind=%s not yet wired for %s", kind, substrate_id)
    except Exception as e:
        log.error("generate_derivative error: kind=%s %s: %s", kind, substrate_id, e)


@router.post("/{substrate_id}/generate", status_code=202)
async def generate_derivative(
    substrate_id: str,
    body: dict,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(jwt_auth),
):
    uh = hash_user_id(user_id)
    kind = body.get("kind", "markdown")
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, source_path FROM substrates WHERE id=? AND user_id=?",
            (substrate_id, uh),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Document not found")
    background_tasks.add_task(_run_generate, substrate_id, uh, kind)
    return {"task_id": substrate_id, "kind": kind, "status": "queued"}


@router.get("/{substrate_id}/derivatives")
async def get_derivatives(substrate_id: str, user=Depends(get_current_user)):
    uh = hash_user_id(user.user_id)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT d.kind, d.content FROM derivative d "
            "JOIN substrates s ON d.substrate_id = s.id "
            "WHERE d.substrate_id = ? AND (s.user_id=? OR s.user_id=?) "
            "ORDER BY d.seq, d.created_at",
            (substrate_id, uh, user.user_id),
        ).fetchall()
    return [{"kind": r[0], "content": r[1]} for r in rows]


@router.post("/{substrate_id}/pin")
async def pin_substrate(substrate_id: str, user=Depends(get_current_user)):
    uh = hash_user_id(user.user_id)
    sub = read("substrates", substrate_id)
    if not sub or sub.get("user_id") != uh:
        raise HTTPException(404, "Substrate not found")
    update("substrates", substrate_id, {"is_pinned": True, "pinned_at": now_utc()})
    from stratum.changefeed import emit_event

    await emit_event(uh, "substrate_pin", {"substrate_id": substrate_id})
    return {"substrate_id": substrate_id, "status": "pinned"}


@router.post("/{substrate_id}/unpin")
async def unpin_substrate(substrate_id: str, user=Depends(get_current_user)):
    uh = hash_user_id(user.user_id)
    sub = read("substrates", substrate_id)
    if not sub or sub.get("user_id") != uh:
        raise HTTPException(404, "Substrate not found")
    update("substrates", substrate_id, {"is_pinned": False, "pinned_at": None})
    from stratum.changefeed import emit_event

    await emit_event(uh, "substrate_unpin", {"substrate_id": substrate_id})
    return {"substrate_id": substrate_id, "status": "unpinned"}
