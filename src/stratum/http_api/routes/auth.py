from fastapi import APIRouter, Depends, HTTPException, Response, Request
from ..schemas.auth import RegisterRequest, RegisterResponse, LoginRequest, LoginResponse, UserPublic, RefreshResponse
from ...dao.users import UserDAO
from ...dao.sessions import SessionDAO
from ...auth.password import hash_password, verify_password, validate_password_strength
from ...auth.jwt_handler import encode_access, decode_access
from ...auth.refresh_handler import create_refresh
import os
import hashlib
from datetime import datetime, timezone

router = APIRouter()

def get_db():
    from stratum.db import get_conn
    with get_conn() as conn:
        yield conn

@router.post("/register", response_model=RegisterResponse)
async def register(req: RegisterRequest, db=Depends(get_db)):
    dao = UserDAO(db)
    if dao.get_user_by_email(req.email): raise HTTPException(400, "Email already registered")
    if dao.get_user_by_username(req.username): raise HTTPException(400, "Username already taken")
    try: validate_password_strength(req.password)
    except ValueError as e: raise HTTPException(400, str(e))
    user = dao.create_user(email=req.email, username=req.username, password_hash=hash_password(req.password))
    return RegisterResponse(user_id=user.id, email=user.email, username=user.username)

@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, response: Response, request: Request, db=Depends(get_db)):
    user_dao = UserDAO(db)
    user = user_dao.get_user_by_email(req.email_or_username) or user_dao.get_user_by_username(req.email_or_username)
    if not user or not verify_password(req.password, user.password_hash): raise HTTPException(401, "Invalid credentials")
    access_token = encode_access(user.email, user.corpus_id)
    token_str, refresh_hash = create_refresh(user.id, request.headers.get("user-agent"), request.client.host)
    SessionDAO(db).create_session(user_id=user.id, refresh_token_hash=refresh_hash, user_agent=request.headers.get("user-agent"), ip=request.client.host)
    response.set_cookie(key="refresh_token", value=token_str, httponly=True, secure=True, samesite="lax", max_age=30*24*3600)
    return LoginResponse(access_token=access_token, user=UserPublic(user_id=user.id, email=user.email, username=user.username, email_verified=user.email_verified, created_at=user.created_at))

@router.post("/refresh", response_model=RefreshResponse)
async def refresh(request: Request, db=Depends(get_db)):
    token_str = request.cookies.get("refresh_token")
    if not token_str: raise HTTPException(401, "Missing refresh token")
    refresh_hash = hashlib.sha256(token_str.encode()).hexdigest()
    session = SessionDAO(db).get_session_by_refresh_hash(refresh_hash)
    if not session: raise HTTPException(401, "Invalid or expired session")
    # PG returns tz-aware datetimes (timestamptz); DuckDB returned naive. Normalize
    # to naive-UTC so the comparison never mixes aware/naive (TypeError otherwise).
    expires_at = session.expires_at
    if expires_at.tzinfo is not None: expires_at = expires_at.astimezone(timezone.utc).replace(tzinfo=None)
    if expires_at < datetime.now(timezone.utc).replace(tzinfo=None): raise HTTPException(401, "Invalid or expired session")
    user = UserDAO(db).get_user_by_id(session.user_id)
    if not user: raise HTTPException(401, "User not found")
    return RefreshResponse(access_token=encode_access(user.email, user.corpus_id))

@router.post("/logout")
async def logout(request: Request, response: Response, db=Depends(get_db)):
    token_str = request.cookies.get("refresh_token")
    if token_str:
        refresh_hash = hashlib.sha256(token_str.encode()).hexdigest()
        db.execute("UPDATE sessions SET revoked_at = ? WHERE refresh_token_hash = ?", (datetime.now(timezone.utc), refresh_hash))
    response.delete_cookie("refresh_token")
    return {"status": "ok"}

@router.get("/me", response_model=UserPublic)
async def get_me(request: Request, db=Depends(get_db)):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "): raise HTTPException(401, "Invalid token")
    token = auth_header.split(" ")[1]
    try:
        payload = decode_access(token)
    except Exception:
        raise HTTPException(401, "Invalid or expired token")
    user = UserDAO(db).get_user_by_email(payload.get("sub"))
    if not user: raise HTTPException(404, "User not found")
    return UserPublic(user_id=user.id, email=user.email, username=user.username, email_verified=user.email_verified, created_at=user.created_at)
