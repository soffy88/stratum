"""Internal utilities — shared embedding endpoint.

Exposes the already-loaded BGE-M3 embedder so other services (notably Stratum's
substrate_chunk vector search) can embed queries in the SAME vector space as
ingest-time embeddings. Reusing this single loaded model avoids baking a ~7GB
torch+model stack into every API image and avoids vector-space drift from a
different embedder (e.g. Ollama qwen3-embedding).

Security (infra-audit 2026-10-17): /internal/embed is auth-exempt, so it is
restricted to loopback / private-network callers. Requests that arrived through
a public tunnel (Cf-Connecting-Ip / X-Forwarded-For carrying a public address)
are rejected.
"""

import ipaddress

from fastapi import APIRouter, Body, HTTPException, Request
from aii import embedding_client

router = APIRouter()


def _is_private(addr: str | None) -> bool:
    if not addr:
        return False
    try:
        ip = ipaddress.ip_address(addr.strip())
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private


def _caller_allowed(request: Request) -> bool:
    if request.headers.get("cf-connecting-ip") or request.headers.get("cf-ray"):
        return False
    for hop in (request.headers.get("x-forwarded-for") or "").split(","):
        if hop.strip() and not _is_private(hop):
            return False
    client = request.client.host if request.client else None
    return _is_private(client)


@router.post("/internal/embed")
async def internal_embed(request: Request, text: str = Body(..., embed=True)):
    """Unified embedding endpoint (bge or eg2). Returns dim matching active backend."""
    if not _caller_allowed(request):
        raise HTTPException(status_code=403, detail="internal endpoint")
    vec = embedding_client.embed_documents([text])[0]
    return {"embedding": [float(x) for x in vec], "dim": len(vec)}
