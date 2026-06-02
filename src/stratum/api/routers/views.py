"""View CRUD — user-defined knowledge views + system presets."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from stratum.changefeed import emit_event
from stratum.common import generate_ulid, jwt_auth, now_utc
from stratum.db import insert, query, read, soft_delete, update, write

router = APIRouter(prefix="/api/v1/views", tags=["views"])

PRESETS: dict[str, dict] = {
    "all": {"name": "通用", "filter": {}, "description": "默认全局检索"},
    "quant_finance": {
        "name": "量化金融",
        "filter": {"medium": ["paper", "article"], "domain": ["quant"]},
    },
    "tech_reading": {
        "name": "技术阅读",
        "filter": {"medium": ["paper"], "domain": ["tech"]},
    },
    "chinese_literature": {
        "name": "中文文学",
        "filter": {"medium": ["book"], "language": ["zh"]},
    },
    "archives": {
        "name": "归档",
        "filter": {"date_range": {"to": "2025-01-01"}},
    },
}


class ViewCreate(BaseModel):
    name: str
    description: str | None = None
    filters: dict = {}
    default_llm: dict = {}
    default_system_prompt: str | None = None


class ViewUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    filters: dict | None = None


@router.post("")
async def create_view(body: ViewCreate, user_id: str = Depends(jwt_auth)):
    vid = generate_ulid()
    insert(
        "user_views",
        {
            "id": vid,
            "user_id": user_id,
            "name": body.name,
            "description": body.description,
            "default_filter": body.filters,
            "default_llm": body.default_llm,
            "default_system_prompt": body.default_system_prompt,
            "created_at": now_utc(),
            "updated_at": now_utc(),
        },
    )
    await emit_event(user_id, "view_create", {"view_id": vid, "name": body.name})
    return {"view_id": vid}


@router.get("")
async def list_views(user_id: str = Depends(jwt_auth)):
    user_views = query(
        "SELECT * FROM user_views WHERE user_id = %(uid)s ORDER BY name",
        {"uid": user_id},
    )
    return {"presets": PRESETS, "user_views": user_views}


@router.put("/{view_id}")
async def update_view(view_id: str, body: ViewUpdate, user_id: str = Depends(jwt_auth)):
    existing = read("user_views", view_id)
    if not existing or existing.get("user_id") != user_id:
        raise HTTPException(404, "View not found")
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    if "filters" in changes:
        changes["default_filter"] = changes.pop("filters")
    if changes:
        changes["updated_at"] = now_utc()
        update("user_views", view_id, changes)
    return {"view_id": view_id, "status": "updated"}


@router.delete("/{view_id}")
async def delete_view(view_id: str, user_id: str = Depends(jwt_auth)):
    existing = read("user_views", view_id)
    if not existing or existing.get("user_id") != user_id:
        raise HTTPException(404, "View not found")
    soft_delete("user_views", view_id)
    return {"view_id": view_id, "status": "deleted"}


@router.post("/{view_id}/set-default")
async def set_default_view(view_id: str, user_id: str = Depends(jwt_auth)):
    existing = read("user_views", view_id)
    if not existing or existing.get("user_id") != user_id:
        raise HTTPException(404, "View not found")
    # Clear other defaults for this user (DuckDB: execute directly on connection)
    from stratum.db import execute

    execute("UPDATE user_views SET is_default = FALSE WHERE user_id = %(uid)s", {"uid": user_id})
    update("user_views", view_id, {"is_default": True})
    await emit_event(user_id, "view_default_changed", {"view_id": view_id})
    return {"view_id": view_id, "status": "default_set"}
