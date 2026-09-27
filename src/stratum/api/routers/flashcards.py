"""Flashcards (闪卡 + 间隔复习) API.

POST   /api/v1/flashcards/generate      {source_kind, source_id} → 生成并入库
GET    /api/v1/flashcards               ?due_only&limit → 列表
GET    /api/v1/flashcards/due           到期统计
POST   /api/v1/flashcards/{id}/review   {rating: again|hard|good|easy}
GET/PUT /api/v1/flashcards/settings     {desired_retention: 0.5..0.99}
DELETE /api/v1/flashcards/{id}
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from stratum.common import jwt_auth
from stratum.services import flashcard_service

router = APIRouter(prefix="/api/v1/flashcards", tags=["flashcards"])


class GenerateRequest(BaseModel):
    source_kind: str = Field(pattern="^(substrate|note)$")
    source_id: str
    max_cards: int = Field(default=12, ge=1, le=50)


class ReviewRequest(BaseModel):
    rating: str = Field(pattern="^(again|hard|good|easy)$")


class ReviewSettingsRequest(BaseModel):
    desired_retention: float = Field(default=0.9, ge=0.5, le=0.99)


@router.get("/settings")
async def get_settings(user_id: str = Depends(jwt_auth)):
    """Return the user's FSRS Desired Retention preference."""
    return flashcard_service.get_review_settings(user_id)


@router.put("/settings")
async def update_settings(body: ReviewSettingsRequest, user_id: str = Depends(jwt_auth)):
    """Persist the user's FSRS Desired Retention preference."""
    try:
        return flashcard_service.update_review_settings(user_id, body.desired_retention)
    except Exception as exc:
        raise HTTPException(503, f"Review settings unavailable: {exc}") from exc


@router.post("/generate")
async def generate(body: GenerateRequest, user_id: str = Depends(jwt_auth)):
    try:
        cards = flashcard_service.generate_cards(
            user_id, body.source_kind, body.source_id, max_cards=body.max_cards
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"generated": len(cards), "cards": cards}


@router.get("")
async def list_cards(
    due_only: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    user_id: str = Depends(jwt_auth),
):
    return flashcard_service.list_cards(user_id, due_only=due_only, limit=limit)


@router.get("/due")
async def due_stats(user_id: str = Depends(jwt_auth)):
    return flashcard_service.due_stats(user_id)


@router.post("/{card_id}/review")
async def review(card_id: str, body: ReviewRequest, user_id: str = Depends(jwt_auth)):
    card = flashcard_service.review_card(user_id, card_id, body.rating)
    if not card:
        raise HTTPException(404, "Flashcard not found")
    return card


@router.delete("/{card_id}")
async def delete(card_id: str, user_id: str = Depends(jwt_auth)):
    if not flashcard_service.delete_card(user_id, card_id):
        raise HTTPException(404, "Flashcard not found")
    return {"card_id": card_id, "status": "deleted"}
