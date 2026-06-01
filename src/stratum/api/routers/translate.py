"""Translation routes."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from stratum.common import ensure_dir, jwt_auth, user_translations_dir
from stratum.db import read

router = APIRouter(prefix="/api/v1/translate", tags=["translate"])

try:
    from omodul.knowledge.agents.builtin.translation_worker import TranslationWorkerAgent
    from omodul.knowledge.agents.base import AgentContext

    _HAS_TRANSLATE = True
except ImportError:
    _HAS_TRANSLATE = False


@router.post("/substrate/{substrate_id}")
async def translate_substrate(
    substrate_id: str,
    target_lang: str = "zh",
    provider: str = "qwen3",
    user_id: str = Depends(jwt_auth),
):
    sub = read("substrates", substrate_id)
    if not sub or sub.get("user_id") != user_id:
        raise HTTPException(404, "Substrate not found")

    if not _HAS_TRANSLATE:
        return {
            "status": "not_implemented",
            "substrate_id": substrate_id,
            "message": "translation_worker agent not yet available",
        }

    out_dir = ensure_dir(user_translations_dir(user_id))
    agent = TranslationWorkerAgent()
    context = AgentContext(user_id=user_id, corpus_id=f"user_{user_id}")
    result = await asyncio.to_thread(
        asyncio.run,
        agent.run(
            {"substrate_id": substrate_id, "target_lang": target_lang, "provider": provider},
            context,
        ),
    )
    return {
        "status": "completed",
        "substrate_id": substrate_id,
        "output": result.output if hasattr(result, "output") else None,
    }


@router.get("/detect/{substrate_id}")
async def detect_language_route(substrate_id: str, user_id: str = Depends(jwt_auth)):
    sub = read("substrates", substrate_id)
    if not sub or sub.get("user_id") != user_id:
        raise HTTPException(404, "Substrate not found")
    preview = (sub.get("content_preview") or sub.get("title") or "")[:200]
    # Heuristic: if more than 20% chars are CJK → zh
    cjk = sum(1 for c in preview if "一" <= c <= "鿿")
    lang = "zh" if preview and cjk / max(len(preview), 1) > 0.2 else "en"
    return {"substrate_id": substrate_id, "detected_language": lang}
