"""PG integration tests — AII Notes in the single KnowledgeView retrieval plane.

Covers P0-3 (note body enters unified retrieval):
- migration 093 is idempotent (applies twice) and creates the pg_trgm index,
- scope="user-authored" finds the caller's own note body via KnowledgeView,
- cross-user negative: another user's notes are never returned,
- soft-deleted notes are excluded,
- every result satisfies the stable KnowledgeView schema.

Like tests/integration/test_pg_service_layer.py this talks to the real
PostgreSQL the service layer uses (env STRATUM_PG_*; the CI tenant-security
job bootstraps it on 127.0.0.1:5435).  Seed rows use unique ids and are
committed (so the app's pooled connections can see them) and deleted in
teardown.  If PostgreSQL is unreachable the DB tests SKIP (sk:pif-no-testdb);
the pure unit tests below always run.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import psycopg2
import pytest

REPO_ROOT = Path(__file__).parents[2]
MIGRATION_093 = REPO_ROOT / "src/stratum/db/pg_migrations" / "093_notes_trgm.sql"

NOTES_SL_DDL = """
CREATE SCHEMA IF NOT EXISTS stratum;
CREATE TABLE IF NOT EXISTS stratum.notes_sl (
    "id" TEXT PRIMARY KEY,
    "user_id" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "content_markdown" TEXT,
    "substrate_refs" TEXT[],
    "concept_refs" TEXT[],
    "content_refs" TEXT[],
    "created_at" TIMESTAMPTZ,
    "updated_at" TIMESTAMPTZ,
    "deleted_at" TIMESTAMPTZ
);
"""


def _pg_dsn() -> dict:
    return {
        "host": os.environ.get("STRATUM_PG_HOST", "127.0.0.1"),
        "port": int(os.environ.get("STRATUM_PG_PORT", "5435")),
        "user": os.environ.get("STRATUM_PG_USER", "aii"),
        "password": os.environ.get("STRATUM_PG_PASSWORD", "aii_safe_pass"),
        "dbname": os.environ.get("STRATUM_PG_DB", "aii_kg"),
        "options": "-c search_path=stratum,public",
    }


@pytest.fixture
def pg_notes():
    """Seeded notes_sl on real PG; rows committed for pool visibility.

    Yields (conn, tag); teardown deletes the seeded rows and commits.
    """
    try:
        raw = psycopg2.connect(**_pg_dsn())
    except psycopg2.OperationalError as e:
        pytest.skip(f"PostgreSQL not reachable — sk:pif-no-testdb ({e})")
    raw.autocommit = True
    tag = f"p0-093-{uuid.uuid4().hex[:12]}"
    try:
        with raw.cursor() as cur:
            cur.execute(NOTES_SL_DDL)
            # Idempotency: the migration file must apply cleanly twice,
            # mirroring the CI migration gate ("run upgrade, run again").
            sql = MIGRATION_093.read_text(encoding="utf-8")
            cur.execute(sql)
            cur.execute(sql)
            seeds = [
                (
                    f"{tag}-a1",
                    "p0-user-a",
                    "红烧肉菜谱",
                    "五花肉切块，冰糖炒糖色，小火慢炖一小时。",
                ),
                (f"{tag}-a2", "p0-user-a", "读书笔记", "检索平面统一，笔记正文进知识图谱。"),
                (f"{tag}-b1", "p0-user-b", "红烧肉秘方", "p0-user-b 的私房菜谱，绝不外传他人。"),
                (f"{tag}-a3", "p0-user-a", "过期清单", "这篇已软删除，红烧肉也不应被搜到。"),
            ]
            for nid, user, title, body in seeds:
                cur.execute(
                    "INSERT INTO stratum.notes_sl (id, user_id, title, content_markdown)"
                    " VALUES (%s, %s, %s, %s)",
                    (nid, user, title, body),
                )
            cur.execute(
                "UPDATE stratum.notes_sl SET deleted_at = NOW() WHERE id = %s", (f"{tag}-a3",)
            )
        yield raw, tag
    finally:
        try:
            with raw.cursor() as cur:
                cur.execute("DELETE FROM stratum.notes_sl WHERE id LIKE %s", (f"{tag}-%",))
        finally:
            raw.close()


# ── migration / index ──────────────────────────────────────────────────────


def test_migration_093_is_idempotent_and_creates_trgm_index(pg_notes):
    raw, _ = pg_notes
    with raw.cursor() as cur:
        cur.execute("SELECT extname FROM pg_extension WHERE extname = 'pg_trgm'")
        assert cur.fetchone(), "pg_trgm extension must be enabled"
        cur.execute(
            "SELECT indexname FROM pg_indexes"
            " WHERE schemaname = 'stratum' AND tablename = 'notes_sl'"
            " AND indexname = 'idx_notes_sl_title_body_trgm'"
        )
        assert cur.fetchone(), "093 must create idx_notes_sl_title_body_trgm"
        # Applying the file a third time stays a no-op (IF NOT EXISTS).
        cur.execute(MIGRATION_093.read_text(encoding="utf-8"))


# ── retrieval through KnowledgeView (scope="user-authored") ─────────────────


def _search(user_id: str, query: str = "红烧肉"):
    from stratum.services.knowledge_view import KnowledgeViewRequest, search_knowledge_view

    return search_knowledge_view(
        KnowledgeViewRequest(query=query, top_k=10, user_id=user_id, scopes=["user-authored"])
    )


def test_user_authored_scope_finds_own_note_body(pg_notes):
    from stratum.services.knowledge_view import validate_result_schema

    _, tag = pg_notes
    resp = _search("p0-user-a")
    ids = [r["id"] for r in resp["results"]]
    assert f"{tag}-a1" in ids, f"own note body must be searchable, got {ids}"
    for r in resp["results"]:
        assert r["type"] == "note"
        assert validate_result_schema(r) == [], f"schema violation: {r}"
        for field in ("id", "title", "type", "score", "snippet"):
            assert field in r, f"missing stable field {field}"
        assert r["snippet"], "snippet must be non-empty"
        assert r["citation"]["source_id"] == r["id"]
        assert r["provenance"]["source_id"] == r["id"]


def test_user_authored_scope_never_returns_other_users_notes(pg_notes):
    _, tag = pg_notes
    resp = _search("p0-user-a")
    ids = [r["id"] for r in resp["results"]]
    assert f"{tag}-b1" not in ids, "cross-user leak: another user's note was returned"
    resp_b = _search("p0-user-b")
    ids_b = [r["id"] for r in resp_b["results"]]
    assert f"{tag}-b1" in ids_b
    assert f"{tag}-a1" not in ids_b


def test_soft_deleted_notes_are_excluded(pg_notes):
    _, tag = pg_notes
    resp = _search("p0-user-a")
    ids = [r["id"] for r in resp["results"]]
    assert f"{tag}-a3" not in ids, "soft-deleted note must not be searchable"


def test_unauthenticated_user_authored_search_is_rejected(pg_notes):
    from stratum.services.knowledge_view import (
        KnowledgeViewInvariantError,
        KnowledgeViewRequest,
        search_knowledge_view,
    )

    with pytest.raises(KnowledgeViewInvariantError, match="authenticated user_id"):
        search_knowledge_view(KnowledgeViewRequest(query="红烧肉", scopes=["user-authored"]))


# ── pure unit tests (no DB) ────────────────────────────────────────────────


def test_note_search_terms_cover_cjk_bigrams():
    from stratum.services.knowledge_view import _note_search_terms

    terms = _note_search_terms("红烧肉 做法")
    assert "红烧肉" in terms
    assert "做法" in terms
    # bigrams give substring recall for CJK
    assert "红烧" in terms and "烧肉" in terms
    assert _note_search_terms("") == []
    assert _note_search_terms("a") == []


def test_validate_note_result_against_stable_schema():
    from stratum.services.knowledge_view import (
        KnowledgeViewResult,
        validate_knowledge_view_result,
    )

    def note(note_id: str = "n1") -> KnowledgeViewResult:
        return KnowledgeViewResult(
            id=note_id,
            title="t",
            type="note",
            score=0.8,
            snippet="s",
            citation={"source_id": note_id, "quote": "s"},
            provenance={"source_id": note_id, "projection": "notes_sl"},
        )

    # owner passes without needing a substrate_id
    assert validate_knowledge_view_result(note(), "alice", {"n1": "alice"}) == []
    # foreign owner is rejected
    assert validate_knowledge_view_result(note(), "alice", {"n1": "mallory"})
    # missing citation / provenance are rejected
    bad = note()
    bad.citation = None
    bad.provenance = None
    errors = validate_knowledge_view_result(bad, "alice", {"n1": "alice"})
    assert "result missing valid citation" in errors
    assert "result missing valid provenance" in errors
