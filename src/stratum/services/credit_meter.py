"""Transparent usage-unit policy for high-compute capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


CREDIT_COSTS: dict[str, int] = {
    "deep_research": 10,
    "graph_rebuild": 10,
    "image_generation": 5,
    "tts_generation": 3,
    "large_export": 2,
}

TIER_MONTHLY_CREDITS: dict[str, int] = {
    "free": 25,
    "plus": 250,
    "pro": 1000,
}


class CreditIdempotencyConflict(ValueError):
    """Raised when a key is reused for a different credit operation."""


@dataclass(frozen=True)
class CreditDecision:
    tier: str
    capability: str
    requested: int
    allowance: int
    used: int
    remaining: int
    allowed: bool
    outcome: str = "allowed"

    def to_dict(self) -> dict:
        return {
            "tier": self.tier,
            "capability": self.capability,
            "requested": self.requested,
            "allowance": self.allowance,
            "used": self.used,
            "remaining": self.remaining,
            "allowed": self.allowed,
            "outcome": self.outcome,
        }


def period_key(now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    return current.astimezone(timezone.utc).strftime("%Y-%m")


def estimate_credits(capability: str, units: int = 1) -> int:
    if capability not in CREDIT_COSTS:
        raise ValueError(f"unknown capability: {capability}")
    if units < 1:
        raise ValueError("units must be positive")
    return CREDIT_COSTS[capability] * units


def decide(tier: str, capability: str, used: int, units: int = 1) -> CreditDecision:
    allowance = TIER_MONTHLY_CREDITS.get(tier, TIER_MONTHLY_CREDITS["free"])
    requested = estimate_credits(capability, units)
    remaining = max(0, allowance - max(0, used))
    return CreditDecision(
        tier=tier,
        capability=capability,
        requested=requested,
        allowance=allowance,
        used=max(0, used),
        remaining=remaining,
        allowed=requested <= remaining,
        outcome="allowed" if requested <= remaining else "denied",
    )


def usage_snapshot(
    user_id: str,
    tier: str,
    *,
    now: datetime | None = None,
) -> CreditDecision:
    """Return the current period's usage without charging the account."""
    period = period_key(now)
    from stratum.db import query

    rows = query(
        "SELECT credits_used FROM stratum.usage_credits "
        "WHERE user_id = %(uid)s AND period = %(period)s LIMIT 1",
        {"uid": user_id, "period": period},
    )
    used = int(rows[0].get("credits_used") or 0) if rows else 0
    return CreditDecision(
        tier=tier,
        capability="account",
        requested=0,
        allowance=TIER_MONTHLY_CREDITS.get(tier, TIER_MONTHLY_CREDITS["free"]),
        used=max(0, used),
        remaining=max(
            0,
            TIER_MONTHLY_CREDITS.get(tier, TIER_MONTHLY_CREDITS["free"]) - max(0, used),
        ),
        allowed=True,
        outcome="snapshot",
    )


def consume_credits(
    user_id: str,
    tier: str,
    capability: str,
    *,
    units: int = 1,
    now: datetime | None = None,
    idempotency_key: str | None = None,
) -> CreditDecision:
    """Atomically charge the monthly ledger, returning a denial if exhausted."""
    requested = estimate_credits(capability, units)
    if idempotency_key is not None and not idempotency_key.strip():
        raise ValueError("idempotency_key must be non-empty when supplied")
    period = period_key(now)
    allowance = TIER_MONTHLY_CREDITS.get(tier, TIER_MONTHLY_CREDITS["free"])
    from stratum.db import get_conn

    with get_conn() as conn:
        current_row = conn.execute(
            "SELECT credits_used FROM stratum.usage_credits WHERE user_id=? AND period=?",
            (user_id, period),
        ).fetchone()
        current = int(current_row[0]) if current_row else 0
        decision = decide(tier, capability, current, units)
        if idempotency_key is not None:
            event_row = conn.execute(
                "INSERT INTO stratum.usage_credit_events "
                "(idempotency_key, user_id, period, capability, units, credits, status) "
                "VALUES (?,?,?,?,?,?,?) ON CONFLICT (user_id, idempotency_key) "
                "DO NOTHING RETURNING status, credits, capability, units, period",
                (idempotency_key, user_id, period, capability, units, requested, "pending"),
            ).fetchone()
            if event_row is None:
                event_row = conn.execute(
                    "SELECT status, credits, capability, units, period FROM stratum.usage_credit_events "
                    "WHERE user_id=? AND idempotency_key=?",
                    (user_id, idempotency_key),
                ).fetchone()
                if event_row is None:
                    raise RuntimeError("usage credit idempotency event disappeared")
                (
                    replayed_status,
                    replayed_credits,
                    replayed_capability,
                    replayed_units,
                    replayed_period,
                ) = event_row
                if (
                    str(replayed_capability) != capability
                    or int(replayed_units) != units
                    or int(replayed_credits) != requested
                    or str(replayed_period) != period
                ):
                    raise CreditIdempotencyConflict(
                        "idempotency_key is already associated with a different credit operation"
                    )
                if replayed_status == "pending":
                    # A concurrent first request owns the pending reservation;
                    # do not charge a second time. The caller may retry later.
                    return CreditDecision(
                        tier=tier,
                        capability=str(replayed_capability),
                        requested=int(replayed_credits),
                        allowance=allowance,
                        used=max(0, current),
                        remaining=max(0, allowance - max(0, current)),
                        allowed=False,
                        outcome="in_flight",
                    )
                return CreditDecision(
                    tier=tier,
                    capability=str(replayed_capability),
                    requested=int(replayed_credits),
                    allowance=allowance,
                    used=max(0, current),
                    remaining=max(0, allowance - max(0, current)),
                    allowed=replayed_status == "charged",
                    outcome="replayed" if replayed_status == "charged" else "denied",
                )
        if not decision.allowed:
            if idempotency_key is not None:
                conn.execute(
                    "UPDATE stratum.usage_credit_events SET status=? "
                    "WHERE user_id=? AND idempotency_key=? AND status='pending'",
                    ("denied", user_id, idempotency_key),
                )
            return decision
        row = conn.execute(
            "INSERT INTO stratum.usage_credits (user_id, period, credits_used, updated_at) "
            "VALUES (?,?,?,NOW()) "
            "ON CONFLICT (user_id, period) DO UPDATE SET "
            "credits_used = stratum.usage_credits.credits_used + EXCLUDED.credits_used, "
            "updated_at = NOW() "
            "WHERE stratum.usage_credits.credits_used + EXCLUDED.credits_used <= ? "
            "RETURNING credits_used",
            (user_id, period, requested, allowance),
        ).fetchone()
        if not row:
            if idempotency_key is not None:
                conn.execute(
                    "UPDATE stratum.usage_credit_events SET status=? "
                    "WHERE user_id=? AND idempotency_key=? AND status='pending'",
                    ("denied", user_id, idempotency_key),
                )
            latest = conn.execute(
                "SELECT credits_used FROM stratum.usage_credits WHERE user_id=? AND period=?",
                (user_id, period),
            ).fetchone()
            return decide(tier, capability, int(latest[0]) if latest else allowance, units)
        used = int(row[0])
        if idempotency_key is not None:
            conn.execute(
                "UPDATE stratum.usage_credit_events SET status=? "
                "WHERE user_id=? AND idempotency_key=? AND status='pending'",
                ("charged", user_id, idempotency_key),
            )
    # The returned decision describes the post-charge ledger state.  Returning
    # the pre-charge value here made callers display stale usage and could hide
    # an exhausted account until the next request.  `allowed` remains true
    # because this request has already been accepted, including the exact
    # boundary case where remaining credits become zero.
    return CreditDecision(
        tier=tier,
        capability=capability,
        requested=requested,
        allowance=allowance,
        used=used,
        remaining=max(0, allowance - used),
        allowed=True,
        outcome="charged",
    )
