"""Tests for stratum.dao.users — ≥10 tests per §3.7."""
import pytest
from stratum.dao.users import UserDAO


def test_create_user(db):
    dao = UserDAO(db)
    user = dao.create_user(email="a@b.com", username="alice", password_hash="hash123")
    assert user.email == "a@b.com"
    assert user.username == "alice"
    assert user.id is not None


def test_corpus_id_auto_generated(db):
    dao = UserDAO(db)
    user = dao.create_user(email="a@b.com", username="alice", password_hash="h")
    assert user.corpus_id == f"user_{user.id}"


def test_corpus_id_unique_per_user(db):
    dao = UserDAO(db)
    u1 = dao.create_user(email="a@b.com", username="alice", password_hash="h")
    u2 = dao.create_user(email="b@b.com", username="bob", password_hash="h")
    assert u1.corpus_id != u2.corpus_id


def test_get_user_by_id(db):
    dao = UserDAO(db)
    user = dao.create_user(email="a@b.com", username="alice", password_hash="h")
    found = dao.get_user_by_id(user.id)
    assert found.email == "a@b.com"


def test_get_user_by_email(db):
    dao = UserDAO(db)
    dao.create_user(email="a@b.com", username="alice", password_hash="h")
    found = dao.get_user_by_email("a@b.com")
    assert found.username == "alice"


def test_get_user_by_username(db):
    dao = UserDAO(db)
    dao.create_user(email="a@b.com", username="alice", password_hash="h")
    found = dao.get_user_by_username("alice")
    assert found.email == "a@b.com"


def test_get_nonexistent_returns_none(db):
    dao = UserDAO(db)
    assert dao.get_user_by_id("nonexistent") is None
    assert dao.get_user_by_email("no@no.com") is None
    assert dao.get_user_by_username("nobody") is None


def test_duplicate_email_raises(db):
    dao = UserDAO(db)
    dao.create_user(email="a@b.com", username="alice", password_hash="h")
    with pytest.raises(Exception):
        dao.create_user(email="a@b.com", username="bob", password_hash="h")


def test_duplicate_username_raises(db):
    dao = UserDAO(db)
    dao.create_user(email="a@b.com", username="alice", password_hash="h")
    with pytest.raises(Exception):
        dao.create_user(email="c@d.com", username="alice", password_hash="h")


def test_user_defaults(db):
    dao = UserDAO(db)
    user = dao.create_user(email="a@b.com", username="alice", password_hash="h")
    assert user.email_verified is False
    assert user.is_active is True
    assert user.is_suspended is False


def test_created_at_populated(db):
    dao = UserDAO(db)
    user = dao.create_user(email="a@b.com", username="alice", password_hash="h")
    assert user.created_at is not None
