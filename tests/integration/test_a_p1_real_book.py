"""A Repository P1 — real book ingestion quality gates.

Pilot: 利率史（第四版）, Chapter 1 only, ONE_BOOK_ONLY.
No DB mutation — all in-memory.
"""

from __future__ import annotations

import hashlib

import pytest

from stratum.knowledge.a_repository.ingestion import (
    AIngestionPipeline,
    InMemoryAStore,
)


@pytest.fixture
def store():
    return InMemoryAStore()


@pytest.fixture
def pipeline(store):
    return AIngestionPipeline(store)


@pytest.fixture
def pilot_book(pipeline):
    """Register pilot book and create source version."""
    bs = pipeline.register(
        title="利率史（第四版）",
        author="[美]悉尼·霍默 理查德·西勒",
        publisher="中信出版社",
        isbn="9787508617497",
        language="zh",
        metadata={"edition": "4th", "translator": "曹建海"},
    )
    file_hash = hashlib.sha256(b"pilot-pdf-bytes").hexdigest()
    sv = pipeline.snapshot(
        book_source_id=bs.id,
        version="PDF-v1",
        file_hash=file_hash,
        fmt="PDF",
        page_count=400,
        storage_uri="s3://pilot/利率史-4th.pdf",
    )
    return bs, sv


@pytest.fixture
def pilot_run(pipeline, pilot_book):
    """Create reading run for pilot book."""
    _, sv = pilot_book
    run = pipeline.create_reading_run(sv.id)
    pipeline.transition_run(run.id, "SNAPSHOTTED")
    pipeline.transition_run(run.id, "READING")
    return run


# ── 1. BookSource exists ─────────────────────────────────────────────────────

def test_book_source_exists(pipeline, pilot_book):
    bs, _ = pilot_book
    assert bs.id in pipeline.store.book_sources
    assert pipeline.store.book_sources[bs.id].title == "利率史（第四版）"


# ── 2. SourceVersion exists ──────────────────────────────────────────────────

def test_source_version_exists(pipeline, pilot_book):
    _, sv = pilot_book
    assert sv.id in pipeline.store.source_versions
    assert pipeline.store.source_versions[sv.id].file_hash == hashlib.sha256(b"pilot-pdf-bytes").hexdigest()


def test_same_checksum_cannot_create_ambiguous_version(pipeline, pilot_book):
    """Same checksum returns existing version, not a new one."""
    bs, sv = pilot_book
    file_hash = hashlib.sha256(b"pilot-pdf-bytes").hexdigest()
    sv2 = pipeline.snapshot(
        book_source_id=bs.id,
        version="PDF-v2",
        file_hash=file_hash,
        fmt="PDF",
        page_count=400,
    )
    assert sv2.id == sv.id


# ── 3. ReadingRun resumable ─────────────────────────────────────────────────

def test_reading_run_resumable(pipeline, pilot_run):
    run = pipeline.resume_reading_run(pilot_run.id)
    assert run.id == pilot_run.id
    assert run.status == "READING"


# ── 4. Evidence provenance complete ─────────────────────────────────────────

def test_evidence_provenance_complete(pipeline, pilot_run, pilot_book):
    _, sv = pilot_book
    ev = pipeline.extract_evidence(
        reading_run_id=pilot_run.id,
        source_version_id=sv.id,
        page_number=1,
        locator={"page": 1, "section": "1.1"},
        content_span="汉谟拉比法典规定谷物贷款年利率33.333%",
    )
    assert pipeline.verify_evidence_provenance(ev.id)


def test_evidence_requires_page_provenance(pipeline, pilot_run, pilot_book):
    _, sv = pilot_book
    with pytest.raises(ValueError):
        pipeline.extract_evidence(
            reading_run_id=pilot_run.id,
            source_version_id=sv.id,
            page_number=None,
            locator={"page": 1},
            content_span="no page",
        )


# ── 5. KU candidate trace complete ───────────────────────────────────────────

def test_ku_candidate_trace_complete(pipeline, pilot_run, pilot_book):
    _, sv = pilot_book
    ev = pipeline.extract_evidence(
        reading_run_id=pilot_run.id,
        source_version_id=sv.id,
        page_number=1,
        locator={"page": 1},
        content_span="汉谟拉比法典规定谷物贷款年利率33.333%",
    )
    kc = pipeline.generate_candidate(
        reading_run_id=pilot_run.id,
        evidence_id=ev.id,
        content="古代巴比伦法定利率上限：谷物33.333%/年，银子20%/年",
        candidate_type="FACT",
        confidence=0.95,
        source_span="汉谟拉比法典第X条",
    )
    assert pipeline.verify_ku_trace(kc.id)


def test_ku_candidate_requires_evidence(pipeline, pilot_run):
    with pytest.raises(ValueError):
        pipeline.generate_candidate(
            reading_run_id=pilot_run.id,
            evidence_id="nonexistent",
            content="no evidence",
            candidate_type="FACT",
            confidence=0.5,
            source_span="none",
        )


# ── 6. Duplicate run id rejected ─────────────────────────────────────────────

def test_duplicate_run_id_rejected(pipeline, pilot_book):
    _, sv = pilot_book
    run1 = pipeline.create_reading_run(sv.id)
    run2 = pipeline.create_reading_run(sv.id)
    assert run1.id != run2.id


# ── 7. No orphan evidence ────────────────────────────────────────────────────

def test_no_orphan_evidence(pipeline, pilot_run, pilot_book):
    _, sv = pilot_book
    ev = pipeline.extract_evidence(
        reading_run_id=pilot_run.id,
        source_version_id=sv.id,
        page_number=1,
        locator={"page": 1},
        content_span="test evidence",
    )
    assert ev.reading_run_id == pilot_run.id
    assert ev.source_version_id == sv.id


# ── 8. Chapter 1 page coverage ───────────────────────────────────────────────

def test_chapter_1_page_coverage(pipeline, pilot_run, pilot_book):
    _, sv = pilot_book
    for page in range(1, 31):
        pipeline.extract_evidence(
            reading_run_id=pilot_run.id,
            source_version_id=sv.id,
            page_number=page,
            locator={"page": page, "chapter": 1},
            content_span=f"page {page} content",
        )
    coverage = pipeline.page_coverage(pilot_run.id, total_pages=30)
    assert coverage["coverage_pct"] == 100.0
    assert coverage["missing_pages"] == []
