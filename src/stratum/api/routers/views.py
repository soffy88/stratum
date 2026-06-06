"""View CRUD — user_saved_views table + lazy preset seed."""

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from stratum.common import generate_ulid, jwt_auth, now_utc
from stratum.db import _conn

router = APIRouter(prefix="/api/v1/views", tags=["views"])

_DEFAULT_PRESETS = [
    {
        "name": "通用",
        "description": "默认全局检索",
        "icon": "📚",
        "filter_json": {},
        "sort_by": "updated_at",
        "sort_order": "desc",
        "position": 0,
    },
    {
        "name": "量化金融",
        "description": "金融论文 + 量化资料",
        "icon": "📈",
        "filter_json": {"medium": ["paper", "book", "epub"], "tags": ["finance", "quant", "trading", "investment"]},
        "sort_by": "created_at",
        "sort_order": "desc",
        "position": 1,
    },
    {
        "name": "技术阅读",
        "description": "技术论文 + 文档",
        "icon": "💻",
        "filter_json": {"medium": ["paper", "webpage"], "tags": ["tech", "programming", "engineering", "ai"]},
        "sort_by": "created_at",
        "sort_order": "desc",
        "position": 2,
    },
    {
        "name": "中文文学",
        "description": "中文书籍 + 散文",
        "icon": "📖",
        "filter_json": {"medium": ["book", "epub"], "language": ["zh", "zh-CN"]},
        "sort_by": "created_at",
        "sort_order": "desc",
        "position": 3,
    },
    {
        "name": "归档",
        "description": "归档/不活跃内容",
        "icon": "📦",
        "filter_json": {"tags": ["archived"]},
        "sort_by": "updated_at",
        "sort_order": "asc",
        "position": 4,
    },
]


def _seed_presets(user_id: str) -> None:
    with _conn() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM user_saved_views WHERE user_id = ? AND is_preset = TRUE",
            (user_id,),
        ).fetchone()[0]
        if count > 0:
            return
        for p in _DEFAULT_PRESETS:
            conn.execute(
                """INSERT INTO user_saved_views
                   (id, user_id, name, description, icon, is_preset,
                    filter_json, sort_by, sort_order, display_mode, position,
                    created_at, updated_at)
                   VALUES (?,?,?,?,?,TRUE,?,?,?,'list',?,NOW(),NOW())""",
                (
                    generate_ulid(), user_id, p["name"], p["description"],
                    p["icon"], json.dumps(p["filter_json"]),
                    p["sort_by"], p["sort_order"], p["position"],
                ),
            )


def _row_to_dict(row: tuple, cols: list[str]) -> dict[str, Any]:
    d = dict(zip(cols, row))
    if isinstance(d.get("filter_json"), str):
        try:
            d["filter_json"] = json.loads(d["filter_json"])
        except Exception:
            d["filter_json"] = {}
    for ts in ("created_at", "updated_at"):
        if d.get(ts) is not None:
            d[ts] = str(d[ts])
    return d


_COLS = [
    "id", "user_id", "name", "description", "icon", "is_preset",
    "filter_json", "sort_by", "sort_order", "display_mode", "position",
    "created_at", "updated_at",
]
_SEL = ", ".join(_COLS)


class ViewCreate(BaseModel):
    name: str
    description: str | None = None
    icon: str | None = None
    filter_json: dict = {}
    sort_by: str = "created_at"
    sort_order: str = "desc"
    display_mode: str = "list"
    position: int = 99


class ViewUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    icon: str | None = None
    filter_json: dict | None = None
    sort_by: str | None = None
    sort_order: str | None = None
    display_mode: str | None = None
    position: int | None = None


@router.get("")
async def list_views(user_id: str = Depends(jwt_auth)):
    _seed_presets(user_id)
    with _conn() as conn:
        rows = conn.execute(
            f"SELECT {_SEL} FROM user_saved_views WHERE user_id = ? ORDER BY position ASC, created_at ASC",
            (user_id,),
        ).fetchall()
    return [_row_to_dict(r, _COLS) for r in rows]


@router.post("", status_code=201)
async def create_view(body: ViewCreate, user_id: str = Depends(jwt_auth)):
    vid = generate_ulid()
    with _conn() as conn:
        conn.execute(
            """INSERT INTO user_saved_views
               (id, user_id, name, description, icon, is_preset,
                filter_json, sort_by, sort_order, display_mode, position,
                created_at, updated_at)
               VALUES (?,?,?,?,?,FALSE,?,?,?,?,?,NOW(),NOW())""",
            (vid, user_id, body.name, body.description, body.icon,
             json.dumps(body.filter_json), body.sort_by, body.sort_order,
             body.display_mode, body.position),
        )
        row = conn.execute(
            f"SELECT {_SEL} FROM user_saved_views WHERE id = ?", (vid,)
        ).fetchone()
    return _row_to_dict(row, _COLS)


@router.put("/{view_id}")
async def update_view(view_id: str, body: ViewUpdate, user_id: str = Depends(jwt_auth)):
    with _conn() as conn:
        existing = conn.execute(
            "SELECT is_preset, user_id FROM user_saved_views WHERE id = ?", (view_id,)
        ).fetchone()
        if not existing or existing[1] != user_id:
            raise HTTPException(404, "View not found")
        if existing[0]:
            raise HTTPException(403, "Cannot modify preset views")
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if "filter_json" in updates:
            updates["filter_json"] = json.dumps(updates["filter_json"])
        updates["updated_at"] = now_utc()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE user_saved_views SET {set_clause} WHERE id = ?",
            list(updates.values()) + [view_id],
        )
        row = conn.execute(
            f"SELECT {_SEL} FROM user_saved_views WHERE id = ?", (view_id,)
        ).fetchone()
    return _row_to_dict(row, _COLS)


@router.delete("/{view_id}", status_code=204)
async def delete_view(view_id: str, user_id: str = Depends(jwt_auth)):
    with _conn() as conn:
        existing = conn.execute(
            "SELECT is_preset, user_id FROM user_saved_views WHERE id = ?", (view_id,)
        ).fetchone()
        if not existing or existing[1] != user_id:
            raise HTTPException(404, "View not found")
        if existing[0]:
            raise HTTPException(403, "Cannot delete preset views")
        conn.execute("DELETE FROM user_saved_views WHERE id = ?", (view_id,))
