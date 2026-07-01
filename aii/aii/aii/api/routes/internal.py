"""Internal utilities — shared embedding endpoint.

Exposes the already-loaded BGE-M3 embedder so other services (notably Stratum's
substrate_chunk vector search) can embed queries in the SAME vector space as
ingest-time embeddings. Reusing this single loaded model avoids baking a ~7GB
torch+model stack into every API image and avoids vector-space drift from a
different embedder (e.g. Ollama qwen3-embedding).
"""
from fastapi import APIRouter, Body
from oprim import vector_encode

router = APIRouter()


@router.post("/internal/embed")
async def internal_embed(text: str = Body(..., embed=True)):
    """Return the BGE-M3 embedding (provider='default', 1024-dim) for one text."""
    vec = vector_encode(texts=[text], provider="default")[0]
    return {"embedding": [float(x) for x in vec], "dim": len(vec)}
