from fastapi import APIRouter, Body
from aii.api._dependencies import backend
from aii.api._envelope import success_response, error_response
from oprim import vector_encode

router = APIRouter()

_VALID_KT = {"conceptual", "rationale", "factual", "procedural", "positional", "metacognitive"}


@router.post("/query")
async def query_ku(
    query: str = Body(...),
    top_k: int = Body(5),
    knowledge_type: "str | list[str] | None" = Body(None),  # ★按六类过滤检索维度: 单类/多类/不传
):
    try:
        # 0. 校验 knowledge_type (六类之一/多类), 非法值忽略
        kt = knowledge_type
        if isinstance(kt, str):
            kt = kt if kt in _VALID_KT else None
        elif isinstance(kt, list):
            kt = [k for k in kt if k in _VALID_KT] or None

        # 1. Encode query
        qv = vector_encode(texts=[query], provider="default")[0]

        # 2. Search DB (Ensure plain Python floats for asyncpg/pgvector)
        results = await backend.search_ku_by_vector([float(x) for x in qv], limit=top_k, knowledge_type=kt)
        
        # 3. Format output
        formatted = []
        for r in results:
            formatted.append({
                "ku_id": str(r["ku_id"]),
                "natural_text": r.get("natural_text"),
                "natural_text_zh": r.get("natural_text_zh"),
                "knowledge_type": r.get("knowledge_type"),
                "grade": r.get("grade"),
                "score": 1.0 - r.get("distance", 1.0) # Similarity score
            })
            
        return success_response(formatted)
    except Exception as e:
        return error_response("QUERY_ERROR", str(e))
