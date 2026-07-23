"""POST /api/search — hybrid search with corpus isolation."""

import os
from typing import Optional, Literal

import duckdb
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()


def get_db():
    from stratum.db import get_conn

    with get_conn() as conn:
        yield conn


class SearchRequest(BaseModel):
    query: str
    top_k: int = 10
    mode: Literal["strict", "augmented"] = "augmented"
    rerank: bool = False
    expand: bool = False
    view_id: Optional[str] = None
    filter_medium: Optional[list[str]] = None


class SearchResultItem(BaseModel):
    id: str
    type: str
    title: str
    score: float
    highlight: Optional[str] = None


class SearchResponse(BaseModel):
    results: list[SearchResultItem]
    query_used: str


@router.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest, request: Request, db=Depends(get_db)):
    corpus_id = request.state.corpus_id
    user_id = request.state.user_id

    try:
        from stratum.service.search import stratum_search

        raw = await stratum_search(
            query=req.query,
            corpus_id=corpus_id,
            user_id=user_id,
            top_k=req.top_k,
            rerank=req.rerank,
            expand=req.expand,
            view_id=req.view_id,
            filter_medium=req.filter_medium,
        )
        results = [
            SearchResultItem(
                id=r.id, type=r.type, title=r.title, score=r.score, highlight=r.highlight
            )
            for r in raw
        ]
    except ImportError:
        # Fallback: direct DB search if oskill unavailable (uses substrates plural, user_id)
        rows = db.execute(
            "SELECT id, 'substrate' as type, title FROM substrates WHERE user_id = ? AND title ILIKE ? LIMIT ?",
            (user_id, f"%{req.query}%", req.top_k),
        ).fetchall()
        results = [SearchResultItem(id=r[0], type=r[1], title=r[2], score=1.0) for r in rows]

    return SearchResponse(results=results, query_used=req.query)
