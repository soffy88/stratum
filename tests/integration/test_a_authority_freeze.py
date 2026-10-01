"""A Repository P1 — authority freeze gates for the frozen real-book chain.

Three gates:
- Phase 1 PROVENANCE: every evidence/candidate traceable, no orphans.
- Phase 2 REPLAY: same checksum replay creates no duplicate objects.
- Phase 3 AUTHORITY: append-only; no evidence overwrite, no candidate
  overwrite, no automatic merge.

No DB mutation — all in-memory via freeze_runner.
"""

from __future__ import annotations

import pytest

from stratum.knowledge.a_repository import pilot_corpus as C
from stratum.knowledge.a_repository.freeze_runner import build_baseline, inventory
from stratum.knowledge.a_repository.ingestion import AuthorityViolation


@pytest.fixture(scope="module")
def frozen():
    return build_baseline()


@pytest.fixture(scope="module")
def inv(frozen):
    return inventory(frozen)


# ══ Phase 1: PROVENANCE AUDIT ═══════════════════════════════════════════════

def test_reading_evidence_has_full_provenance(frozen):
    """Every evidence row carries run, version, page, locator, span."""
    p = frozen["pipeline"]
    run_id = frozen["reading_run_id"]
    assert p.evidence_count(run_id) == len(C.EVIDENCE)

    for ev in p.store.evidence.values():
        assert ev.reading_run_id, "evidence missing reading_run_id"
        assert ev.source_version_id, "evidence missing source_version_id"
        assert isinstance(ev.page_number, int) and ev.page_number >= 1, \
            "evidence missing valid page_number"
        assert ev.locator, "evidence missing locator"
        assert ev.content_span, "evidence missing content_span"
        assert ev.extractor_version, "evidence missing extractor_version"


def test_ku_candidate_has_full_trace(frozen):
    """Every candidate carries evidence, run, and confidence."""
    p = frozen["pipeline"]
    run_id = frozen["reading_run_id"]
    assert p.candidate_count(run_id) == len(C.KU_CANDIDATES)

    for kc in p.store.ku_candidates.values():
        assert kc.evidence_id, "candidate missing evidence_id"
        assert kc.reading_run_id, "candidate missing reading_run_id"
        assert kc.confidence is not None, "candidate missing confidence"
        assert 0.0 <= kc.confidence <= 1.0, "confidence out of range"
        assert kc.source_span, "candidate missing source_span"


def test_every_candidate_points_at_real_evidence(frozen):
    p = frozen["pipeline"]
    for kc in p.store.ku_candidates.values():
        assert kc.evidence_id in p.store.evidence, "dangling evidence_id"


def test_no_orphan_evidence(frozen, inv):
    assert inv["orphan_evidence"] == []


def test_no_orphan_candidates(frozen, inv):
    assert inv["orphan_candidates"] == []


def test_every_evidence_has_verified_provenance(frozen):
    p = frozen["pipeline"]
    for ev_id in p.store.evidence:
        assert p.verify_evidence_provenance(ev_id), f"{ev_id} failed provenance"


def test_every_candidate_verified_trace(frozen):
    p = frozen["pipeline"]
    for kc_id in p.store.ku_candidates:
        assert p.verify_ku_trace(kc_id), f"{kc_id} failed trace"


def test_chapter_1_full_page_coverage(inv):
    cov = inv["page_coverage"]
    assert cov["total_pages"] == C.CHAPTER_PAGE_COUNT
    assert cov["coverage_pct"] == 100.0
    assert cov["missing_pages"] == []


# ══ Phase 2: REPLAY ═════════════════════════════════════════════════════════

def test_replay_same_checksum_no_duplicate_version(frozen):
    """Same PDF checksum must resolve to the existing SourceVersion."""
    p = frozen["pipeline"]
    again = p.snapshot(
        book_source_id=frozen["book_source"].id,
        version=C.FILE_VERSION,
        file_hash=C.CHECKSUM,
        fmt=C.SOURCE_FORMAT,
        page_count=C.FULL_PAGE_COUNT,
    )
    assert again.id == frozen["source_version_id"]
    assert len(p.store.source_versions) == 1


def test_replay_generates_no_duplicate_evidence(frozen):
    """Replaying evidence extraction must be a no-op."""
    p = frozen["pipeline"]
    run_id = frozen["reading_run_id"]
    before = p.evidence_fingerprint(run_id)
    before_count = p.evidence_count(run_id)

    replayed = 0
    for item in C.EVIDENCE:
        if p.has_evidence(run_id, item["page_number"], item["content_span"]):
            replayed += 1
            continue
        p.extract_evidence(
            reading_run_id=run_id,
            source_version_id=frozen["source_version_id"],
            page_number=item["page_number"],
            locator={"page": item["page_number"], "section": item["section"]},
            content_span=item["content_span"],
            extractor_version=item["extractor_version"],
        )

    assert replayed == len(C.EVIDENCE), "replay should skip all existing evidence"
    assert p.evidence_count(run_id) == before_count, "replay duplicated evidence"
    assert p.evidence_fingerprint(run_id) == before, "evidence fingerprint drifted"


def test_replay_generates_no_duplicate_candidates(frozen):
    p = frozen["pipeline"]
    run_id = frozen["reading_run_id"]
    before = p.candidate_count(run_id)

    replayed = 0
    ev_ids = frozen["evidence_ids"]
    for item in C.KU_CANDIDATES:
        ev_id = ev_ids[item["evidence_key"]]
        if p.has_candidate(run_id, ev_id, item["source_span"]):
            replayed += 1
            continue
        p.generate_candidate(
            reading_run_id=run_id,
            evidence_id=ev_id,
            content=item["content"],
            candidate_type=item["candidate_type"],
            confidence=item["confidence"],
            source_span=item["source_span"],
        )

    assert replayed == len(C.KU_CANDIDATES), "replay should skip all existing candidates"
    assert p.candidate_count(run_id) == before, "replay duplicated candidates"


def test_replay_resumes_existing_reading_run(frozen):
    p = frozen["pipeline"]
    run_id = frozen["reading_run_id"]
    resumed = p.resume_reading_run(run_id)
    assert resumed.id == run_id
    assert resumed.status == "READING"
    assert len(p.store.reading_runs) == 1


def test_baseline_is_reproducible():
    """Two independent executions produce identical IDs and counts."""
    a, b = inventory(build_baseline()), inventory(build_baseline())
    for key in ("book_source", "source_version", "reading_run"):
        assert a[key] == b[key], f"{key} not reproducible"
    assert a["evidence_count"] == b["evidence_count"]
    assert a["ku_candidate_count"] == b["ku_candidate_count"]
    assert a["evidence_ids"] == b["evidence_ids"]
    assert a["candidate_ids"] == b["candidate_ids"]


# ══ Phase 3: A仓 AUTHORITY FREEZE ═══════════════════════════════════════════

def test_a_repository_allows_new_evidence(frozen):
    """A仓 permits appending new evidence."""
    p = frozen["pipeline"]
    run_id = frozen["reading_run_id"]
    before = p.evidence_count(run_id)
    ev = p.extract_evidence(
        reading_run_id=run_id,
        source_version_id=frozen["source_version_id"],
        page_number=11,
        locator={"page": 11, "note": "append-only check"},
        content_span="追加证据行",
        extractor_version="p1-v1",
    )
    assert p.evidence_count(run_id) == before + 1
    assert p.verify_evidence_provenance(ev.id)


def test_a_repository_allows_new_candidate(frozen):
    """A仓 permits appending new KU candidates."""
    p = frozen["pipeline"]
    run_id = frozen["reading_run_id"]
    before = p.candidate_count(run_id)
    any_ev = next(iter(p.store.evidence))
    kc = p.generate_candidate(
        reading_run_id=run_id,
        evidence_id=any_ev,
        content="追加候选",
        candidate_type="FACT",
        confidence=0.5,
        source_span="append-only check",
    )
    assert p.candidate_count(run_id) == before + 1
    assert p.verify_ku_trace(kc.id)


def test_a_repository_forbids_evidence_overwrite(frozen):
    p = frozen["pipeline"]
    ev_id = next(iter(p.store.evidence))
    with pytest.raises(AuthorityViolation):
        p.overwrite_evidence(ev_id, content_span="篡改的证据")


def test_a_repository_forbids_candidate_overwrite(frozen):
    p = frozen["pipeline"]
    kc_id = next(iter(p.store.ku_candidates))
    with pytest.raises(AuthorityViolation):
        p.overwrite_candidate(kc_id, content="覆盖旧候选")


def test_a_repository_forbids_auto_merge(frozen):
    p = frozen["pipeline"]
    ids = list(p.store.ku_candidates)[:2]
    with pytest.raises(AuthorityViolation):
        p.auto_merge_candidates(*ids)


def test_evidence_store_has_no_update_or_delete(frozen):
    """Structural guarantee: no mutation surface on evidence."""
    from stratum.knowledge.a_repository.repository import EvidenceRepository
    assert not hasattr(EvidenceRepository, "update")
    assert not hasattr(EvidenceRepository, "delete")


def test_no_dedup_merge_methods_on_candidate_repo():
    """No dedup/merge entry points on the candidate repository."""
    from stratum.knowledge.a_repository.repository import KUCandidateRepository
    for forbidden in ("dedup", "merge", "deduplicate", "auto_merge"):
        assert not hasattr(KUCandidateRepository, forbidden)


def test_no_knowledge_claims_dependency_in_a_repository():
    """A仓 must not reference the B仓 KU authority table."""
    import pathlib
    root = pathlib.Path(__file__).parents[2]
    pkg = root / "src" / "stratum" / "knowledge" / "a_repository"
    for py in pkg.glob("*.py"):
        text = py.read_text(encoding="utf-8")
        assert "knowledge_claims" not in text, f"{py.name} references B仓 table"


def test_070_migration_has_no_b_repo_dependency():
    """070 schema must not FK into B仓 tables."""
    import pathlib
    root = pathlib.Path(__file__).parents[2]
    sql = (root / "src" / "stratum" / "db" / "pg_migrations"
           / "070_a_repository_foundation.sql").read_text(encoding="utf-8")
    for forbidden in ("knowledge_claims", "evidence_trajectory", "book_reading_run"):
        assert f"REFERENCES stratum.{forbidden}" not in sql, \
            f"070 must not depend on {forbidden}"