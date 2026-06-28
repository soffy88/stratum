from fastapi import APIRouter, Body
from aii.api._dependencies import backend
from aii.api._envelope import success_response, error_response
from omodul.governance_adjudicate import governance_adjudicate, GovernanceAdjudicateConfig

router = APIRouter()

@router.get("/governance/pending")
async def governance_pending():
    # onto 模型无 quarantine 机制(ku_onto 无 is_quarantined 列) → 暂无待审 KU.
    return success_response([])

@router.post("/governance/adjudicate")
async def adjudicate(
    ku_id: str = Body(...),
    action: str = Body(...), # "approve" | "reject"
    reason: str = Body(None)
):
    try:
        config = GovernanceAdjudicateConfig(backend=backend)
        # governance_adjudicate usually expects a list of decisions or a single one
        # Here we wrap the single request into the expected omodul input format
        input_data = {
            "decisions": [
                {"ku_id": ku_id, "action": action, "reason": reason}
            ]
        }
        results = governance_adjudicate(config, input_data)
        return success_response(results)
    except Exception as e:
        return error_response("GOVERNANCE_ERROR", str(e))
