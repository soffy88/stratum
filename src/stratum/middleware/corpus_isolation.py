"""Corpus isolation middleware — injects corpus_id from JWT into request.state."""

from fastapi import Request
from fastapi.responses import JSONResponse
from stratum.auth.jwt_handler import decode_access


async def corpus_isolation_middleware(request: Request, call_next):
    """Ensure corpus_id is injected into request.state based on authenticated user."""
    path = request.url.path
    # Exempt paths
    if (
        path.startswith("/api/auth/")
        or path.startswith("/share/")
        or path.startswith("/api/users/by-username/")
        or path in ("/health", "/openapi.json", "/docs", "/redoc")
    ):
        return await call_next(request)

    if path.startswith("/api/"):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401, content={"detail": "Missing or invalid Authorization header"}
            )

        token = auth_header.split(" ")[1]
        try:
            payload = decode_access(token)
            request.state.user_id = payload.get("sub")
            request.state.corpus_id = payload.get("corpus_id")
        except Exception as e:
            return JSONResponse(status_code=401, content={"detail": str(e)})

    return await call_next(request)
