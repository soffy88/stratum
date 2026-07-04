from fastapi import APIRouter, Body
from aii.api._dependencies import backend
from aii.api._envelope import success_response, error_response
from omodul.governance_adjudicate import governance_adjudicate, GovernanceAdjudicateConfig

router = APIRouter()


@router.get("/governance/pending")
async def governance_pending():
    kus = await backend.list_quarantined_kus()
    return success_response(kus)


@router.post("/governance/quarantine")
async def quarantine(ku_id: str = Body(..., embed=True), reason: str = Body(..., embed=True)):
    try:
        await backend.quarantine_ku(ku_id, reason)
        return success_response({"ku_id": ku_id, "is_quarantined": True})
    except ValueError as e:
        return error_response("KU_NOT_FOUND", str(e))


@router.post("/governance/unquarantine")
async def unquarantine(ku_id: str = Body(..., embed=True), reason: str = Body(..., embed=True)):
    try:
        await backend.unquarantine_ku(ku_id, reason)
        return success_response({"ku_id": ku_id, "is_quarantined": False})
    except ValueError as e:
        return error_response("KU_NOT_FOUND", str(e))


@router.get("/governance/contradictions")
async def contradictions_pending():
    rows = await backend.list_pending_contradictions()
    return success_response(rows)


@router.post("/governance/contradictions/{contradiction_id}/resolve")
async def contradictions_resolve(
    contradiction_id: int,
    action: str = Body(..., embed=True),  # keep_a | keep_b | keep_both | dismiss
    note: str = Body(None, embed=True),
):
    try:
        result = await backend.resolve_contradiction(contradiction_id, action, note)
        return success_response(result)
    except ValueError as e:
        return error_response("CONTRADICTION_RESOLVE_ERROR", str(e))


@router.post("/governance/reingest/{substrate_id}")
async def reingest_substrate(substrate_id: str, reason: str = Body(..., embed=True)):
    """Retire a substrate's current KUs (supersede_ku, history preserved) and
    clear its ingested_substrate row so the flywheel re-extracts it fresh."""
    result = await backend.reingest_substrate(substrate_id, reason)
    return success_response(result)


@router.post("/governance/adjudicate")
async def adjudicate(
    ku_id: str = Body(...),
    action: str = Body(...),  # "approve" | "reject"
    reason: str = Body(None),
):
    try:
        config = GovernanceAdjudicateConfig(backend=backend)
        # governance_adjudicate usually expects a list of decisions or a single one
        # Here we wrap the single request into the expected omodul input format
        input_data = {"decisions": [{"ku_id": ku_id, "action": action, "reason": reason}]}
        results = governance_adjudicate(config, input_data)
        return success_response(results)
    except Exception as e:
        return error_response("GOVERNANCE_ERROR", str(e))
