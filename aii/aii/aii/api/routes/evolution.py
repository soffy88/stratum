import json
from fastapi import APIRouter, Query
from aii.api._dependencies import backend
from aii.api._envelope import success_response, error_response
from aii.service.evolution_engine import EvolutionEngine

router = APIRouter()

@router.post("/evolution/run")
async def evolution_run():
    engine = EvolutionEngine(backend=backend)
    try:
        report = await engine.evolve()
        return success_response(report)
    except Exception as e:
        return error_response("EVOLUTION_ERROR", str(e))

@router.get("/evolution/log")
async def evolution_log(limit: int = Query(50)):
    pool = await backend._ensure_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM aii.ku_state_history ORDER BY created_at DESC LIMIT $1",
            limit
        )
        logs = []
        for r in rows:
            logs.append({
                "id": r["id"],
                "ku_id": str(r["ku_id"]),
                "from_grade": r["from_grade"],
                "to_grade": r["to_grade"],
                "trigger": r["trigger"],
                "decision_trail": json.loads(r["decision_trail"]) if r["decision_trail"] else {},
                "created_at": r["created_at"].isoformat()
            })
    return success_response(logs)
