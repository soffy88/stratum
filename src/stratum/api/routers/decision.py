"""decision_intelligence router — semantica 能力 3O 化 API (P0)。

/decision/{action}: record / link / query_similar / trace / impact / rules / export / list
/reasoning/infer : kg_reasoning 确定性前向推理 (概念图 + 规则)
/provenance     : provenance_w3c W3C PROV-O 溯源导出
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from stratum.common import jwt_auth
from stratum.dao.decision_intelligence import (
    DecisionLedgerBackend,
    list_concept_triples,
    list_provenance,
)

router = APIRouter(prefix="/api/v1/decision", tags=["decision"])

try:
    from omodul.decision_ledger import (
        DecisionLedgerConfig, DecisionLedgerInput, decision_ledger,
    )
    from omodul.kg_reasoning import (
        KgReasoningConfig, KgReasoningInput, kg_reasoning,
    )
    from omodul.provenance_w3c import (
        ProvenanceW3cConfig, ProvenanceW3cInput, provenance_w3c,
    )

    _HAS_OMODUL = True
except ImportError:
    _HAS_OMODUL = False


class LedgerRequest(BaseModel):
    action: str
    category: str = ""
    scenario: str = ""
    reasoning: str = ""
    outcome: str = ""
    confidence: float = 0.5
    decision_maker: str = "master"
    source_refs: list[str] = Field(default_factory=list)
    src_id: str = ""
    dst_id: str = ""
    relationship_type: str = ""
    query_text: str = ""
    decision_id: str = ""
    max_results: int = 5
    max_depth: int = 3
    direction: str = "both"
    rules: list[dict] = Field(default_factory=list)
    format: str = "json"
    metadata: dict = Field(default_factory=dict)


def _require_omodul():
    if not _HAS_OMODUL:
        raise HTTPException(503, "omodul 未装配 (decision intelligence 不可用)")


@router.post("/{action}")
async def ledger(action: str, req: LedgerRequest, user_id: str = Depends(jwt_auth)):
    """决策账本: record/link/query_similar/trace/impact/rules/export/list。"""
    _require_omodul()
    req.action = action
    if req.action == "record" and not req.scenario.strip():
        raise HTTPException(400, "record 需要 scenario")
    try:
        result = decision_ledger(
            DecisionLedgerConfig(),
            DecisionLedgerInput(**req.model_dump(), backend=DecisionLedgerBackend(user_id)),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    return {"user_id": user_id, **result}


@router.post("/reasoning/infer")
async def reasoning_infer(
    rules: list[str],
    query: str = "",
    max_iterations: int = 5,
    user_id: str = Depends(jwt_auth),
):
    """确定性前向推理: 概念图 triples + 规则 → 推导 + 可解释链。"""
    _require_omodul()
    try:
        result = kg_reasoning(
            KgReasoningConfig(max_iterations=max_iterations),
            KgReasoningInput(
                facts=[],
                rules=rules,
                query=query,
                backend=_TripleSource(user_id),
            ),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    return {"user_id": user_id, **result}


class _TripleSource:
    """kg_reasoning 的 backend: 从概念图提供 triples。"""

    def __init__(self, user_id: str) -> None:
        self._uid = user_id

    def list_triples(self) -> list[list[str]]:
        return list_concept_triples(self._uid)


@router.post("/provenance/export")
async def provenance_export(
    format: str = "json",
    user_id: str = Depends(jwt_auth),
):
    """W3C PROV-O 溯源导出 (json | turtle)。"""
    _require_omodul()
    from stratum.dao.decision_intelligence import put_provenance

    # 自动聚合决策溯源: 决策 → wasAttributedTo(决策者)
    for d in DecisionLedgerBackend(user_id).list_decisions(limit=200):
        put_provenance(user_id, "wasAttributedTo", f"veya:decision:{d['decision_id']}",
                       f"veya:agent:{d['decision_maker']}",
                       {"category": d["category"], "outcome": d["outcome"]})
    rels = list_provenance(user_id)
    try:
        result = provenance_w3c(
            ProvenanceW3cConfig(),
            ProvenanceW3cInput(format=format, relations=rels),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    return {"user_id": user_id, **result}
