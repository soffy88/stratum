from fastapi import Request, Header, HTTPException, Depends
from .jwt_handler import decode_access
from .exceptions import AuthError

async def get_current_user_data(authorization: str | None = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split(" ")[1]
    try:
        payload = decode_access(token)
        return payload
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
