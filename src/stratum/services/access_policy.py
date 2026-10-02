"""Small, deterministic entitlement policy shared by content surfaces."""

from __future__ import annotations

TIER_RANK = {"free": 0, "plus": 1, "pro": 2}


def normalize_tier(tier: str | None) -> str:
    value = (tier or "free").strip().lower()
    return value if value in TIER_RANK else "free"


def allowed_content_tiers(user_tier: str | None) -> tuple[str, ...]:
    rank = TIER_RANK[normalize_tier(user_tier)]
    return tuple(name for name, tier_rank in TIER_RANK.items() if tier_rank <= rank)


def can_access_content(user_tier: str | None, required_tier: str | None) -> bool:
    user_rank = TIER_RANK[normalize_tier(user_tier)]
    required = normalize_tier(required_tier)
    return user_rank >= TIER_RANK[required]
