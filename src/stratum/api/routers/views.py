"""View CRUD — user-defined knowledge views + system presets."""

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from stratum.api.deps import get_current_user
from stratum.common import generate_ulid
from stratum.db import get_conn
from stratum.utils.user_id_hash import hash_user_id

router = APIRouter(prefix="/api/v1/views", tags=["views"])

DEFAULT_PRESETS = [
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
        "description": "金融论文+量化资料",
        "icon": "📈",
        "filter_json": {
            "medium": ["paper", "book", "epub"],
            "tags": ["finance", "quant", "trading", "investment"],
        },
        "sort_by": "created_at",
        "sort_order": "desc",
        "position": 1,
    },
    {
        "name": "技术阅读",
        "description": "技术论文+文档",
        "icon": "💻",
        "filter_json": {
            "medium": ["paper", "webpage"],
            "tags": ["tech", "programming", "engineering", "ai"],
        },
        "sort_by": "created_at",
        "sort_order": "desc",
        "position": 2,
    },
    {
        "name": "中文文学",
        "description": "中文书籍+散文",
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


class ViewCreate(BaseModel):
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    filter_json: Dict[str, Any] = {}
    sort_by: str = "created_at"
    sort_order: str = "desc"
    display_mode: str = "list"
    position: int = 0


class ViewUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    filter_json: Optional[Dict[str, Any]] = None
    sort_by: Optional[str] = None
    sort_order: Optional[str] = None
    display_mode: Optional[str] = None
    position: Optional[int] = None


def _row_to_view(r) -> dict:
    # 按 SELECT 列顺序映射，filter_json 解析为 dict
    return {
        "id": r[0],
        "user_id": r[1],
        "name": r[2],
        "description": r[3],
        "is_preset": r[4],
        "icon": r[5],
        "filter_json": json.loads(r[6]) if r[6] else {},
        "sort_by": r[7],
        "sort_order": r[8],
        "display_mode": r[9],
        "position": r[10],
        "created_at": str(r[11]),
        "updated_at": str(r[12]),
    }


def _ensure_presets(user_hash: str):
    with get_conn() as conn:
        n = conn.execute(
            "SELECT COUNT(*) FROM user_saved_views WHERE user_id=? AND is_preset=TRUE", (user_hash,)
        ).fetchone()[0]
        if n > 0:
            return
        for p in DEFAULT_PRESETS:
            conn.execute(
                """
                INSERT INTO user_saved_views (id, user_id, name, description, icon, is_preset,
                    filter_json, sort_by, sort_order, display_mode, position)
                VALUES (?,?,?,?,?,TRUE,?,?,?,'list',?)
            """,
                (
                    generate_ulid(),
                    user_hash,
                    p["name"],
                    p["description"],
                    p["icon"],
                    json.dumps(p["filter_json"]),
                    p["sort_by"],
                    p["sort_order"],
                    p["position"],
                ),
            )


_COLS = "id, user_id, name, description, is_preset, icon, filter_json, sort_by, sort_order, display_mode, position, created_at, updated_at"


@router.get("")
async def list_views(user=Depends(get_current_user)):
    uh = hash_user_id(user.user_id)
    _ensure_presets(uh)
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT {_COLS} FROM user_saved_views WHERE user_id=? ORDER BY position, created_at",
            (uh,),
        ).fetchall()
    return [_row_to_view(r) for r in rows]


@router.post("", status_code=201)
async def create_view(body: ViewCreate, user=Depends(get_current_user)):
    uh = hash_user_id(user.user_id)
    vid = generate_ulid()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO user_saved_views (id, user_id, name, description, icon, is_preset,
                filter_json, sort_by, sort_order, display_mode, position)
            VALUES (?,?,?,?,?,FALSE,?,?,?,?,?)
        """,
            (
                vid,
                uh,
                body.name,
                body.description,
                body.icon,
                json.dumps(body.filter_json),
                body.sort_by,
                body.sort_order,
                body.display_mode,
                body.position,
            ),
        )
        r = conn.execute(f"SELECT {_COLS} FROM user_saved_views WHERE id=?", (vid,)).fetchone()
    return _row_to_view(r)


@router.put("/{view_id}")
async def update_view(view_id: str, body: ViewUpdate, user=Depends(get_current_user)):
    uh = hash_user_id(user.user_id)
    with get_conn() as conn:
        v = conn.execute(
            "SELECT is_preset, user_id FROM user_saved_views WHERE id=?", (view_id,)
        ).fetchone()
        if not v or v[1] != uh:
            raise HTTPException(404, "View not found")
        if v[0]:
            raise HTTPException(403, "Cannot modify preset views")
        updates = {k: val for k, val in body.model_dump().items() if val is not None}
        if "filter_json" in updates:
            updates["filter_json"] = json.dumps(updates["filter_json"])
        if updates:
            set_clause = ", ".join(f"{k}=?" for k in updates) + ", updated_at=NOW()"
            conn.execute(
                f"UPDATE user_saved_views SET {set_clause} WHERE id=?",
                (*updates.values(), view_id),
            )
        r = conn.execute(f"SELECT {_COLS} FROM user_saved_views WHERE id=?", (view_id,)).fetchone()
    return _row_to_view(r)


@router.delete("/{view_id}", status_code=204)
async def delete_view(view_id: str, user=Depends(get_current_user)):
    uh = hash_user_id(user.user_id)
    with get_conn() as conn:
        v = conn.execute(
            "SELECT is_preset, user_id FROM user_saved_views WHERE id=?", (view_id,)
        ).fetchone()
        if not v or v[1] != uh:
            raise HTTPException(404, "View not found")
        if v[0]:
            raise HTTPException(403, "Cannot delete preset views")
        conn.execute("DELETE FROM user_saved_views WHERE id=?", (view_id,))
