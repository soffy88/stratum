"""Tests for GraphRAG graph routes and DAO.

Uses real DuckDB in-memory fixture with 029/030 DDL.
graph_builder_service unit test mocks oprim.llm_call.
"""
import json
import pytest
import duckdb
from unittest.mock import patch, MagicMock


# ── Fixtures ──────────────────────────────────────────────────────────────────

GRAPH_DDL = """
CREATE TABLE IF NOT EXISTS graph_entities (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    entity_type VARCHAR DEFAULT 'concept',
    description VARCHAR,
    aliases JSON DEFAULT '[]',
    source_substrate_ids JSON DEFAULT '[]',
    mention_count INTEGER DEFAULT 1,
    embedding_id VARCHAR,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_graph_entities_user ON graph_entities(user_id);
CREATE TABLE IF NOT EXISTS graph_relations (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    source_entity_id VARCHAR NOT NULL,
    target_entity_id VARCHAR NOT NULL,
    relation_type VARCHAR DEFAULT 'related',
    description VARCHAR,
    weight FLOAT DEFAULT 1.0,
    source_substrate_ids JSON DEFAULT '[]',
    confidence FLOAT DEFAULT 0.5,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_graph_relations_user ON graph_relations(user_id);
"""


@pytest.fixture()
def graph_db(tmp_path):
    """In-memory DuckDB with graph tables."""
    db = duckdb.connect(":memory:")
    db.execute(GRAPH_DDL)
    return db


# ── DAO unit tests ─────────────────────────────────────────────────────────────

def test_upsert_entity_insert(graph_db):
    from stratum.dao.graph import upsert_entity
    with patch("stratum.dao.graph.get_conn") as mock_gc:
        mock_gc.return_value.__enter__ = lambda s: graph_db
        mock_gc.return_value.__exit__ = MagicMock(return_value=False)
        eid = upsert_entity("user1", "Transformer", "concept", "Attention-based model", "sub1")
        assert eid
        row = graph_db.execute(
            "SELECT name, mention_count FROM graph_entities WHERE id=?", (eid,)
        ).fetchone()
        assert row[0] == "Transformer"
        assert row[1] == 1


def test_upsert_entity_merge(graph_db):
    from stratum.dao.graph import upsert_entity
    with patch("stratum.dao.graph.get_conn") as mock_gc:
        mock_gc.return_value.__enter__ = lambda s: graph_db
        mock_gc.return_value.__exit__ = MagicMock(return_value=False)
        eid1 = upsert_entity("user1", "Transformer", "concept", None, "sub1")
        eid2 = upsert_entity("user1", "Transformer", "concept", None, "sub2")
        assert eid1 == eid2
        row = graph_db.execute(
            "SELECT mention_count FROM graph_entities WHERE id=?", (eid1,)
        ).fetchone()
        assert row[0] == 2


def test_upsert_relation(graph_db):
    from stratum.dao.graph import upsert_entity, upsert_relation
    with patch("stratum.dao.graph.get_conn") as mock_gc:
        mock_gc.return_value.__enter__ = lambda s: graph_db
        mock_gc.return_value.__exit__ = MagicMock(return_value=False)
        e1 = upsert_entity("u", "A", "concept", None, "s1")
        e2 = upsert_entity("u", "B", "concept", None, "s1")
        rid = upsert_relation("u", e1, e2, "uses", "A uses B", "s1", 0.8)
        assert rid
        row = graph_db.execute(
            "SELECT relation_type, confidence FROM graph_relations WHERE id=?", (rid,)
        ).fetchone()
        assert row[0] == "uses"
        assert abs(row[1] - 0.8) < 0.01


def test_get_entity_neighbors_empty(graph_db):
    from stratum.dao.graph import get_entity_neighbors
    with patch("stratum.dao.graph.get_conn") as mock_gc:
        mock_gc.return_value.__enter__ = lambda s: graph_db
        mock_gc.return_value.__exit__ = MagicMock(return_value=False)
        result = get_entity_neighbors("user1", [])
        assert result == []


# ── graph_builder_service unit test ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_build_graph_from_substrate_no_derivative():
    """Returns zeros when no markdown derivative exists."""
    from stratum.services.graph_builder_service import build_graph_from_substrate

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = None

    with patch("stratum.services.graph_builder_service.get_conn") as mock_gc:
        mock_gc.return_value.__enter__ = lambda s: mock_conn
        mock_gc.return_value.__exit__ = MagicMock(return_value=False)
        result = await build_graph_from_substrate("sub1", "user_hash")

    assert result == {"entities_added": 0, "relations_added": 0}


@pytest.mark.asyncio
async def test_build_graph_llm_extract(graph_db):
    """Mocked llm_call returns fixed JSON; verifies upsert calls."""
    from stratum.services.graph_builder_service import build_graph_from_substrate

    fake_llm_response = MagicMock()
    fake_llm_response.text = json.dumps({
        "entities": [
            {"name": "Attention", "type": "concept", "description": "Self-attention mechanism"},
            {"name": "Transformer", "type": "method", "description": "Attention-based arch"},
        ],
        "relations": [
            {"source": "Attention", "target": "Transformer",
             "relation_type": "part_of", "description": "Attention is part of Transformer"},
        ]
    })

    derivative_conn = MagicMock()
    derivative_conn.execute.return_value.fetchone.return_value = ("# Title\n\nLong content " * 50,)

    with patch("stratum.services.graph_builder_service.get_conn") as mock_gc, \
         patch("stratum.services.graph_builder_service.upsert_entity") as mock_ue, \
         patch("stratum.services.graph_builder_service.upsert_relation") as mock_ur, \
         patch("oprim.structural_chunk", return_value=[{"content": "test content " * 100}]), \
         patch("oprim.llm_call", return_value=fake_llm_response):
        mock_gc.return_value.__enter__ = lambda s: derivative_conn
        mock_gc.return_value.__exit__ = MagicMock(return_value=False)
        mock_ue.side_effect = lambda **kw: f"eid_{kw['name']}"

        result = await build_graph_from_substrate("sub1", "user_hash")

    assert result["entities_added"] == 2
    assert result["relations_added"] == 1
