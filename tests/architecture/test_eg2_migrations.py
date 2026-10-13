"""Static checks for the EmbeddingGemma2 cutover / cleanup migrations (no DB)."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PG = ROOT / "src" / "stratum" / "db" / "pg_migrations"
AII = ROOT / "aii" / "migrations"

CUTOVER = [
    PG / "089_eg2_embedding_cutover.sql",
    AII / "refined" / "0007_eg2_embedding_cutover.sql",
    AII / "context" / "0007_eg2_embedding_cutover.sql",
]
CLEANUP = [
    PG / "090_drop_bge1024_columns.sql",
    AII / "refined" / "0008_drop_bge1024_columns.sql",
    AII / "context" / "0008_drop_bge1024_columns.sql",
]


@pytest.mark.parametrize("path", CUTOVER + CLEANUP, ids=lambda p: p.name)
def test_guarded_do_block(path):
    sql = path.read_text()
    assert "DO $$" in sql and "END $$;" in sql
    assert "to_regclass" in sql


@pytest.mark.parametrize("path", CUTOVER, ids=lambda p: p.name)
def test_cutover_renames_and_is_idempotent(path):
    sql = path.read_text()
    assert "RENAME COLUMN" in sql
    assert "'_bge1024'" in sql and "'_768'" in sql
    assert "'vector(1024)'" in sql  # only acts while the live column is still 1024-d
    assert "eg2_cutover_allow_gaps" in sql  # refuses to cut over with backfill gaps
    assert "hnsw" in sql.lower() and "vector_cosine_ops" in sql
    assert "Manual rollback" in sql


@pytest.mark.parametrize("path", CLEANUP, ids=lambda p: p.name)
def test_cleanup_drops_only_after_verified_cutover(path):
    sql = path.read_text()
    assert "DROP COLUMN IF EXISTS" in sql and "'_bge1024'" in sql
    assert "'vector(768)'" in sql
    assert "eg2_cutover_verified" in sql
    assert "DROP TABLE IF EXISTS public.eg2_backfill_ledger" in sql


def test_cutover_table_lists():
    kg = (PG / "089_eg2_embedding_cutover.sql").read_text()
    for t in ("ku_onto", "concept_onto", "invariant", "tenant_ann_vectors", "substrate_layers"):
        assert f"'{t}'" in kg
    assert "('stratum', 'multimodal_assets'" not in kg
    rf = (AII / "refined" / "0007_eg2_embedding_cutover.sql").read_text()
    assert "('rf', 'refined_invariant', 'invariant_vector')" in rf
    cx = (AII / "context" / "0007_eg2_embedding_cutover.sql").read_text()
    for t in ("decision_case", "lesson_pattern", "methodology"):
        assert f"'{t}'" in cx
