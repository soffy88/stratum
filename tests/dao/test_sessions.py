"""Tests for stratum.dao.sessions — ≥8 tests per §3.7."""
import pytest
from datetime import datetime, timedelta
from stratum.dao.sessions import SessionDAO


def test_create_session(db):
    dao = SessionDAO(db)
    s = dao.create_session(user_id="u1", refresh_token_hash="hash1", user_agent="Mozilla", ip="1.2.3.4")
    assert s.user_id == "u1"
    assert s.refresh_token_hash == "hash1"


def test_get_session_by_id(db):
    dao = SessionDAO(db)
    s = dao.create_session(user_id="u1", refresh_token_hash="hash1", user_agent=None, ip=None)
    found = dao.get_session_by_id(s.id)
    assert found.id == s.id


def test_get_session_by_refresh_hash(db):
    dao = SessionDAO(db)
    dao.create_session(user_id="u1", refresh_token_hash="unique_hash", user_agent=None, ip=None)
    found = dao.get_session_by_refresh_hash("unique_hash")
    assert found is not None
    assert found.user_id == "u1"


def test_get_revoked_session_returns_none(db):
    dao = SessionDAO(db)
    s = dao.create_session(user_id="u1", refresh_token_hash="h1", user_agent=None, ip=None)
    db.execute("UPDATE sessions SET revoked_at = CURRENT_TIMESTAMP WHERE id = ?", (s.id,))
    found = dao.get_session_by_refresh_hash("h1")
    assert found is None


def test_expires_at_default_30_days(db):
    dao = SessionDAO(db)
    s = dao.create_session(user_id="u1", refresh_token_hash="h1", user_agent=None, ip=None)
    delta = s.expires_at - s.created_at
    assert 29 <= delta.days <= 30


def test_custom_ttl(db):
    dao = SessionDAO(db)
    s = dao.create_session(user_id="u1", refresh_token_hash="h1", user_agent=None, ip=None, ttl_days=7)
    delta = s.expires_at - s.created_at
    assert 6 <= delta.days <= 7


def test_refresh_hash_uniqueness(db):
    dao = SessionDAO(db)
    dao.create_session(user_id="u1", refresh_token_hash="same_hash", user_agent=None, ip=None)
    with pytest.raises(Exception):
        dao.create_session(user_id="u2", refresh_token_hash="same_hash", user_agent=None, ip=None)


def test_nonexistent_hash_returns_none(db):
    dao = SessionDAO(db)
    assert dao.get_session_by_refresh_hash("no_such_hash") is None
