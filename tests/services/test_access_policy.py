import pytest

from stratum.services.access_policy import (
    allowed_content_tiers,
    can_access_content,
    normalize_tier,
)


def test_active_subscription_tier_fails_closed_before_billing_and_jobs(monkeypatch):
    from stratum.api.routers import billing

    seen: dict[str, str] = {}

    def fake_query(sql, *_args, **_kwargs):
        seen["sql"] = sql
        return [{"tier": "enterprise"}]

    monkeypatch.setattr(billing, "query", fake_query)

    assert billing.get_active_tier("user-1") == "free"
    assert "stratum.subscriptions" in seen["sql"]


@pytest.mark.asyncio
async def test_subscription_status_reads_latest_canonical_subscription(monkeypatch):
    from stratum.api.routers import billing

    seen: dict[str, str] = {}

    def fake_query(sql, *_args, **_kwargs):
        seen["sql"] = sql
        return [{"tier": "plus", "status": "active"}]

    monkeypatch.setattr(billing, "query", fake_query)

    result = await billing.subscription_status("user-1")

    assert result["tier"] == "plus"
    assert "ORDER BY started_at DESC" in seen["sql"]
    assert "stratum.subscriptions" in seen["sql"]


def test_unknown_or_empty_tier_fails_closed_to_free():
    assert normalize_tier(None) == "free"
    assert normalize_tier("enterprise") == "free"
    assert allowed_content_tiers("enterprise") == ("free",)
    assert can_access_content("enterprise", "free") is True
    assert can_access_content("enterprise", "plus") is False


def test_tiers_are_cumulative():
    assert allowed_content_tiers("free") == ("free",)
    assert allowed_content_tiers("plus") == ("free", "plus")
    assert allowed_content_tiers("pro") == ("free", "plus", "pro")
    assert can_access_content("plus", "pro") is False
    assert can_access_content("pro", "plus") is True
