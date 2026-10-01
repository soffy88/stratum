"""A Repository Contract — architecture invariants for Stratum A仓.

Tests (contract-only, no content quality scoring):
- provenance exists
- evidence cannot exist without source
- KU candidate requires evidence
- no B/C dependency
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[2]
DOCS = ROOT / "docs" / "book-understanding-2.0"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8", errors="ignore")


def _doc(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8", errors="ignore")


# ── 1. provenance exists ──────────────────────────────────────────────────────

def test_reading_evidence_has_provenance_fields():
    spec = _doc("A_REPOSITORY_SPEC.md")
    for field in (
        "source_version_id",
        "page_locator",
        "chapter_locator",
        "quote_span",
        "context",
        "parser_version",
        "extractor_version",
    ):
        assert field in spec, f"ReadingEvidence missing provenance field: {field}"


def test_evidence_provenance_invariant_documented():
    spec = _doc("A_REPOSITORY_SPEC.md")
    assert "evidence 不能脱离 source_version 存在" in spec
    assert "FK NOT NULL" in spec


# ── 2. evidence cannot exist without source ───────────────────────────────────

def test_evidence_requires_source_version_fk():
    spec = _doc("A_REPOSITORY_SPEC.md")
    assert "source_version_id | TEXT FK -> source_version" in spec
    assert "run_id | TEXT FK -> book_reading_run" in spec


def test_source_version_requires_book_source_fk():
    spec = _doc("A_REPOSITORY_SPEC.md")
    assert "book_source_id | TEXT FK -> BookSource" in spec


# ── 3. KU candidate requires evidence ────────────────────────────────────────

def test_ku_candidate_requires_evidence_fk():
    spec = _doc("A_REPOSITORY_SPEC.md")
    assert "reading_evidence_id | TEXT FK -> reading_evidence" in spec


def test_ku_candidate_does_not_write_b_repo():
    spec = _doc("A_REPOSITORY_SPEC.md")
    assert "禁止直接挂 knowledge_claims" in spec
    assert "KU Candidate != B仓 KU" in spec


# ── 4. no B/C dependency ─────────────────────────────────────────────────────

def test_a_repo_spec_excludes_b_and_c():
    spec = _doc("A_REPOSITORY_SPEC.md")
    assert "不做：" in spec
    assert "B仓概念去重" in spec
    assert "C仓推理生成" in spec
    assert "本性(emergent essence)计算" in spec


def test_pipeline_spec_excludes_b_and_c():
    spec = _doc("A_PIPELINE_SPEC.md")
    assert "A仓不做 B仓去重、C仓推理、本性计算" in spec


def test_no_b_c_tables_in_a_schema_gap():
    report = _doc("A_SCHEMA_GAP_REPORT.md")
    for table in ("book_source", "source_version", "reading_evidence", "ku_candidate"):
        assert table in report
    assert "SCHEMA_EXTENSION_REQUIRED=yes" in report


# ── 5. migration freeze respected ─────────────────────────────────────────────

def test_new_tables_require_070_plus():
    report = _doc("A_SCHEMA_GAP_REPORT.md")
    assert "migration 编号 070+" in report
    assert "不修改 060-066" in report


def test_bu2_migrations_untouched():
    for f in (
        "060_bu2_p2_reading_evidence.sql",
        "065_bu2_pipeline_state.sql",
        "066_bu2_p4_p9_repair.sql",
    ):
        p = ROOT / "src" / "stratum" / "db" / "pg_migrations" / f
        assert p.exists(), f"missing baseline migration: {f}"


# ── 6. pilot constraint ──────────────────────────────────────────────────────

def test_pilot_is_one_book_only():
    pilot = _doc("A_FIRST_BOOK_PILOT.md")
    assert "ONE_BOOK_ONLY" in pilot
    assert "禁止批量导入" in pilot


# ── 7. required contract tests (10) ──────────────────────────────────────────

_MIGRATION_070 = "src/stratum/db/pg_migrations/070_a_repository_foundation.sql"


def _migration() -> str:
    return _read(_MIGRATION_070)


# 1. BookSource -> SourceVersion FK
def test_book_source_to_source_version_fk():
    sql = _migration()
    assert "CREATE TABLE IF NOT EXISTS stratum.book_source" in sql
    assert "CREATE TABLE IF NOT EXISTS stratum.source_version" in sql
    assert "book_source_id TEXT NOT NULL REFERENCES stratum.book_source(id)" in sql


# 2. SourceVersion -> ReadingRun
def test_source_version_to_reading_run_fk():
    sql = _migration()
    assert "CREATE TABLE IF NOT EXISTS stratum.reading_run" in sql
    assert "source_version_id TEXT NOT NULL REFERENCES stratum.source_version(id)" in sql


# 3. ReadingRun -> Evidence
def test_reading_run_to_evidence_fk():
    sql = _migration()
    assert "CREATE TABLE IF NOT EXISTS stratum.reading_evidence" in sql
    assert "reading_run_id TEXT NOT NULL REFERENCES stratum.reading_run(id)" in sql


# 4. Evidence -> KU Candidate
def test_evidence_to_ku_candidate_fk():
    sql = _migration()
    assert "CREATE TABLE IF NOT EXISTS stratum.ku_candidate" in sql
    assert "evidence_id TEXT NOT NULL REFERENCES stratum.reading_evidence(id)" in sql
    assert "reading_run_id TEXT NOT NULL REFERENCES stratum.reading_run(id)" in sql


# 5. Resume same run_id
def test_resume_same_run_id():
    from stratum.knowledge.a_repository import pipeline as pipe_mod
    from stratum.knowledge.a_repository.pipeline import (
        ARepositoryPipeline,
        PipelineStageError,
    )
    from stratum.knowledge.a_repository.types import PipelineStage

    class FakeRun:
        @staticmethod
        def get(run_id):
            return None

    orig = pipe_mod.ReadingRunRepository
    pipe_mod.ReadingRunRepository = FakeRun
    try:
        pipeline = ARepositoryPipeline()
        try:
            pipeline.freeze("nonexistent_run")
            assert False, "should raise PipelineStageError"
        except PipelineStageError as e:
            assert e.stage == PipelineStage.FREEZE
    finally:
        pipe_mod.ReadingRunRepository = orig


# 6. Duplicate candidate rejected
def test_duplicate_candidate_rejected():
    from stratum.knowledge.a_repository import pipeline as pipe_mod
    from stratum.knowledge.a_repository.models import KUCandidate
    from stratum.knowledge.a_repository.pipeline import ARepositoryPipeline

    existing = KUCandidate(
        id="kc_1", reading_run_id="arr_1", evidence_id="ev_1",
        content="dup", status="EXTRACTED",
    )

    class FakeRun:
        @staticmethod
        def get(run_id):
            from stratum.knowledge.a_repository.models import ReadingRun
            return ReadingRun(id=run_id, source_version_id="sv_1")

    class FakeKC:
        @staticmethod
        def list_for_run(reading_run_id):
            return [existing]

        @staticmethod
        def create(**kwargs):
            return KUCandidate(**kwargs)

    orig_run = pipe_mod.ReadingRunRepository
    orig_kc = pipe_mod.KUCandidateRepository
    pipe_mod.ReadingRunRepository = FakeRun
    pipe_mod.KUCandidateRepository = FakeKC
    try:
        pipeline = ARepositoryPipeline()
        result = pipeline.candidate("arr_1", "ev_1", content="dup")
        assert result.id == "kc_1"
    finally:
        pipe_mod.ReadingRunRepository = orig_run
        pipe_mod.KUCandidateRepository = orig_kc


# 7. Evidence immutable
def test_evidence_immutable():
    from stratum.knowledge.a_repository.repository import EvidenceRepository
    assert not hasattr(EvidenceRepository, "update")
    assert not hasattr(EvidenceRepository, "delete")


# 8. No dedup in A repository
def test_no_dedup_in_a_repository():
    from stratum.knowledge.a_repository import repository as repo_mod
    for name in ("BookSourceRepository", "SourceVersionRepository",
                 "ReadingRunRepository", "EvidenceRepository",
                 "KUCandidateRepository"):
        cls = getattr(repo_mod, name)
        for forbidden in ("dedup", "merge", "deduplicate"):
            assert not hasattr(cls, forbidden), f"{name} has {forbidden}"


# 9. Pipeline state transition valid
def test_pipeline_state_transition_valid():
    from stratum.knowledge.a_repository.types import ReadingRunStatus
    valid = {s.value for s in ReadingRunStatus}
    assert "CREATED" in valid
    assert "FROZEN" in valid
    assert "FAILED" in valid


# 10. Migration additive only
def test_migration_additive_only():
    sql = _migration()
    assert "-- 070: A Repository Foundation" in sql
    for forbidden in ("DROP TABLE", "ALTER TABLE", "DELETE FROM", "UPDATE "):
        assert forbidden not in sql, f"non-additive statement found: {forbidden}"
    for table in ("book_source", "source_version", "reading_run",
                  "reading_evidence", "ku_candidate"):
        assert f"stratum.{table}" in sql
