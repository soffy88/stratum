"""Tests for stratum.dao.share_tokens — ≥10 tests per §6.6."""
import pytest
from stratum.dao.share_tokens import ShareTokenDAO
from stratum.dao.users import UserDAO


@pytest.fixture
def setup(db):
    user_dao = UserDAO(db)
    u = user_dao.create_user(email="s@t.com", username="sharer", password_hash="h")
    return ShareTokenDAO(db), u, db


def test_create_share_token(setup):
    dao, u, _ = setup
    s = dao.create_share_token(resource_type="note", resource_id="n1", corpus_id=u.corpus_id, created_by=u.id)
    assert s.token is not None
    assert len(s.token) == 16
    assert s.resource_type == "note"


def test_get_share_token(setup):
    dao, u, _ = setup
    s = dao.create_share_token(resource_type="note", resource_id="n1", corpus_id=u.corpus_id, created_by=u.id)
    found = dao.get_share_token(s.token)
    assert found.resource_id == "n1"


def test_get_nonexistent_returns_none(setup):
    dao, _, _ = setup
    assert dao.get_share_token("nonexistent") is None


def test_list_user_shares(setup):
    dao, u, _ = setup
    dao.create_share_token(resource_type="note", resource_id="n1", corpus_id=u.corpus_id, created_by=u.id)
    dao.create_share_token(resource_type="note", resource_id="n2", corpus_id=u.corpus_id, created_by=u.id)
    shares = dao.list_user_shares(u.id)
    assert len(shares) == 2


def test_list_filters_by_type(setup):
    dao, u, _ = setup
    dao.create_share_token(resource_type="note", resource_id="n1", corpus_id=u.corpus_id, created_by=u.id)
    dao.create_share_token(resource_type="substrate", resource_id="s1", corpus_id=u.corpus_id, created_by=u.id)
    assert len(dao.list_user_shares(u.id, resource_type="note")) == 1


def test_revoke_share(setup):
    dao, u, _ = setup
    s = dao.create_share_token(resource_type="note", resource_id="n1", corpus_id=u.corpus_id, created_by=u.id)
    assert dao.revoke_share(s.token, u.id) is True
    revoked = dao.get_share_token(s.token)
    assert revoked.revoked_at is not None


def test_revoke_wrong_user_fails(setup):
    dao, u, db = setup
    s = dao.create_share_token(resource_type="note", resource_id="n1", corpus_id=u.corpus_id, created_by=u.id)
    assert dao.revoke_share(s.token, "other_user") is False


def test_revoked_not_in_list(setup):
    dao, u, _ = setup
    s = dao.create_share_token(resource_type="note", resource_id="n1", corpus_id=u.corpus_id, created_by=u.id)
    dao.revoke_share(s.token, u.id)
    assert len(dao.list_user_shares(u.id)) == 0


def test_increment_access(setup):
    dao, u, _ = setup
    s = dao.create_share_token(resource_type="note", resource_id="n1", corpus_id=u.corpus_id, created_by=u.id)
    dao.increment_access(s.token)
    dao.increment_access(s.token)
    updated = dao.get_share_token(s.token)
    assert updated.access_count == 2
    assert updated.last_accessed_at is not None


def test_expires_in_days(setup):
    dao, u, _ = setup
    s = dao.create_share_token(resource_type="note", resource_id="n1", corpus_id=u.corpus_id, created_by=u.id, expires_in_days=7)
    assert s.expires_at is not None
    delta = s.expires_at - s.created_at
    assert 6 <= delta.days <= 7
