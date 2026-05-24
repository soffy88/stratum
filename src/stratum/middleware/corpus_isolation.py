from fastapi import Request, HTTPException
from stratum.auth.jwt_handler import decode_access
from stratum.auth.exceptions import AuthError

async def corpus_isolation_middleware(request: Request, call_next):
    """Ensure corpus_id is injected into request.state based on authenticated user."""
    path = request.url.path
    # Exempt paths
    if path.startswith("/api/auth/") or path.startswith("/share/") or path == "/health" or path == "/openapi.json":
        return await call_next(request)
    
    if path.startswith("/api/"):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        
        token = auth_header.split(" ")[1]
        try:
            payload = decode_access(token)
            request.state.user_id = payload.get("sub")
            request.state.corpus_id = payload.get("corpus_id")
        except Exception as e:
            raise HTTPException(status_code=401, detail=str(e))
            
    return await call_next(request)
