"""Tests for stratum.auth.dependencies — ≥5 tests per §3.7."""
import pytest
from unittest.mock import AsyncMock
from fastapi import HTTPException
from stratum.auth.dependencies import get_current_user_data
from stratum.auth.jwt_handler import encode_access


@pytest.mark.asyncio
async def test_valid_bearer_token():
    token = encode_access("user1", "corpus_user1")
    result = await get_current_user_data(authorization=f"Bearer {token}")
    assert result["sub"] == "user1"
    assert result["corpus_id"] == "corpus_user1"


@pytest.mark.asyncio
async def test_missing_authorization_header():
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_data(authorization=None)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_invalid_token():
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_data(authorization="Bearer invalid.token.here")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_wrong_scheme_basic():
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_data(authorization="Basic dXNlcjpwYXNz")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_empty_bearer():
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_data(authorization="Bearer ")
    assert exc_info.value.status_code == 401
