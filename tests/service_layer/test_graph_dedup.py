"""Entity dedup: case/whitespace-insensitive merge in dao.graph.upsert_entity.

Real in-memory DuckDB fixture; patches get_conn like test_graph_routes.
"""
from unittest.mock import patch, MagicMock

import duckdb
import pytest

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
"""


@pytest.fixture()
def graph_db():
    db = duckdb.connect(":memory:")
    db.execute(GRAPH_DDL)
    return db


def _patched(graph_db):
    mock_gc = MagicMock()
    mock_gc.return_value.__enter__ = lambda s: graph_db
    mock_gc.return_value.__exit__ = MagicMock(return_value=False)
    return patch("stratum.dao.graph.get_conn", mock_gc)


def test_case_and_whitespace_insensitive_merge(graph_db):
    from stratum.dao.graph import upsert_entity

    with _patched(graph_db):
        a = upsert_entity("u1", "Deep Learning", "concept", "d", "sub1")
        b = upsert_entity("u1", "deep learning", "concept", "d", "sub2")
        c = upsert_entity("u1", "  DEEP LEARNING  ", "concept", "d", "sub3")

    assert a == b == c, "case/whitespace variants must collapse to one entity"
    rows = graph_db.execute("SELECT COUNT(*), MAX(mention_count) FROM graph_entities").fetchone()
    assert rows[0] == 1, "only one row should exist"
    assert rows[1] == 3, "mention_count accumulates across merges"

    sids = graph_db.execute("SELECT source_substrate_ids FROM graph_entities").fetchone()[0]
    import json
    assert set(json.loads(sids)) == {"sub1", "sub2", "sub3"}


def test_distinct_names_stay_separate(graph_db):
    from stratum.dao.graph import upsert_entity

    with _patched(graph_db):
        upsert_entity("u1", "Transformer", "concept", "d", "sub1")
        upsert_entity("u1", "Attention", "concept", "d", "sub1")

    n = graph_db.execute("SELECT COUNT(*) FROM graph_entities").fetchone()[0]
    assert n == 2
