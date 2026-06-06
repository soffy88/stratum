"""Corpus isolation tests for all DAO entities — §4.6 requirements.

Covers: substrate, note, concept, derivative, view, task, template.
Each entity: user A cannot read/list user B's data.
"""

import pytest
import ulid as ulid_mod
from datetime import datetime
from stratum.dao.users import UserDAO
from stratum.dao.substrate import SubstrateDAO
from stratum.utils.user_id_hash import hash_user_id
from stratum.dao.note import NoteDAO
from stratum.dao.concept import ConceptDAO
from stratum.dao.derivative import DerivativeDAO
from stratum.dao.view import ViewDAO
from stratum.dao.task import TaskDAO
from stratum.dao.template import TemplateDAO


@pytest.fixture
def two_users(db):
    dao = UserDAO(db)
    uA = dao.create_user(email="a@t.com", username="userA", password_hash="h")
    uB = dao.create_user(email="b@t.com", username="userB", password_hash="h")
    return uA, uB, db


# --- Substrate isolation (≥5) ---


def test_substrate_get_blocked_cross_corpus(two_users):
    uA, uB, db = two_users
    sid = str(ulid_mod.ULID())
    db.execute(
        "INSERT INTO substrates (id, user_id, title) VALUES (?,?,?)",
        (sid, hash_user_id(uA.id), "A's doc"),
    )
    dao = SubstrateDAO(db)
    assert dao.get_substrate(substrate_id=sid, user_id=uB.id) is None


def test_substrate_get_own_corpus(two_users):
    uA, uB, db = two_users
    sid = str(ulid_mod.ULID())
    db.execute(
        "INSERT INTO substrates (id, user_id, title) VALUES (?,?,?)",
        (sid, hash_user_id(uA.id), "A's doc"),
    )
    dao = SubstrateDAO(db)
    assert dao.get_substrate(substrate_id=sid, user_id=uA.id) is not None


def test_substrate_list_only_own(two_users):
    uA, uB, db = two_users
    db.execute(
        "INSERT INTO substrates (id, user_id, title) VALUES (?,?,?)",
        ("s1", hash_user_id(uA.id), "A1"),
    )
    db.execute(
        "INSERT INTO substrates (id, user_id, title) VALUES (?,?,?)",
        ("s2", hash_user_id(uB.id), "B1"),
    )
    dao = SubstrateDAO(db)
    a_list = dao.list_substrates(user_id=uA.id)
    assert all(s.user_id == hash_user_id(uA.id) for s in a_list)
    assert len(a_list) == 1


def test_substrate_list_empty_for_other(two_users):
    uA, uB, db = two_users
    db.execute(
        "INSERT INTO substrates (id, user_id, title) VALUES (?,?,?)",
        ("s1", hash_user_id(uA.id), "A1"),
    )
    dao = SubstrateDAO(db)
    assert dao.list_substrates(user_id=uB.id) == []


def test_substrate_nonexistent_id_returns_none(two_users):
    uA, _, db = two_users
    dao = SubstrateDAO(db)
    assert dao.get_substrate(substrate_id="fake", user_id=uA.id) is None


# --- Note isolation (≥5) ---


def test_note_create_and_get_own(two_users):
    uA, uB, db = two_users
    dao = NoteDAO(db)
    note = dao.create_note(corpus_id=uA.corpus_id, title="A note", content="content")
    assert dao.get_note(note_id=note.id, corpus_id=uA.corpus_id) is not None


def test_note_get_blocked_cross_corpus(two_users):
    uA, uB, db = two_users
    dao = NoteDAO(db)
    note = dao.create_note(corpus_id=uA.corpus_id, title="A note", content="secret")
    assert dao.get_note(note_id=note.id, corpus_id=uB.corpus_id) is None


def test_note_list_only_own(two_users):
    uA, uB, db = two_users
    dao = NoteDAO(db)
    dao.create_note(corpus_id=uA.corpus_id, title="A1", content="c")
    dao.create_note(corpus_id=uB.corpus_id, title="B1", content="c")
    a_notes = dao.list_notes(corpus_id=uA.corpus_id)
    assert len(a_notes) == 1
    assert a_notes[0].title == "A1"


def test_note_list_empty_for_other(two_users):
    uA, uB, db = two_users
    dao = NoteDAO(db)
    dao.create_note(corpus_id=uA.corpus_id, title="A1", content="c")
    assert dao.list_notes(corpus_id=uB.corpus_id) == []


def test_note_corpus_id_stored_correctly(two_users):
    uA, _, db = two_users
    dao = NoteDAO(db)
    note = dao.create_note(corpus_id=uA.corpus_id, title="T", content="C")
    assert note.corpus_id == uA.corpus_id


# --- Concept isolation (≥3) ---


def test_concept_get_blocked_cross_corpus(two_users):
    uA, uB, db = two_users
    cid = str(ulid_mod.ULID())
    db.execute(
        "INSERT INTO concept (id, name, source_ids, corpus_id) VALUES (?,?,?,?)",
        (cid, "X", "", uA.corpus_id),
    )
    dao = ConceptDAO(db)
    assert dao.get_concept(concept_id=cid, corpus_id=uB.corpus_id) is None


def test_concept_get_own(two_users):
    uA, _, db = two_users
    cid = str(ulid_mod.ULID())
    db.execute(
        "INSERT INTO concept (id, name, source_ids, corpus_id) VALUES (?,?,?,?)",
        (cid, "X", "", uA.corpus_id),
    )
    dao = ConceptDAO(db)
    assert dao.get_concept(concept_id=cid, corpus_id=uA.corpus_id) is not None


# --- Derivative isolation (≥3) ---


def test_derivative_list_blocked_cross_corpus(two_users):
    uA, uB, db = two_users
    db.execute(
        "INSERT INTO derivative (id, substrate_id, kind, seq, content, corpus_id) VALUES (?,?,?,?,?,?)",
        ("d1", "s1", "chunk", 0, "text", uA.corpus_id),
    )
    dao = DerivativeDAO(db)
    assert dao.list_by_substrate(substrate_id="s1", corpus_id=uB.corpus_id) == []


def test_derivative_list_own(two_users):
    uA, _, db = two_users
    db.execute(
        "INSERT INTO derivative (id, substrate_id, kind, seq, content, corpus_id) VALUES (?,?,?,?,?,?)",
        ("d1", "s1", "chunk", 0, "text", uA.corpus_id),
    )
    dao = DerivativeDAO(db)
    assert len(dao.list_by_substrate(substrate_id="s1", corpus_id=uA.corpus_id)) == 1


# --- View isolation (≥3) ---


def test_view_get_blocked_cross_corpus(two_users):
    uA, uB, db = two_users
    db.execute(
        "INSERT INTO views (id, user_id, corpus_id, name, default_filter) VALUES (?,?,?,?,?)",
        ("v1", uA.id, uA.corpus_id, "My View", "{}"),
    )
    dao = ViewDAO(db)
    assert dao.get_view(view_id="v1", corpus_id=uB.corpus_id) is None


def test_view_list_only_own(two_users):
    uA, uB, db = two_users
    db.execute(
        "INSERT INTO views (id, user_id, corpus_id, name, default_filter) VALUES (?,?,?,?,?)",
        ("v1", uA.id, uA.corpus_id, "A View", "{}"),
    )
    db.execute(
        "INSERT INTO views (id, user_id, corpus_id, name, default_filter) VALUES (?,?,?,?,?)",
        ("v2", uB.id, uB.corpus_id, "B View", "{}"),
    )
    dao = ViewDAO(db)
    assert len(dao.list_views(corpus_id=uA.corpus_id)) == 1


# --- Task isolation (≥3) ---


def test_task_get_blocked_cross_corpus(two_users):
    uA, uB, db = two_users
    db.execute(
        "INSERT INTO tasks (id, user_id, corpus_id, text) VALUES (?,?,?,?)",
        ("t1", uA.id, uA.corpus_id, "Do thing"),
    )
    dao = TaskDAO(db)
    assert dao.get_task(task_id="t1", corpus_id=uB.corpus_id) is None


def test_task_list_only_own(two_users):
    uA, uB, db = two_users
    db.execute(
        "INSERT INTO tasks (id, user_id, corpus_id, text) VALUES (?,?,?,?)",
        ("t1", uA.id, uA.corpus_id, "A task"),
    )
    db.execute(
        "INSERT INTO tasks (id, user_id, corpus_id, text) VALUES (?,?,?,?)",
        ("t2", uB.id, uB.corpus_id, "B task"),
    )
    dao = TaskDAO(db)
    assert len(dao.list_tasks(corpus_id=uA.corpus_id)) == 1


# --- Template isolation (≥3) ---


def test_template_get_blocked_cross_corpus(two_users):
    uA, uB, db = two_users
    db.execute(
        "INSERT INTO templates (id, user_id, corpus_id, name, content) VALUES (?,?,?,?,?)",
        ("tp1", uA.id, uA.corpus_id, "My Tmpl", "body"),
    )
    dao = TemplateDAO(db)
    assert dao.get_template(template_id="tp1", corpus_id=uB.corpus_id) is None


def test_template_list_only_own(two_users):
    uA, uB, db = two_users
    db.execute(
        "INSERT INTO templates (id, user_id, corpus_id, name, content) VALUES (?,?,?,?,?)",
        ("tp1", uA.id, uA.corpus_id, "A", "a"),
    )
    db.execute(
        "INSERT INTO templates (id, user_id, corpus_id, name, content) VALUES (?,?,?,?,?)",
        ("tp2", uB.id, uB.corpus_id, "B", "b"),
    )
    dao = TemplateDAO(db)
    assert len(dao.list_templates(corpus_id=uA.corpus_id)) == 1
