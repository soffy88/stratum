"""Security contract for the browser-facing legacy API."""

import pytest
from starlette.middleware.cors import CORSMiddleware


def test_legacy_cors_does_not_use_wildcard_with_credentials():
    from stratum.http_api.app import app

    middleware = next(item for item in app.user_middleware if item.cls is CORSMiddleware)
    assert "*" not in middleware.kwargs["allow_origins"]
    assert middleware.kwargs["allow_credentials"] is True


def test_cors_origin_parser_rejects_wildcard(monkeypatch):
    from stratum.http_api.app import _cors_origins

    monkeypatch.setenv("STRATUM_CORS_ALLOWED_ORIGINS", "https://example.com, *")
    with pytest.raises(RuntimeError, match="must not contain"):
        _cors_origins()
