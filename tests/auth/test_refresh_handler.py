"""Tests for stratum.auth.refresh_handler — ≥8 tests per §3.7."""
import hashlib
from stratum.auth.refresh_handler import create_refresh


def test_create_refresh_returns_tuple():
    token_str, refresh_hash = create_refresh("user1", "Mozilla/5.0", "127.0.0.1")
    assert isinstance(token_str, str)
    assert isinstance(refresh_hash, str)


def test_token_contains_ulid_and_secret():
    token_str, _ = create_refresh("user1", None, None)
    parts = token_str.split("_", 1)
    assert len(parts) == 2
    assert len(parts[0]) == 26  # ULID length
    assert len(parts[1]) == 128  # 64 bytes hex


def test_hash_is_sha256_of_token():
    token_str, refresh_hash = create_refresh("user1", None, None)
    expected = hashlib.sha256(token_str.encode()).hexdigest()
    assert refresh_hash == expected


def test_each_call_produces_unique_token():
    t1, h1 = create_refresh("user1", None, None)
    t2, h2 = create_refresh("user1", None, None)
    assert t1 != t2
    assert h1 != h2


def test_hash_length_is_64_hex():
    _, refresh_hash = create_refresh("user1", None, None)
    assert len(refresh_hash) == 64


def test_token_str_not_empty():
    token_str, _ = create_refresh("u", "agent", "1.2.3.4")
    assert len(token_str) > 100


def test_different_users_different_tokens():
    t1, _ = create_refresh("alice", None, None)
    t2, _ = create_refresh("bob", None, None)
    assert t1 != t2


def test_none_user_agent_and_ip_accepted():
    token_str, refresh_hash = create_refresh("user1", None, None)
    assert token_str and refresh_hash
