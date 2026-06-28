"""Feedback submission route."""

import os
from typing import Optional

import duckdb
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ...auth.jwt_handler import decode_access
from ...dao.feedback import FeedbackDAO

router = APIRouter()


def get_db():
    from stratum.db import get_conn
    with get_conn() as conn:
        yield conn


class FeedbackRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    page_url: Optional[str] = None


@router.post("/feedback")
async def submit_feedback(req: FeedbackRequest, request: Request, db=Depends(get_db)):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing Authorization header")
    try:
        payload = decode_access(auth.split(" ")[1])
        user_id = payload["sub"]
    except Exception:
        raise HTTPException(401, "Invalid token")
    FeedbackDAO(db).create_feedback(user_id=user_id, content=req.content, page_url=req.page_url)
    return {"status": "received"}
