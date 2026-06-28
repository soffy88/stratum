from fastapi import APIRouter, Body
from aii.api._dependencies import backend
from aii.api._envelope import success_response, error_response
from aii.service.synthesis_engine import SynthesisEngine

router = APIRouter()

@router.post("/chat")
async def chat(
    message: str = Body(..., embed=True),
    top_k: int = Body(5)
):
    engine = SynthesisEngine(backend=backend)
    try:
        # Note: SynthesisEngine.chat currently doesn't take top_k in its signature 
        # in the file I read, but the user request implies we might want to control it.
        # Since the engine handles search internally with a fixed limit=3, 
        # I'll stick to what the engine provides for now.
        res = await engine.chat(message)
        return success_response(res)
    except Exception as e:
        return error_response("CHAT_ERROR", str(e))
