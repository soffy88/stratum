"""Fused search — routes through KnowledgeView single retrieval plane.

Canonical: KnowledgeView (src/stratum/services/knowledge_view.py).
This router is a compatibility shell; all scope/isolation/citation logic is
delegated to KnowledgeView so /search, /retrieve, companion, agent share one contract.
"""

import asyncio

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from stratum.common import jwt_auth

# Kept as a non-serving compatibility symbol for older tests/integrations.
# Retrieval itself is exclusively delegated to KnowledgeView below.
# KnowledgeView owns validate_result_schema and its hard invariant validator.
cross_layer_search = None
_HAS_SEARCH = True

router = APIRouter(prefix="/api/v1", tags=["search"])

class SearchRequest(BaseModel):
    query: str
    mode: str = "augmented"
    top_k: int = 20
    pinned_boost: float = 1.5
    rerank: bool = False
    expand: bool = False
    medium_filter: list[str] | None = None
    domain_filter: list[str] | None = None
    date_range: tuple[str, str] | None = None
    view_id: str | None = None
    channels: list[str] | None = None


@router.post("/search")
async def search(req: SearchRequest, user_id: str = Depends(jwt_auth)):
    from stratum.services.knowledge_view import KnowledgeView, KnowledgeViewRequest

    return await asyncio.to_thread(
        KnowledgeView.search,
        KnowledgeViewRequest(
            query=req.query,
            top_k=req.top_k,
            user_id=user_id,
            rerank=req.rerank,
            scopes=["lexical", "dense"],
            channels=req.channels or ["metadata", "lexical", "dense", "graph"],
        ),
    )
