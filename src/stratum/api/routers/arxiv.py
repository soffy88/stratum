import json
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from pydantic import BaseModel

from stratum.common import jwt_auth, generate_ulid
from stratum.utils.user_id_hash import hash_user_id
from stratum.db import get_conn
from stratum.services.arxiv_watcher_service import _run_first_check

router = APIRouter()


class ArxivSubscribeRequest(BaseModel):
    name: str | None = None
    categories: list[str] = []
    keywords: str | None = None
    author: str | None = None
    after_date: str | None = None
    max_results: int = 10
    llm_filter: str | None = None


@router.post("/api/v1/arxiv/subscribe", status_code=202)
async def arxiv_subscribe(
    body: ArxivSubscribeRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(jwt_auth),
):
    if not body.categories and not body.keywords and not body.author:
        raise HTTPException(400, "至少填 categories、keywords 或 author 之一")
    uh = hash_user_id(user_id)
    sub_id = generate_ulid()
    name = body.name or (", ".join(body.categories) or body.keywords or body.author or "arXiv")
    sub_cfg = {
        "name": name,
        "categories": body.categories,
        "keywords": body.keywords,
        "author": body.author,
        "after_date": body.after_date,
        "max_results": max(1, min(body.max_results, 50)),
        "llm_filter": body.llm_filter,
    }
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO arxiv_subscriptions "
            "(id, user_id, name, categories_json, keywords, author, after_date, max_results) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                sub_id, uh, name,
                json.dumps(body.categories),
                body.keywords, body.author,
                body.after_date,
                sub_cfg["max_results"],
            ),
        )
    background_tasks.add_task(_run_first_check, sub_id, uh, sub_cfg)
    return {"status": "subscribed", "subscription_id": sub_id}


@router.get("/api/v1/arxiv")
async def list_arxiv_subscriptions(user_id: str = Depends(jwt_auth)):
    uh = hash_user_id(user_id)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, categories_json, keywords, author, status, scan_status, "
            "last_check, found_count, ingested_count, current_paper "
            "FROM arxiv_subscriptions WHERE user_id=? ORDER BY created_at DESC",
            (uh,),
        ).fetchall()
    return [
        {
            "id": r[0],
            "name": r[1],
            "categories": json.loads(r[2] or "[]"),
            "keywords": r[3],
            "author": r[4],
            "status": r[5],
            "scan_status": r[6],
            "last_check": str(r[7]) if r[7] else None,
            "found_count": r[8],
            "ingested_count": r[9],
            "current_paper": r[10],
        }
        for r in rows
    ]


@router.delete("/api/v1/arxiv/{sub_id}", status_code=204)
async def delete_arxiv_subscription(sub_id: str, user_id: str = Depends(jwt_auth)):
    uh = hash_user_id(user_id)
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM arxiv_subscriptions WHERE id=? AND user_id=?", (sub_id, uh)
        )


@router.patch("/api/v1/arxiv/{sub_id}")
async def toggle_arxiv_subscription(
    sub_id: str, body: dict, user_id: str = Depends(jwt_auth)
):
    uh = hash_user_id(user_id)
    status = body.get("status")
    if status not in ("active", "paused"):
        raise HTTPException(400, "status must be 'active' or 'paused'")
    with get_conn() as conn:
        conn.execute(
            "UPDATE arxiv_subscriptions SET status=? WHERE id=? AND user_id=?",
            (status, sub_id, uh),
        )
    return {"ok": True}
