"""WebSocket push endpoint.

Auth design: tokens must NOT be passed via query string (logged by every
reverse proxy and visible in browser history). Two safe options are supported:

  1. HttpOnly cookie 'refresh_token' — already set by /api/auth/login.
     Client connects bare: new WebSocket("wss://stratum.uex.hk/ws")
     Server reads ws.cookies['access_token'] or ws.cookies['refresh_token'].

  2. Short-lived WS ticket — client calls POST /api/v1/ws/ticket (authenticated),
     receives a 30-second single-use ticket, and connects:
     new WebSocket("wss://stratum.uex.hk/ws?ticket=<ticket>")
     Ticket is NOT a long-lived JWT; it is a random token stored in DedupCache.
"""

import os
import secrets

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from stratum.common import dedup_cache, jwt_auth, verify_token

router = APIRouter()

# Allowlist for Origin header enforcement when cookie auth is used.
# Cross-origin pages can initiate WS connections and the browser will send
# cookies automatically — this is Cross-Site WebSocket Hijacking (CSWSH).
# Ticket-based auth is not vulnerable (tickets are one-time tokens obtained
# via an authenticated same-origin POST request).
_ALLOWED_ORIGINS: set[str] = {
    o.strip()
    for o in os.environ.get(
        "STRATUM_WS_ALLOWED_ORIGINS",
        "http://localhost:3000,https://stratum.uex.hk",
    ).split(",")
    if o.strip()
}

# user_id → list of open connections
active_connections: dict[str, list[WebSocket]] = {}


@router.post("/api/v1/ws/ticket")
async def issue_ws_ticket(user_id: str = Depends(jwt_auth)) -> dict:
    """Issue a 30-second single-use WebSocket ticket (avoids token-in-URL)."""
    ticket = secrets.token_urlsafe(32)
    await dedup_cache.set(f"ws_ticket:{ticket}", user_id, ttl=30)
    return {"ticket": ticket, "expires_in": 30}


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """Accept WebSocket connection authenticated via cookie or short-lived ticket.

    Auth priority:
      1. 'access_token' HttpOnly cookie (set by /api/auth/login)
      2. 'ticket' query-string parameter (30-second single-use, from /api/v1/ws/ticket)

    Long-lived JWT query parameters are explicitly rejected.
    """
    user_id: str | None = None

    # Option 1: HttpOnly cookie — only accepted from allowed origins (CSWSH guard).
    # A cross-origin page can open a WebSocket and the browser sends cookies
    # automatically; the Origin header is set by the browser and cannot be
    # spoofed from a web context, so checking it is sufficient here.
    cookie_token = ws.cookies.get("access_token") or ws.cookies.get("refresh_token")
    if cookie_token:
        origin = ws.headers.get("origin")
        if origin is None or origin not in _ALLOWED_ORIGINS:
            await ws.close(code=4403)
            return
        try:
            user_id = verify_token(f"Bearer {cookie_token}")
        except Exception:
            pass

    # Option 2: Short-lived ticket (query param)
    if not user_id:
        ticket = ws.query_params.get("ticket")
        if ticket:
            user_id = await dedup_cache.get(f"ws_ticket:{ticket}")
            if user_id:
                # Single-use: invalidate immediately
                await dedup_cache.set(f"ws_ticket:{ticket}", None, ttl=1)

    if not user_id:
        await ws.close(code=4001)
        return

    await ws.accept()
    active_connections.setdefault(user_id, []).append(ws)
    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        conns = active_connections.get(user_id, [])
        if ws in conns:
            conns.remove(ws)


async def broadcast_to_user(user_id: str, event: dict) -> None:
    """Push a changefeed event to all connected devices for this user."""
    for ws in list(active_connections.get(user_id, [])):
        try:
            await ws.send_json(event)
        except Exception:
            pass
