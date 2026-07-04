"""Subscription billing — Stripe (real SDK) + WeChat Pay (stub, unchanged).

Stripe: uses the official `stripe` package (already in the image) via Checkout
Sessions — one hosted payment URL, matching what /subscribe already promises
callers. Code-complete; needs STRATUM_STRIPE_SECRET / STRATUM_STRIPE_WEBHOOK_SECRET
(currently REPLACE_ME_* placeholders) to actually process a real payment.

WeChat Pay is left as the pre-existing oprim.wechat-backed stub (still returns
501 — that integration needs a real WeChat merchant account + oprim.wechat,
neither of which exist yet; out of scope here).
"""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from stratum.common import generate_ulid, jwt_auth, now_utc
from stratum.config import BASE_URL, PRICES, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET
from stratum.db import insert, read, update

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


def get_active_tier(user_id: str) -> str:
    """Return the caller's active paid tier, or "free" if none/expired/cancelled.

    Used for feature gating (see stratum.api.routers.folder_watch / scheduled_jobs).
    """
    sub = read("subscriptions", user_id, id_column="user_id")
    if not sub or sub.get("status") != "active":
        return "free"
    return sub.get("tier", "free")


# Optional payment integrations
try:
    from oprim.wechat import payment_wechat  # type: ignore[import]

    _HAS_WECHAT = True
except ImportError:
    _HAS_WECHAT = False

try:
    import stripe as _stripe

    _HAS_STRIPE = bool(STRIPE_SECRET_KEY) and not STRIPE_SECRET_KEY.startswith("REPLACE_ME")
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
            raise HTTPException(501, "Stripe not configured — set STRATUM_STRIPE_SECRET")
        _stripe.api_key = STRIPE_SECRET_KEY
        interval = "year" if body.plan == "yearly" else "month"
        session = await asyncio.to_thread(
            _stripe.checkout.Session.create,
            mode="subscription",
            client_reference_id=order_id,
            metadata={
                "order_id": order_id,
                "user_id": user_id,
                "tier": body.tier,
                "plan": body.plan,
            },
            line_items=[
                {
                    "price_data": {
                        "currency": "cny",
                        "unit_amount": amount * 100,
                        "recurring": {"interval": interval},
                        "product_data": {"name": f"Stratum {body.tier.upper()} ({body.plan})"},
                    },
                    "quantity": 1,
                }
            ],
            success_url=f"{BASE_URL}/settings?billing=success&order_id={order_id}",
            cancel_url=f"{BASE_URL}/settings?billing=cancelled",
        )
        pay_url = session.url
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


@router.post("/callback/stripe")
async def stripe_callback(request: Request):
    """Stripe webhook — verifies signature via STRATUM_STRIPE_WEBHOOK_SECRET.

    Handles checkout.session.completed (activate) and customer.subscription.deleted
    (cancel). Returns 400 on bad signature so Stripe's retry logic kicks in
    correctly instead of silently dropping events.
    """
    if not _HAS_STRIPE:
        raise HTTPException(501, "Stripe not configured")
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = _stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except (ValueError, _stripe.error.SignatureVerificationError) as e:
        raise HTTPException(400, f"Invalid webhook signature: {e}")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        order_id = session.get("client_reference_id") or session.get("metadata", {}).get("order_id")
        if order_id:
            update(
                "subscriptions",
                order_id,
                {
                    "status": "active",
                    "payment_ref": session.get("subscription") or session.get("id"),
                },
            )
    elif event["type"] in ("customer.subscription.deleted", "customer.subscription.canceled"):
        sub_ref = event["data"]["object"].get("id")
        if sub_ref:
            from stratum.db import query

            rows = query(
                "SELECT id FROM subscriptions WHERE payment_ref = $ref LIMIT 1",
                {"ref": sub_ref},
            )
            if rows:
                update(
                    "subscriptions",
                    rows[0]["id"],
                    {"status": "cancelled", "cancelled_at": now_utc()},
                )

    return {"status": "ok"}


@router.get("/subscription")
async def subscription_status(user_id: str = Depends(jwt_auth)):
    return read("subscriptions", user_id, id_column="user_id") or {"tier": "free"}
