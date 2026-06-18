from fastapi import APIRouter, Body
from aii.api._dependencies import backend
from aii.api._envelope import success_response, error_response
from oprim import vector_encode

router = APIRouter()

@router.post("/query")
async def query_ku(
    query: str = Body(...),
    top_k: int = Body(5)
):
    try:
        # 1. Encode query
        qv = vector_encode(texts=[query], provider="default")[0]
        
        # 2. Search DB (Ensure plain Python floats for asyncpg/pgvector)
        results = await backend.search_ku_by_vector([float(x) for x in qv], limit=top_k)
        
        # 3. Format output
        formatted = []
        for r in results:
            formatted.append({
                "ku_id": str(r["ku_id"]),
                "natural_text": r.get("natural_text"),
                "knowledge_type": r.get("knowledge_type"),
                "grade": r.get("grade"),
                "score": 1.0 - r.get("distance", 1.0) # Similarity score
            })
            
        return success_response(formatted)
    except Exception as e:
        return error_response("QUERY_ERROR", str(e))
