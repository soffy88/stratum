import pytest
import duckdb
import os
import ulid
import uuid
from stratum.dao.users import UserDAO
from stratum.dao.substrate import SubstrateDAO
from stratum.dao.note import NoteDAO

@pytest.fixture
def db_conn():
    db_path = os.path.expanduser("~/.stratum/meta.duckdb")
    conn = duckdb.connect(db_path)
    yield conn
    conn.close()

def test_user_A_cannot_read_user_B_substrate(db_conn):
    user_dao = UserDAO(db_conn)
    sub_dao = SubstrateDAO(db_conn)
    suffix = str(uuid.uuid4())[:8]
    uA = user_dao.create_user(email=f"uA_{suffix}@test.com", username=f"userA_{suffix}", password_hash="hash")
    uB = user_dao.create_user(email=f"uB_{suffix}@test.com", username=f"userB_{suffix}", password_hash="hash")
    sub_id = str(ulid.ULID())
    db_conn.execute("INSERT INTO substrate (id, ulid, corpus_id, title) VALUES (?, ?, ?, ?)", (sub_id, sub_id, uA.corpus_id, "Secret A"))
    leak = sub_dao.get_substrate(substrate_id=sub_id, corpus_id=uB.corpus_id)
    assert leak is None
    own = sub_dao.get_substrate(substrate_id=sub_id, corpus_id=uA.corpus_id)
    assert own is not None

def test_user_A_cannot_list_user_B_notes(db_conn):
    user_dao = UserDAO(db_conn)
    note_dao = NoteDAO(db_conn)
    suffix = str(uuid.uuid4())[:8]
    uA = user_dao.create_user(email=f"uA2_{suffix}@test.com", username=f"userA2_{suffix}", password_hash="hash")
    uB = user_dao.create_user(email=f"uB2_{suffix}@test.com", username=f"userB2_{suffix}", password_hash="hash")
    note_dao.create_note(corpus_id=uA.corpus_id, title="Note A", content="A content")
    notes_for_B = note_dao.list_notes(corpus_id=uB.corpus_id)
    for n in notes_for_B:
        assert n.corpus_id == uB.corpus_id
        assert n.title != "Note A"

@pytest.mark.asyncio
async def test_user_A_cannot_search_user_B_content(db_conn):
    from stratum.service.search import stratum_search
    user_dao = UserDAO(db_conn)
    suffix = str(uuid.uuid4())[:8]
    uA = user_dao.create_user(email=f"uA_s_{suffix}@test.com", username=f"userA_s_{suffix}", password_hash="hash")
    uB = user_dao.create_user(email=f"uB_s_{suffix}@test.com", username=f"userB_s_{suffix}", password_hash="hash")
    sub_id_A = str(ulid.ULID())
    db_conn.execute("INSERT INTO substrate (id, ulid, corpus_id, title) VALUES (?, ?, ?, ?)", (sub_id_A, sub_id_A, uA.corpus_id, "UniqueTitleA"))
    sub_id_B = str(ulid.ULID())
    db_conn.execute("INSERT INTO substrate (id, ulid, corpus_id, title) VALUES (?, ?, ?, ?)", (sub_id_B, sub_id_B, uB.corpus_id, "UniqueTitleB"))
    
    from unittest.mock import patch
    from oskill.hybrid_search import SearchResult
    mock_results = [
        SearchResult(type="substrate", id=sub_id_A, title="Title A", score=0.9, highlight=None),
        SearchResult(type="substrate", id=sub_id_B, title="Title B", score=0.8, highlight=None),
    ]
    with patch("stratum.service.search.hybrid_search", return_value=mock_results):
        results = await stratum_search(query="Unique", corpus_id=uA.corpus_id)
        ids = [r.id for r in results]
        assert sub_id_A in ids
        assert sub_id_B not in ids
