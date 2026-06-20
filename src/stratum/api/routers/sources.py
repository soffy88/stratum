import json
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from pydantic import BaseModel

from stratum.common import jwt_auth, generate_ulid
from stratum.utils.user_id_hash import hash_user_id
from stratum.db import get_conn
from stratum.services.source_watcher_service import run_first_check

router = APIRouter()

VALID_SOURCE_TYPES = {"arxiv", "gutenberg", "oapen"}


class SourceSubscribeRequest(BaseModel):
    name: str | None = None
    source_type: str
    query: dict = {}
    max_results: int = 10


@router.post("/api/v1/sources/subscribe", status_code=202)
async def source_subscribe(
    body: SourceSubscribeRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(jwt_auth),
):
    if body.source_type not in VALID_SOURCE_TYPES:
        raise HTTPException(400, f"source_type 须为 {VALID_SOURCE_TYPES!r} 之一")

    # Per-source validation
    q = body.query
    if body.source_type == "arxiv":
        cats = q.get("categories") or []
        kw = q.get("keywords") or ""
        auth = q.get("author") or ""
        if not cats and not kw.strip() and not auth.strip():
            raise HTTPException(400, "arXiv 订阅至少填 categories、keywords 或 author 之一")
    elif body.source_type == "gutenberg":
        if not q.get("topic") and not q.get("keywords") and not q.get("author"):
            raise HTTPException(400, "Gutenberg 订阅至少填 topic、keywords 或 author 之一")
    elif body.source_type == "oapen":
        if not q.get("query"):
            raise HTTPException(400, "OAPEN 订阅需填写 query（搜索词）")

    uh = hash_user_id(user_id)
    sub_id = generate_ulid()
    name = (body.name or "").strip() or _default_name(body.source_type, q)
    max_r = max(1, min(body.max_results, 50))

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO source_subscriptions "
            "(id, user_id, source_type, name, query_json, max_results) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (sub_id, uh, body.source_type, name, json.dumps(q, ensure_ascii=False), max_r),
        )

    background_tasks.add_task(
        run_first_check, sub_id, uh, body.source_type, q, max_r
    )
    return {"status": "subscribed", "subscription_id": sub_id}


def _default_name(source_type: str, q: dict) -> str:
    if source_type == "arxiv":
        cats = q.get("categories") or []
        kw = q.get("keywords") or ""
        return ", ".join(cats[:3]) or kw or "arXiv"
    if source_type == "gutenberg":
        return q.get("topic") or q.get("keywords") or "Gutenberg"
    if source_type == "oapen":
        return q.get("query") or "OAPEN"
    return source_type


@router.get("/api/v1/sources")
async def list_source_subscriptions(user_id: str = Depends(jwt_auth)):
    uh = hash_user_id(user_id)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, source_type, name, query_json, max_results, status, "
            "scan_status, last_check, found_count, ingested_count, current_item "
            "FROM source_subscriptions WHERE user_id=? ORDER BY created_at DESC",
            (uh,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(r) -> dict:
    q = json.loads(r[3] or "{}")
    return {
        "id": r[0],
        "source_type": r[1],
        "name": r[2],
        "query": q,
        "max_results": r[4],
        "status": r[5],
        "scan_status": r[6],
        "last_check": str(r[7]) if r[7] else None,
        "found_count": r[8],
        "ingested_count": r[9],
        "current_item": r[10],
    }


@router.delete("/api/v1/sources/{sub_id}", status_code=204)
async def delete_source_subscription(sub_id: str, user_id: str = Depends(jwt_auth)):
    uh = hash_user_id(user_id)
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM source_subscriptions WHERE id=? AND user_id=?", (sub_id, uh)
        )


@router.patch("/api/v1/sources/{sub_id}")
async def toggle_source_subscription(
    sub_id: str, body: dict, user_id: str = Depends(jwt_auth)
):
    uh = hash_user_id(user_id)
    status = body.get("status")
    if status not in ("active", "paused"):
        raise HTTPException(400, "status 须为 'active' 或 'paused'")
    with get_conn() as conn:
        conn.execute(
            "UPDATE source_subscriptions SET status=? WHERE id=? AND user_id=?",
            (status, sub_id, uh),
        )
    return {"ok": True}


# ── /api/v1/arxiv/* compat shim（保持旧前端可用，读 source_subscriptions）────

@router.post("/api/v1/arxiv/subscribe", status_code=202)
async def arxiv_subscribe_compat(
    body: dict,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(jwt_auth),
):
    from pydantic import ValidationError
    cats = body.get("categories") or []
    kw = body.get("keywords") or ""
    auth = body.get("author") or ""
    if not cats and not kw.strip() and not auth.strip():
        raise HTTPException(400, "至少填 categories、keywords 或 author 之一")
    q = {
        "categories": cats,
        "keywords": kw or None,
        "author": auth or None,
        "after_date": body.get("after_date"),
    }
    uh = hash_user_id(user_id)
    sub_id = generate_ulid()
    name = body.get("name") or ", ".join(cats[:3]) or kw or "arXiv"
    max_r = max(1, min(int(body.get("max_results") or 10), 50))
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO source_subscriptions "
            "(id, user_id, source_type, name, query_json, max_results) "
            "VALUES (?, ?, 'arxiv', ?, ?, ?)",
            (sub_id, uh, name, json.dumps(q, ensure_ascii=False), max_r),
        )
    background_tasks.add_task(run_first_check, sub_id, uh, "arxiv", q, max_r)
    return {"status": "subscribed", "subscription_id": sub_id}


@router.get("/api/v1/arxiv")
async def list_arxiv_compat(user_id: str = Depends(jwt_auth)):
    uh = hash_user_id(user_id)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, source_type, name, query_json, max_results, status, "
            "scan_status, last_check, found_count, ingested_count, current_item "
            "FROM source_subscriptions WHERE user_id=? AND source_type='arxiv' ORDER BY created_at DESC",
            (uh,),
        ).fetchall()
    result = []
    for r in rows:
        q = json.loads(r[3] or "{}")
        result.append({
            "id": r[0],
            "name": r[2],
            "categories": q.get("categories") or [],
            "keywords": q.get("keywords"),
            "author": q.get("author"),
            "status": r[5],
            "scan_status": r[6],
            "last_check": str(r[7]) if r[7] else None,
            "found_count": r[8],
            "ingested_count": r[9],
            "current_paper": r[10],
        })
    return result


@router.delete("/api/v1/arxiv/{sub_id}", status_code=204)
async def delete_arxiv_compat(sub_id: str, user_id: str = Depends(jwt_auth)):
    uh = hash_user_id(user_id)
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM source_subscriptions WHERE id=? AND user_id=? AND source_type='arxiv'",
            (sub_id, uh),
        )


@router.patch("/api/v1/arxiv/{sub_id}")
async def toggle_arxiv_compat(sub_id: str, body: dict, user_id: str = Depends(jwt_auth)):
    uh = hash_user_id(user_id)
    status = body.get("status")
    if status not in ("active", "paused"):
        raise HTTPException(400, "status must be 'active' or 'paused'")
    with get_conn() as conn:
        conn.execute(
            "UPDATE source_subscriptions SET status=? WHERE id=? AND user_id=? AND source_type='arxiv'",
            (status, sub_id, uh),
        )
    return {"ok": True}
