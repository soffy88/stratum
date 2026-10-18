"""STRATUM_REGISTRATION_ENABLED switch for POST /api/auth/register."""

import pytest
from fastapi import HTTPException

from stratum.http_api.routes import auth as auth_routes


@pytest.mark.parametrize("val", [None, "1", "true", "yes", "on", ""])
def test_registration_enabled_by_default(monkeypatch, val):
    if val is None:
        monkeypatch.delenv("STRATUM_REGISTRATION_ENABLED", raising=False)
    else:
        monkeypatch.setenv("STRATUM_REGISTRATION_ENABLED", val)
    assert auth_routes.registration_enabled() is True


@pytest.mark.parametrize("val", ["0", "false", "FALSE", "no", "off", " off "])
def test_registration_disabled_values(monkeypatch, val):
    monkeypatch.setenv("STRATUM_REGISTRATION_ENABLED", val)
    assert auth_routes.registration_enabled() is False


@pytest.mark.asyncio
async def test_register_rejected_when_disabled(monkeypatch):
    monkeypatch.setenv("STRATUM_REGISTRATION_ENABLED", "0")
    with pytest.raises(HTTPException) as ei:
        await auth_routes.register(req=None, request=None, db=None)  # type: ignore[arg-type]
    assert ei.value.status_code == 403
