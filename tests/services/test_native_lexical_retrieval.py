"""Contract tests for database-native lexical retrieval."""

from pathlib import Path


ROOT = Path(__file__).parents[2]
ENGINE = ROOT / "src/stratum/services/retrieval_engine.py"
MIGRATION = ROOT / "src/stratum/db/pg_migrations/052_lexical_retrieval_indexes.sql"


def test_lexical_retrieval_uses_native_index_contract():
    source = ENGINE.read_text(encoding="utf-8")
    lexical = source[
        source.index("def _text_search_layers") : source.index("def _vector_search_chunks")
    ]
    metadata = source[
        source.index("def _title_metadata_search") : source.index("def _rrf_merge_channels")
    ]
    assert "ORDER BY score DESC" in source
    assert "LIMIT ?" in source
    assert "pg_trgm" in source or "ILIKE" in source
    assert "results.sort" not in lexical
    assert "results.sort" not in metadata
    assert "SELECT s.id, s.title, s.source_path FROM substrates s" not in metadata


def test_lexical_indexes_cover_fragments_and_metadata():
    migration = MIGRATION.read_text(encoding="utf-8")
    assert "CREATE EXTENSION IF NOT EXISTS pg_trgm" in migration
    assert "idx_substrate_chunk_text_trgm" in migration
    assert "idx_substrates_title_trgm" in migration
    assert "idx_substrates_source_path_trgm" in migration
