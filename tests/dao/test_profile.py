"""Tests for stratum.dao.profile — ≥8 tests per §6.6."""
import pytest
from stratum.dao.profile import ProfileDAO
from stratum.dao.users import UserDAO


@pytest.fixture
def setup(db):
    u = UserDAO(db).create_user(email="p@t.com", username="profuser", password_hash="h")
    return ProfileDAO(db), u


def test_create_profile(setup):
    dao, u = setup
    p = dao.create_profile(u.id, display_name="Test User")
    assert p.user_id == u.id
    assert p.display_name == "Test User"


def test_get_profile(setup):
    dao, u = setup
    dao.create_profile(u.id, display_name="X")
    p = dao.get_profile(u.id)
    assert p.display_name == "X"


def test_get_nonexistent_returns_none(setup):
    dao, _ = setup
    assert dao.get_profile("fake") is None


def test_update_profile(setup):
    dao, u = setup
    dao.create_profile(u.id, display_name="Old")
    updated = dao.update_profile(u.id, display_name="New", bio="Hello")
    assert updated.display_name == "New"
    assert updated.bio == "Hello"


def test_update_nonexistent_returns_none(setup):
    dao, _ = setup
    assert dao.update_profile("fake", display_name="X") is None


def test_default_timezone(setup):
    dao, u = setup
    p = dao.create_profile(u.id)
    assert p.timezone == "Asia/Shanghai"


def test_default_locale(setup):
    dao, u = setup
    p = dao.create_profile(u.id)
    assert p.locale == "zh-CN"


def test_update_avatar_url(setup):
    dao, u = setup
    dao.create_profile(u.id)
    updated = dao.update_profile(u.id, avatar_url="/avatars/test.png")
    assert updated.avatar_url == "/avatars/test.png"
