"""Weekly Useful Knowledge Reuse (WUKR) metric."""

from __future__ import annotations


def calculate_wukr(active_users: int, useful_reuse_users: int) -> dict[str, float | int]:
    """Return the north-star ratio and its auditable numerator/denominator."""
    active = max(0, int(active_users))
    useful = max(0, min(active, int(useful_reuse_users)))
    return {
        "active_users": active,
        "useful_reuse_users": useful,
        "wukr": round(useful / active, 4) if active else 0.0,
    }
