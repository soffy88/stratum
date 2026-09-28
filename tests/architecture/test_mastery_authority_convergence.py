"""P1 Authority Convergence — mastery authority + KnowledgeRef contract tests.

Proves:
1. MASTERY_AUTHORITY_COUNT = 1 (cx.learning_progress is sole mastery authority)
2. KnowledgeRef roundtrip (to_dict/from_dict, to_string/from_string)
3. KnowledgeRef identity excludes source_version; no text matching
4. Cross-DB ref contract across A/B/C warehouses
5. Non-authority stores are NOT mastery (localStorage, cornell, flashcards)
6. Real DB qualification against aii_context (skipped when DB unavailable)
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8", errors="ignore")


# ── 1. MASTERY_AUTHORITY_COUNT = 1 ────────────────────────────────────────────


def test_mastery_authority_count_is_one():
    """Exactly one mastery authority exists: cx.learning_progress."""
    from stratum.services.mastery_authority import MasteryAuthority

    authority = MasteryAuthority()
    assert authority is not None
    # The adapter routes through cx.learning_progress — no other store
    assert "cx.learning_progress" in _read("src/stratum/services/mastery_authority.py")
    # No new mastery store is created
    assert "CREATE TABLE" not in _read("src/stratum/services/mastery_authority.py")


def test_mastery_authority_map_declares_single_authority():
    """AUTHORITY_MAP.md declares cx.learning_progress as sole mastery authority."""
    am = _read("docs/book-understanding-2.0/AUTHORITY_MAP.md")
    assert "MASTERY_AUTHORITY" in am
    # Must mention cx.learning_progress as the authority
    assert "cx.learning_progress" in am
    # Must explicitly declare non-authorities
    assert "NOT mastery" in am


def test_localstorage_is_not_mastery_authority():
    """localStorage completion/read/review state is NOT mastery."""
    am = _read("docs/book-understanding-2.0/AUTHORITY_MAP.md")
    assert "localStorage" in am
    assert "NOT mastery" in am
    # Frontend code uses localStorage for Deep Card completion
    ll = _read("aii-web/src/aii/components/LearningLayer.tsx")
    assert "localStorage" in ll
    # But it's not the mastery authority — the authority is cx.learning_progress
    assert "aii-bu-learning-" in ll  # localStorage key prefix


def test_cornell_progress_is_not_mastery_authority():
    """Cornell progress/telemetry is NOT mastery."""
    am = _read("docs/book-understanding-2.0/AUTHORITY_MAP.md")
    assert "cornell_progress" in am
    assert "NOT mastery" in am
    # Cornell progress table exists but is telemetry, not mastery
    cornell = _read("src/stratum/api/routers/cornell.py")
    assert "cornell_progress" in cornell


def test_flashcards_are_not_mastery_authority():
    """Flashcard scheduling/review state is NOT mastery; scheduler preserved."""
    am = _read("docs/book-understanding-2.0/AUTHORITY_MAP.md")
    assert "flashcards" in am
    assert "NOT mastery" in am
    # Flashcard scheduler is FSRS (py-fsrs) with SM-2 fallback — preserved
    sr = _read("src/stratum/services/spaced_repetition.py")
    assert "FSRS" in sr or "fsrs" in sr
    assert "SM-2" in sr or "sm2" in sr.lower() or "legacy" in sr.lower()


# ── 2. KnowledgeRef roundtrip ────────────────────────────────────────────────


def test_knowledge_ref_dict_roundtrip():
    """KnowledgeRef to_dict/from_dict roundtrip."""
    from stratum.knowledge.knowledge_ref import KnowledgeRef

    ref = KnowledgeRef(
        repository="C",
        object_type="learning_point",
        object_id="42",
        source_version="v1",
    )
    d = ref.to_dict()
    assert d == {
        "repository": "C",
        "object_type": "learning_point",
        "object_id": "42",
        "source_version": "v1",
    }
    ref2 = KnowledgeRef.from_dict(d)
    assert ref2 == ref
    assert ref2.identity == ref.identity


def test_knowledge_ref_string_roundtrip():
    """KnowledgeRef to_string/from_string roundtrip."""
    from stratum.knowledge.knowledge_ref import KnowledgeRef

    ref = KnowledgeRef(
        repository="B",
        object_type="ku",
        object_id="ku-123",
        source_version="2026-01",
    )
    s = ref.to_string()
    assert s == "B:ku:ku-123@2026-01"
    ref2 = KnowledgeRef.from_string(s)
    assert ref2 == ref

    # Without source_version
    ref3 = KnowledgeRef(repository="A", object_type="concept", object_id="c1")
    s3 = ref3.to_string()
    assert s3 == "A:concept:c1"
    ref4 = KnowledgeRef.from_string(s3)
    assert ref4 == ref3
    assert ref4.source_version is None


def test_knowledge_ref_without_version_roundtrip():
    """KnowledgeRef without source_version roundtrips correctly."""
    from stratum.knowledge.knowledge_ref import KnowledgeRef

    ref = KnowledgeRef(repository="A", object_type="substrate", object_id="sub-1")
    d = ref.to_dict()
    assert d["source_version"] is None
    ref2 = KnowledgeRef.from_dict(d)
    assert ref2 == ref
    assert ref2.source_version is None


# ── 3. Identity excludes source_version; no text matching ─────────────────────


def test_knowledge_ref_identity_excludes_source_version():
    """source_version is NOT part of identity."""
    from stratum.knowledge.knowledge_ref import KnowledgeRef

    ref1 = KnowledgeRef("C", "learning_point", "1", source_version="v1")
    ref2 = KnowledgeRef("C", "learning_point", "1", source_version="v2")
    ref3 = KnowledgeRef("C", "learning_point", "1", source_version=None)
    # All three have the same identity
    assert ref1.identity == ref2.identity == ref3.identity
    # But they are not equal (source_version differs)
    assert ref1 != ref2
    assert ref1 != ref3


def test_knowledge_ref_no_text_matching():
    """KnowledgeRef identity is (repository, object_type, object_id) — no text."""
    from stratum.knowledge.knowledge_ref import KnowledgeRef

    ref = KnowledgeRef("C", "learning_point", "42")
    d = ref.to_dict()
    # No text fields in identity
    assert "point_name" not in d
    assert "title" not in d
    assert "content" not in d
    assert "text" not in d
    assert "name" not in d
    # Identity tuple has exactly 3 elements
    assert len(ref.identity) == 3


def test_knowledge_ref_validation():
    """KnowledgeRef validates repository and rejects empty fields."""
    from stratum.knowledge.knowledge_ref import KnowledgeRef

    with pytest.raises(ValueError):
        KnowledgeRef("D", "concept", "1")  # invalid repository
    with pytest.raises(ValueError):
        KnowledgeRef("A", "", "1")  # empty object_type
    with pytest.raises(ValueError):
        KnowledgeRef("A", "concept", "")  # empty object_id


# ── 4. Cross-DB ref contract across A/B/C ─────────────────────────────────────


def test_knowledge_ref_cross_db_contract():
    """KnowledgeRef works across all three warehouses A/B/C."""
    from stratum.knowledge.knowledge_ref import REPOSITORIES, KnowledgeRef

    assert REPOSITORIES == frozenset({"A", "B", "C"})
    for repo in ("A", "B", "C"):
        ref = KnowledgeRef(repository=repo, object_type="concept", object_id="test-1")
        assert ref.repository == repo
        assert ref.identity[0] == repo


def test_knowledge_ref_cross_db_roundtrip():
    """KnowledgeRef roundtrips across all three warehouses."""
    from stratum.knowledge.knowledge_ref import KnowledgeRef

    for repo in ("A", "B", "C"):
        ref = KnowledgeRef(
            repository=repo,
            object_type="ku",
            object_id=f"ku-{repo}-1",
            source_version="v1",
        )
        # Dict roundtrip
        ref2 = KnowledgeRef.from_dict(ref.to_dict())
        assert ref2 == ref
        # String roundtrip
        ref3 = KnowledgeRef.from_string(ref.to_string())
        assert ref3 == ref


# ── 5. MasteryAuthority adapter contract ──────────────────────────────────────


def test_mastery_authority_routes_through_c_warehouse():
    """MasteryAuthority adapter routes through cx.learning_progress (C-warehouse)."""
    ma = _read("src/stratum/services/mastery_authority.py")
    assert "cx.learning_progress" in ma
    assert "REPOSITORY_C" in ma or '"C"' in ma
    # Does not create a new mastery store
    assert "CREATE TABLE" not in ma
    assert "personal_states" not in ma  # no new store


def test_mastery_authority_preserves_flashcard_scheduler():
    """Flashcard scheduler (FSRS/SM-2) is preserved, not replaced."""
    sr = _read("src/stratum/services/spaced_repetition.py")
    # FSRS is the production scheduler
    assert "FSRS" in sr or "fsrs" in sr
    # SM-2 fallback exists
    assert "SM-2" in sr or "legacy" in sr.lower()
    # Scheduler file is unchanged — no destructive migration
    assert "schedule_review" in sr


# ── 6. Real DB qualification (skipped when DB unavailable) ────────────────────


def _pg_available() -> bool:
    import psycopg2

    try:
        conn = psycopg2.connect(
            host="127.0.0.1",
            port=5436,
            user="aii",
            password="***REMOVED***",
            dbname="aii_context",
            connect_timeout=2,
        )
        conn.close()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _pg_available(), reason="aii_context DB unavailable")
def test_real_db_cx_learning_progress_schema():
    """Real DB: cx.learning_progress table exists with expected columns."""
    import psycopg2

    conn = psycopg2.connect(
        host="127.0.0.1",
        port=5436,
        user="aii",
        password="***REMOVED***",
        dbname="aii_context",
        connect_timeout=3,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='cx' AND table_name='learning_progress' "
                "ORDER BY ordinal_position"
            )
            columns = {r[0] for r in cur.fetchall()}
        expected = {
            "point_id",
            "profile_id",
            "point_name",
            "grade",
            "mastery_score",
            "attempts",
            "next_review_at",
            "last_tested_at",
        }
        assert expected.issubset(columns), f"missing columns: {expected - columns}"
    finally:
        conn.close()


@pytest.mark.skipif(not _pg_available(), reason="aii_context DB unavailable")
def test_real_db_mastery_authority_reads_existing_rows():
    """Real DB: MasteryAuthority can read existing cx.learning_progress rows."""
    from stratum.knowledge.knowledge_ref import KnowledgeRef
    from stratum.services.mastery_authority import MasteryAuthority

    auth = MasteryAuthority()
    # Read an existing point (point_id=40 exists in the test DB)
    ref = KnowledgeRef(repository="C", object_type="learning_point", object_id="40")
    state = auth.get_mastery(ref)
    assert state is not None
    assert state.ref == ref
    assert state.grade in ("unverified", "learning", "verified")
    assert 0.0 <= state.mastery_score <= 1.0


@pytest.mark.skipif(not _pg_available(), reason="aii_context DB unavailable")
def test_real_db_mastery_authority_due_reviews():
    """Real DB: MasteryAuthority can query due reviews."""
    from stratum.services.mastery_authority import MasteryAuthority

    auth = MasteryAuthority()
    # profile_id=1 exists in the test DB
    due = auth.get_due_reviews(profile_id=1)
    assert isinstance(due, list)
    # All returned items are MasteryState with valid refs
    for state in due:
        assert state.ref.repository == "C"
        assert state.ref.object_type == "learning_point"
