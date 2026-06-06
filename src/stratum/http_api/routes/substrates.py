"""Substrate routes: list, get by id, get derivatives."""

import os
from typing import Optional
from datetime import datetime

import duckdb
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ...dao.substrate import SubstrateDAO
from ...dao.derivative import DerivativeDAO

router = APIRouter()


def get_db():
    conn = duckdb.connect(os.path.expanduser("~/.stratum/meta.duckdb"))
    try:
        yield conn
    finally:
        conn.close()


class SubstrateItem(BaseModel):
    id: str
    title: Optional[str] = None
    mime: Optional[str] = None
    language: Optional[str] = None
    page_count: Optional[int] = None
    created_at: Optional[datetime] = None


class ListSubstratesResponse(BaseModel):
    items: list[SubstrateItem]
    total: int


class DerivativeItem(BaseModel):
    id: str
    kind: str
    seq: int
    content: str


@router.get("/substrates", response_model=ListSubstratesResponse)
async def list_substrates(
    request: Request,
    medium: Optional[str] = None,
    view_id: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    limit: int = 50,
    db=Depends(get_db),
):
    import json as _json
    user_id = request.state.user_id

    view_filter = None
    if view_id:
        from stratum.utils.user_id_hash import hash_user_id
        uid_hash = hash_user_id(user_id)
        row = db.execute(
            "SELECT filter_json, sort_by, sort_order FROM user_saved_views WHERE id = ? AND user_id = ?",
            (view_id, uid_hash),
        ).fetchone()
        if row:
            try:
                view_filter = _json.loads(row[0]) if isinstance(row[0], str) else (row[0] or {})
            except Exception:
                view_filter = {}
            sort_by = row[1] or sort_by
            sort_order = row[2] or sort_order

    subs = SubstrateDAO(db).list_substrates(
        user_id=user_id,
        medium=medium,
        limit=limit,
        view_filter=view_filter,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    items = [
        SubstrateItem(
            id=s.id, title=s.title, mime=s.mime,
            language=s.language, page_count=s.page_count, created_at=s.created_at,
        )
        for s in subs
    ]
    return ListSubstratesResponse(items=items, total=len(items))


@router.get("/substrates/{substrate_id}", response_model=SubstrateItem)
async def get_substrate(substrate_id: str, request: Request, db=Depends(get_db)):
    user_id = request.state.user_id
    s = SubstrateDAO(db).get_substrate(substrate_id=substrate_id, user_id=user_id)
    if not s:
        raise HTTPException(404, "Substrate not found")
    return SubstrateItem(
        id=s.id,
        title=s.title,
        mime=s.mime,
        language=s.language,
        page_count=s.page_count,
        created_at=s.created_at,
    )


@router.get("/substrates/{substrate_id}/derivatives")
async def get_derivatives(substrate_id: str, request: Request, db=Depends(get_db)):
    user_id = request.state.user_id
    corpus_id = request.state.corpus_id  # derivative table still uses corpus_id
    s = SubstrateDAO(db).get_substrate(substrate_id=substrate_id, user_id=user_id)
    if not s:
        raise HTTPException(404, "Substrate not found")
    derivs = DerivativeDAO(db).list_by_substrate(substrate_id=substrate_id, corpus_id=corpus_id)
    return {
        "items": [
            DerivativeItem(id=d.id, kind=d.kind, seq=d.seq, content=d.content) for d in derivs
        ]
    }
