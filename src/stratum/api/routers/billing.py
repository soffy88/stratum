"""Subscription billing — WeChat Pay + Stripe stubs."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from stratum.common import generate_ulid, jwt_auth, now_utc
from stratum.config import BASE_URL, PRICES
from stratum.db import insert, read, update

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])

# Optional payment integrations
try:
    from oprim.wechat import payment_wechat  # type: ignore[import]

    _HAS_WECHAT = True
except ImportError:
    _HAS_WECHAT = False

try:
    from oprim.stripe import create_payment_intent as stripe_pi  # type: ignore[import]

    _HAS_STRIPE = True
except ImportError:
    _HAS_STRIPE = False


class SubscribeRequest(BaseModel):
    tier: str  # "plus" | "pro"
    plan: str  # "monthly" | "yearly"
    provider: str  # "wechat" | "stripe"


@router.post("/subscribe")
async def subscribe(body: SubscribeRequest, user_id: str = Depends(jwt_auth)):
    if body.tier not in PRICES or body.plan not in PRICES[body.tier]:
        raise HTTPException(400, f"Unknown tier/plan: {body.tier}/{body.plan}")
    amount = PRICES[body.tier][body.plan]
    order_id = generate_ulid()

    if body.provider == "wechat":
        if not _HAS_WECHAT:
            raise HTTPException(501, "WeChat Pay not configured")
        payment = await payment_wechat(
            action="create_order",
            order_id=order_id,
            amount_yuan=amount,
            description=f"Stratum {body.tier.upper()} {body.plan}",
            notify_url=f"{BASE_URL}/api/v1/billing/callback/wechat",
        )
        pay_url = getattr(payment, "pay_url", "")
    elif body.provider == "stripe":
        if not _HAS_STRIPE:
            raise HTTPException(501, "Stripe not configured")
        pi = await stripe_pi(amount=amount * 100, currency="cny")
        pay_url = getattr(pi, "client_secret", "")
    else:
        raise HTTPException(400, f"Unsupported provider: {body.provider}")

    insert(
        "subscriptions",
        {
            "id": order_id,
            "user_id": user_id,
            "tier": body.tier,
            "plan": body.plan,
            "status": "pending",
            "started_at": now_utc(),
            "payment_provider": body.provider,
            "payment_ref": pay_url,
        },
    )
    return {"order_id": order_id, "payment_url": pay_url}


@router.post("/callback/wechat")
async def wechat_callback(request: Request):
    if not _HAS_WECHAT:
        return {"return_code": "FAIL"}
    body = await request.body()
    result = await payment_wechat(action="verify_notify", raw_body=body)
    if getattr(result, "status", "") == "success":
        order_id = getattr(result, "order_id", "")
        update("subscriptions", order_id, {"status": "active"})
    return {"return_code": "SUCCESS", "return_msg": "OK"}


@router.get("/subscription")
async def subscription_status(user_id: str = Depends(jwt_auth)):
    return read("subscriptions", user_id, id_column="user_id") or {"tier": "free"}
