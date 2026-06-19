# src/stratum/api/routers/channels.py
import json
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from pydantic import BaseModel

from stratum.common import jwt_auth, generate_ulid
from stratum.utils.user_id_hash import hash_user_id
from stratum.db import get_conn
from stratum.services.channel_watcher_service import _run_first_check

router = APIRouter()

class SubscribeRequest(BaseModel):
    channel_url: str
    after_date: str | None = None
    limit: int | None = None
    min_duration_min: float | None = None    # 分钟（转秒存）
    max_duration_min: float | None = None
    title_include: list[str] = []
    title_exclude: list[str] = []
    llm_filter: str | None = None
    incremental: bool = True

@router.post("/api/v1/channels/subscribe", status_code=202)
async def subscribe(
    body: SubscribeRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(jwt_auth),
):
    uh = hash_user_id(user_id)
    sub_id = generate_ulid()
    rules = {
        "after_date": body.after_date,
        "limit": body.limit,
        "min_duration": (body.min_duration_min or 0)*60 or None,
        "max_duration": (body.max_duration_min or 0)*60 or None,
        "title_include": body.title_include,
        "title_exclude": body.title_exclude,
        "llm_filter": body.llm_filter,
    }
    
    # 获取频道标题以作展示（默认为 URL，后续扫描可能会被更新）
    channel_title = body.channel_url.split('/')[-1] or "YouTube Channel"

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO channel_subscriptions (id, user_id, channel_url, channel_title, rules_json, status) "
            "VALUES (?, ?, ?, ?, ?, 'active')",
            (sub_id, uh, body.channel_url, channel_title, json.dumps(rules))
        )
        
    # 立即跑一次首次扫描（后台异步）
    background_tasks.add_task(_run_first_check, sub_id, uh, body.channel_url, rules)
    return {"status": "subscribed", "subscription_id": sub_id}

@router.get("/api/v1/channels")
async def list_channels(user_id: str = Depends(jwt_auth)):
    uh = hash_user_id(user_id)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, channel_url, channel_title, status, scan_status, last_check, "
            "found_count, ingested_count, current_video FROM channel_subscriptions "
            "WHERE user_id = ? ORDER BY created_at DESC", (uh,)
        ).fetchall()
    return [{
        "id": r[0],
        "channel_url": r[1],
        "channel_title": r[2],
        "status": r[3],
        "scan_status": r[4],
        "last_check": str(r[5]) if r[5] else None,
        "found_count": r[6],
        "ingested_count": r[7],
        "current_video": r[8]
    } for r in rows]

@router.delete("/api/v1/channels/{sub_id}", status_code=204)
async def unsubscribe(sub_id: str, user_id: str = Depends(jwt_auth)):
    uh = hash_user_id(user_id)
    with get_conn() as conn:
        conn.execute("DELETE FROM channel_subscriptions WHERE id = ? AND user_id = ?", (sub_id, uh))

@router.patch("/api/v1/channels/{sub_id}")
async def toggle_channel(sub_id: str, body: dict, user_id: str = Depends(jwt_auth)):
    uh = hash_user_id(user_id)
    status = body.get("status")  # active | paused
    if status not in ("active", "paused"):
        raise HTTPException(status_code=400, detail="Invalid status. Must be 'active' or 'paused'.")
    with get_conn() as conn:
        conn.execute("UPDATE channel_subscriptions SET status = ? WHERE id = ? AND user_id = ?",
                     (status, sub_id, uh))
    return {"ok": True}
