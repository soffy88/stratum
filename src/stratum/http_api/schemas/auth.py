from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=32, pattern=r'^[a-zA-Z0-9_]+$')
    password: str = Field(..., min_length=10)
class RegisterResponse(BaseModel):
    user_id: str
    email: str
    username: str
    verify_email_sent: bool = False
class LoginRequest(BaseModel):
    email_or_username: str
    password: str
class UserPublic(BaseModel):
    user_id: str
    email: str
    username: str
    email_verified: bool
    created_at: datetime
class LoginResponse(BaseModel):
    access_token: str
    expires_in: int = 900
    user: UserPublic
class RefreshResponse(BaseModel):
    access_token: str
    expires_in: int = 900
