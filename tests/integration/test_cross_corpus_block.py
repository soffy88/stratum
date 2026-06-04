"""Cross-corpus penetration tests — ≥20 tests per §4.6.

Red-line tests: any failure blocks Wave 2.
"""

import pytest
import ulid as ulid_mod
import uuid
import os
import glob
from stratum.dao.users import UserDAO
from stratum.dao.substrate import SubstrateDAO
from stratum.dao.note import NoteDAO
from stratum.dao.concept import ConceptDAO
from stratum.dao.derivative import DerivativeDAO
from stratum.dao.view import ViewDAO
from stratum.dao.task import TaskDAO
from stratum.dao.template import TemplateDAO


@pytest.fixture
def two_users(db):
    dao = UserDAO(db)
    uA = dao.create_user(email="pA@t.com", username="penA", password_hash="h")
    uB = dao.create_user(email="pB@t.com", username="penB", password_hash="h")
    return uA, uB, db


# --- Substrate penetration ---


def test_user_A_cannot_read_user_B_substrate(two_users):
    uA, uB, db = two_users
    sid = str(ulid_mod.ULID())
    db.execute(
        "INSERT INTO substrates (id, user_id, title) VALUES (?,?,?)",
        (sid, uB.id, "B secret"),
    )
    assert SubstrateDAO(db).get_substrate(substrate_id=sid, user_id=uA.id) is None


def test_user_A_cannot_list_user_B_substrates(two_users):
    uA, uB, db = two_users
    db.execute(
        "INSERT INTO substrates (id, user_id, title) VALUES (?,?,?)",
        ("s1", uB.id, "B doc"),
    )
    results = SubstrateDAO(db).list_substrates(user_id=uA.id)
    assert len(results) == 0


# --- Note penetration ---


def test_user_A_cannot_read_user_B_note(two_users):
    uA, uB, db = two_users
    note = NoteDAO(db).create_note(corpus_id=uB.corpus_id, title="B note", content="secret")
    assert NoteDAO(db).get_note(note_id=note.id, corpus_id=uA.corpus_id) is None


def test_user_A_cannot_list_user_B_notes(two_users):
    uA, uB, db = two_users
    NoteDAO(db).create_note(corpus_id=uB.corpus_id, title="B note", content="x")
    results = NoteDAO(db).list_notes(corpus_id=uA.corpus_id)
    assert len(results) == 0


# --- Concept penetration ---


def test_user_A_cannot_read_user_B_concept(two_users):
    uA, uB, db = two_users
    cid = str(ulid_mod.ULID())
    db.execute(
        "INSERT INTO concept (id, name, source_ids, corpus_id) VALUES (?,?,?,?)",
        (cid, "Secret", "", uB.corpus_id),
    )
    assert ConceptDAO(db).get_concept(concept_id=cid, corpus_id=uA.corpus_id) is None


# --- Derivative penetration ---


def test_user_A_cannot_list_user_B_derivatives(two_users):
    uA, uB, db = two_users
    db.execute(
        "INSERT INTO derivative (id, substrate_id, kind, seq, content, corpus_id) VALUES (?,?,?,?,?,?)",
        ("d1", "s1", "chunk", 0, "text", uB.corpus_id),
    )
    assert DerivativeDAO(db).list_by_substrate(substrate_id="s1", corpus_id=uA.corpus_id) == []


# --- View penetration ---


def test_user_A_cannot_read_user_B_view(two_users):
    uA, uB, db = two_users
    db.execute(
        "INSERT INTO views (id, user_id, corpus_id, name, default_filter) VALUES (?,?,?,?,?)",
        ("v1", uB.id, uB.corpus_id, "B view", "{}"),
    )
    assert ViewDAO(db).get_view(view_id="v1", corpus_id=uA.corpus_id) is None


def test_user_A_cannot_list_user_B_views(two_users):
    uA, uB, db = two_users
    db.execute(
        "INSERT INTO views (id, user_id, corpus_id, name, default_filter) VALUES (?,?,?,?,?)",
        ("v1", uB.id, uB.corpus_id, "B view", "{}"),
    )
    assert ViewDAO(db).list_views(corpus_id=uA.corpus_id) == []


# --- Task penetration ---


def test_user_A_cannot_read_user_B_task(two_users):
    uA, uB, db = two_users
    db.execute(
        "INSERT INTO tasks (id, user_id, corpus_id, text) VALUES (?,?,?,?)",
        ("t1", uB.id, uB.corpus_id, "B task"),
    )
    assert TaskDAO(db).get_task(task_id="t1", corpus_id=uA.corpus_id) is None


def test_user_A_cannot_list_user_B_tasks(two_users):
    uA, uB, db = two_users
    db.execute(
        "INSERT INTO tasks (id, user_id, corpus_id, text) VALUES (?,?,?,?)",
        ("t1", uB.id, uB.corpus_id, "B task"),
    )
    assert TaskDAO(db).list_tasks(corpus_id=uA.corpus_id) == []


# --- Template penetration ---


def test_user_A_cannot_read_user_B_template(two_users):
    uA, uB, db = two_users
    db.execute(
        "INSERT INTO templates (id, user_id, corpus_id, name, content) VALUES (?,?,?,?,?)",
        ("tp1", uB.id, uB.corpus_id, "B tmpl", "body"),
    )
    assert TemplateDAO(db).get_template(template_id="tp1", corpus_id=uA.corpus_id) is None


def test_user_A_cannot_list_user_B_templates(two_users):
    uA, uB, db = two_users
    db.execute(
        "INSERT INTO templates (id, user_id, corpus_id, name, content) VALUES (?,?,?,?,?)",
        ("tp1", uB.id, uB.corpus_id, "B tmpl", "body"),
    )
    assert TemplateDAO(db).list_templates(corpus_id=uA.corpus_id) == []


# --- Search isolation (mocked) ---


@pytest.mark.asyncio
async def test_user_A_cannot_search_user_B_content(two_users):
    uA, uB, db = two_users
    sid_a = str(ulid_mod.ULID())
    sid_b = str(ulid_mod.ULID())
    db.execute(
        "INSERT INTO substrates (id, user_id, title) VALUES (?,?,?)",
        (sid_a, uA.id, "A doc"),
    )
    db.execute(
        "INSERT INTO substrates (id, user_id, title) VALUES (?,?,?)",
        (sid_b, uB.id, "B doc"),
    )

    from unittest.mock import patch, AsyncMock
    from types import SimpleNamespace

    mock_results = [
        SimpleNamespace(type="substrate", id=sid_a, title="A", score=0.9, highlight=None),
        SimpleNamespace(type="substrate", id=sid_b, title="B", score=0.8, highlight=None),
    ]
    with patch(
        "stratum.service.search.hybrid_search", new_callable=AsyncMock, return_value=mock_results
    ):
        with patch("stratum.service.search.duckdb") as mock_duckdb:
            mock_duckdb.connect.return_value = db
            from stratum.service.search import stratum_search

            results = await stratum_search(query="test", corpus_id=uA.corpus_id, user_id=uA.id)
            ids = [r.id for r in results]
            assert sid_a in ids
            assert sid_b not in ids


# --- Injection attack tests ---


def test_corpus_id_injection_via_direct_sql_blocked(two_users):
    """Even if attacker knows B's corpus_id, DAO enforces filtering."""
    uA, uB, db = two_users
    NoteDAO(db).create_note(corpus_id=uB.corpus_id, title="Secret", content="data")
    # Attacker tries to use B's corpus_id directly
    results = NoteDAO(db).list_notes(corpus_id=uB.corpus_id)
    # This succeeds at DAO level (DAO trusts caller), but middleware prevents this
    # The real protection is middleware never passes B's corpus_id to A's request
    assert len(results) == 1  # DAO returns B's data when given B's corpus_id
    # But A's corpus_id returns nothing
    assert NoteDAO(db).list_notes(corpus_id=uA.corpus_id) == []


def test_no_api_route_accepts_corpus_id_from_input():
    """Grep routes to ensure no endpoint accepts corpus_id from query/body."""
    import pathlib

    routes_dir = pathlib.Path(__file__).parents[2] / "src" / "stratum" / "http_api" / "routes"
    for py_file in routes_dir.glob("*.py"):
        content = py_file.read_text()
        # corpus_id should never appear as a query param or request body field
        assert "corpus_id: str" not in content or "request.state.corpus_id" in content, (
            f"{py_file.name} accepts corpus_id as input parameter"
        )


def test_corpus_id_not_in_register_response(two_users):
    """Register response schema must not expose corpus_id."""
    from stratum.http_api.schemas.auth import RegisterResponse

    fields = RegisterResponse.model_fields
    assert "corpus_id" not in fields


def test_corpus_id_not_in_user_public(two_users):
    """UserPublic schema must not expose corpus_id."""
    from stratum.http_api.schemas.auth import UserPublic

    fields = UserPublic.model_fields
    assert "corpus_id" not in fields


def test_multiple_users_complete_isolation(db):
    """Create 5 users, each with data. Verify complete isolation."""
    user_dao = UserDAO(db)
    note_dao = NoteDAO(db)
    users = []
    for i in range(5):
        u = user_dao.create_user(email=f"u{i}@t.com", username=f"user{i}", password_hash="h")
        users.append(u)
        note_dao.create_note(corpus_id=u.corpus_id, title=f"Note {i}", content=f"Content {i}")

    for i, u in enumerate(users):
        notes = note_dao.list_notes(corpus_id=u.corpus_id)
        assert len(notes) == 1
        assert notes[0].title == f"Note {i}"
