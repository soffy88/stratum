"""Internal utilities — shared embedding endpoint.

Exposes the already-loaded BGE-M3 embedder so other services (notably Stratum's
substrate_chunk vector search) can embed queries in the SAME vector space as
ingest-time embeddings. Reusing this single loaded model avoids baking a ~7GB
torch+model stack into every API image and avoids vector-space drift from a
different embedder (e.g. Ollama qwen3-embedding).
"""

from fastapi import APIRouter, Body
from aii import embedding_client

router = APIRouter()


@router.post("/internal/embed")
async def internal_embed(text: str = Body(..., embed=True)):
    """Unified embedding endpoint (bge or eg2). Returns dim matching active backend."""
    vec = embedding_client.embed_documents([text])[0]
    return {"embedding": [float(x) for x in vec], "dim": len(vec)}
