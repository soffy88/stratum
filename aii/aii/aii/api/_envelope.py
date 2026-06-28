from typing import Any, Optional
from pydantic import BaseModel

class ResponseEnvelope(BaseModel):
    status: str = "ok"
    data: Optional[Any] = None
    error: Optional[dict[str, Any]] = None

def success_response(data: Any = None) -> dict[str, Any]:
    return ResponseEnvelope(status="ok", data=data).model_dump(exclude_none=True)

def error_response(code: str, message: str) -> dict[str, Any]:
    return ResponseEnvelope(
        status="error", 
        error={"code": code, "message": message}
    ).model_dump(exclude_none=True)
