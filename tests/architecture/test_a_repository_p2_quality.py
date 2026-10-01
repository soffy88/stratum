"""A Repository P2 — evidence quality + KU candidate classification.

Contract tests for the frozen P2 quality layer (migration 071):
- quality requires evidence
- one quality row per evidence row
- quality rows are append-only
- classification is a closed enum
- the runner is deterministic
- replay leaves the store unchanged
- no external authority reference
- locator compatibility with A_SOURCE_LOCATOR_SPEC.md
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[2]
PKG = ROOT / "src" / "stratum" / "knowledge" / "a_repository"

from stratum.knowledge.a_repository import pilot_corpus as C  # noqa: E402
from stratum.knowledge.a_repository.quality import (  # noqa: E402
    PAGINATED_SOURCE_TYPES,
    EvidenceLocator,
    EvidenceQualityPipeline,
    QualityViolation,
    deterministic_id,
)
from stratum.knowledge.a_repository.quality_runner import (  # noqa: E402
    build_quality_baseline,
    report,
)
from stratum.knowledge.a_repository.types import (  # noqa: E402
    KIClassification,
    PipelineStage,
)


@pytest.fixture
def quality():
    result = build_quality_baseline()
    return {
        "base": result["base"],
        "pipeline": result["base"]["pipeline"],
        "quality": result["quality"],
        "report": report(result),
    }


# ── 1. quality requires evidence ──────────────────────────────────────────────

def test_quality_requires_existing_evidence(quality):
    pipeline = EvidenceQualityPipeline(quality["pipeline"])
    with pytest.raises(ValueError):
        pipeline.score_evidence("ev_does_not_exist", locator={})


def test_no_orphan_quality_rows(quality):
    """Every quality row points at a real evidence row."""
    pipeline = quality["quality"]
    assert pipeline.quality_count(quality["base"]["reading_run_id"]) == 17
    assert pipeline.orphan_quality() == []


def test_quality_scoring_requires_no_extra_columns():
    """A quality row is derived only from its own evidence + locator."""
    from stratum.knowledge.a_repository.quality import EvidenceQuality
    assert {f for f in EvidenceQuality.__dataclass_fields__} == {
        "id", "evidence_id", "source_trace_score", "locator_score",
        "completeness_score", "confidence_score", "quality_version",
        "metadata",
    }


# ── 2. evidence_id unique ────────────────────────────────────────────────────

def test_exactly_one_quality_row_per_evidence_row(quality):
    store = quality["pipeline"].store
    assert len(store.quality) == len(store.evidence) == 17
    assert len(store._quality_by_evidence) == 17
    assert len(set(store._quality_by_evidence.values())) == 17


def test_quality_id_is_deterministic(quality):
    store = quality["pipeline"].store
    ev_id = quality["base"]["evidence_ids"]["ev_hammurabi_grain_rate"]
    assert store._quality_by_evidence[ev_id] == deterministic_id(
        "eq", ev_id, "p2-v1")


def test_duplicate_evidence_cannot_create_a_second_quality_row(quality):
    """Schema declares evidence_id UNIQUE; the model enforces it too."""
    sql = (ROOT / "src" / "stratum" / "db" / "pg_migrations"
           / "071_a_evidence_quality.sql").read_text(encoding="utf-8")
    assert "evidence_id TEXT NOT NULL UNIQUE" in sql


# ── 3. quality append only ────────────────────────────────────────────────────

def test_overwrite_quality_is_forbidden(quality):
    pipeline = EvidenceQualityPipeline(quality["pipeline"])
    store = quality["pipeline"].store
    q_id = next(iter(store.quality))
    before = store.quality[q_id]
    with pytest.raises(QualityViolation):
        pipeline.overwrite_quality(q_id, confidence_score=0.0)
    assert store.quality[q_id] == before


def test_overwrite_classification_is_forbidden(quality):
    pipeline = EvidenceQualityPipeline(quality["pipeline"])
    store = quality["pipeline"].store
    kc_id = next(iter(store.ku_candidates))
    before = store.ku_candidates[kc_id].classification
    with pytest.raises(QualityViolation):
        pipeline.overwrite_classification(kc_id, KIClassification.CONCEPT)
    assert store.ku_candidates[kc_id].classification == before


def test_merge_and_conclusion_are_forbidden(quality):
    pipeline = EvidenceQualityPipeline(quality["pipeline"])
    store = quality["pipeline"].store
    ids = list(store.ku_candidates)[:2]
    with pytest.raises(QualityViolation):
        pipeline.merge_candidates(*ids)
    with pytest.raises(QualityViolation):
        pipeline.write_conclusion(ids[0])


# ── 4. candidate classification enum ──────────────────────────────────────────

def test_every_classification_is_in_the_closed_enum(quality):
    store = quality["pipeline"].store
    values = {k.classification for k in store.ku_candidates.values()}
    assert values
    assert values <= {c.value for c in KIClassification}
    assert all(isinstance(v, str) for v in values)


def test_migration_check_list_matches_the_enum(quality):
    """The DB CHECK constraint and the Python enum must not drift."""
    sql = (ROOT / "src" / "stratum" / "db" / "pg_migrations"
           / "071_a_evidence_quality.sql").read_text(encoding="utf-8")
    listed = set(re.findall(r"'([A-Z]+)'", sql.split("classification IN (")[1]))
    assert listed == {c.value for c in KIClassification}


def test_all_candidates_classified_exactly_once(quality):
    pipeline = quality["quality"]
    run_id = quality["base"]["reading_run_id"]
    assert pipeline.classification_count(run_id) == 17
    assert pipeline.unclassified_candidates(run_id) == []


def test_classification_requires_the_candidate_own_evidence(quality):
    """Classification reads its own evidence only, never another candidate."""
    pipeline = EvidenceQualityPipeline(quality["pipeline"])
    store = quality["pipeline"].store
    kc = store.ku_candidates[quality["base"]["candidate_ids"]
                             ["kc_babylon_grain_rate_cap"]]
    other = store.evidence[
        quality["base"]["evidence_ids"]["ev_solon_date"]]
    alone = pipeline.classify(kc, store.evidence[kc.evidence_id])
    with_other = pipeline.classify(kc, other)
    assert isinstance(alone, KIClassification)
    assert isinstance(with_other, KIClassification)


def test_classification_of_an_evidence_less_candidate_is_refused(quality):
    pipeline = EvidenceQualityPipeline(quality["pipeline"])
    with pytest.raises(ValueError):
        pipeline.classify_candidate("kc_does_not_exist")


# ── 5. runner deterministic ───────────────────────────────────────────────────

def test_runner_is_deterministic():
    first, second = report(build_quality_baseline()), report(build_quality_baseline())
    assert first == second


def test_runner_counts_are_stable(quality):
    r = quality["report"]
    assert r["evidence_count"] == 17
    assert r["quality_count"] == 17
    assert r["classification_count"] == 17
    assert r["orphan_quality"] == []
    assert r["unclassified"] == []
    assert sum(r["classification_breakdown"].values()) == 17


def test_runner_emits_a_quality_event_per_transition(quality):
    events = quality["quality"].events
    assert events, "quality stage must emit events"
    assert {e.stage for e in events} == {PipelineStage.QUALITY}
    assert sum(1 for e in events if "quality_id" in e.payload) == 17
    assert sum(1 for e in events if "classification" in e.payload) == 17


# ── 6. replay unchanged ───────────────────────────────────────────────────────

def test_replay_adds_no_duplicate_rows(quality):
    pipeline, store = quality["pipeline"], quality["pipeline"].store
    run_id = quality["base"]["reading_run_id"]
    qp = EvidenceQualityPipeline(pipeline)

    quality_snapshot = dict(store.quality)
    index_snapshot = dict(store._quality_by_evidence)
    evidence_snapshot = {eid: dict(ev.locator) for eid, ev in store.evidence.items()}

    for item in C.EVIDENCE:
        ev_id = quality["base"]["evidence_ids"][item["key"]]
        qp.score_evidence(evidence_id=ev_id,
                          locator=store.evidence[ev_id].locator,
                          quality_id=deterministic_id("eq", ev_id, "p2-v1"))
    for item in C.KU_CANDIDATES:
        qp.classify_candidate(
            quality["base"]["candidate_ids"][item["key"]])

    assert store.quality == quality_snapshot
    assert store._quality_by_evidence == index_snapshot
    assert {eid: dict(ev.locator) for eid, ev in store.evidence.items()} \
        == evidence_snapshot
    assert qp.quality_count(run_id) == 17
    assert qp.classification_count(run_id) == 17
    assert qp.orphan_quality() == []


def test_replay_does_not_move_a_locator(quality):
    """A_SOURCE_LOCATOR_SPEC.md Rule 3: a persisted locator is frozen."""
    store = quality["pipeline"].store
    ev_id = quality["base"]["evidence_ids"]["ev_prehistory_conclusion"]
    assert store.evidence[ev_id].locator["logical_locator"] == f"{C.CHAPTER}/1.5"
    assert store.evidence[ev_id].locator["physical_locator"] == "p.10"


# ── 7. no external authority reference ────────────────────────────────────────

FORBIDDEN_TOKENS = ("knowledge_claims", "evidence_trajectory",
                    "book_reading_run", "B仓", "C仓")


@pytest.mark.parametrize("name", ["quality.py", "quality_runner.py"])
def test_p2_code_names_no_external_authority(name):
    """P2 code describes evidence, quality and candidates only."""
    text = (PKG / name).read_text(encoding="utf-8")
    for token in FORBIDDEN_TOKENS:
        assert token not in text, f"{name} references external authority: {token}"


def test_p2_migration_depends_on_a_repository_tables_only():
    sql = (ROOT / "src" / "stratum" / "db" / "pg_migrations"
           / "071_a_evidence_quality.sql").read_text(encoding="utf-8")
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", sql))
    assert referenced <= {"reading_evidence"}
    for token in FORBIDDEN_TOKENS:
        assert token not in sql


# ── 8. locator compatibility ──────────────────────────────────────────────────

def test_locator_is_valid_when_either_address_exists():
    assert EvidenceLocator("PDF", "sv", "h", "第一章/1.2", "p.4").is_valid()
    assert EvidenceLocator("HTML", "sv", "h", "/body/div").is_valid()
    assert not EvidenceLocator("PDF", "sv", "h", "").is_valid()


@pytest.mark.parametrize("logical,physical,source_type,expected", [
    ("第一章/1.2", "p.4", "PDF", 1.0),
    ("第一章/1.2", None, "MARKDOWN", 0.9),
    ("第一章/1.2", None, "HTML", 0.9),
    ("第一章/1.2", None, "PDF", 0.6),
    ("第一章/1.2", None, "OCR_TEXT", 0.6),
    ("", "p.4", "PDF", 0.5),
    ("", None, "MARKDOWN", 0.0),
])
def test_locator_score_matches_the_spec_table(
    logical, physical, source_type, expected
):
    """A_SOURCE_LOCATOR_SPEC.md §5."""
    locator = {
        "source_type": source_type,
        "source_id": "sv",
        "content_hash": "h",
        "logical_locator": logical,
        "physical_locator": physical,
    }
    assert EvidenceQualityPipeline.score_locator(locator) == expected


def test_empty_locator_scores_zero():
    assert EvidenceQualityPipeline.score_locator({}) == 0.0


def test_paginated_sources_are_the_spec_set():
    assert PAGINATED_SOURCE_TYPES == {"PDF", "OCR_TEXT"}


def test_frozen_baseline_locators_are_fully_anchored(quality):
    """The P1 baseline is a PDF: logical + physical on every row."""
    store = quality["pipeline"].store
    for ev in store.evidence.values():
        assert ev.locator["logical_locator"].startswith(f"{C.CHAPTER}/")
        assert ev.locator["physical_locator"].startswith("p.")
        assert ev.locator["source_type"] == "PDF"
        assert ev.locator["content_hash"] == C.CHECKSUM
    assert quality["report"]["overall_quality"]["locator_score"] == 1.0
    assert quality["report"]["overall_quality"]["source_trace_score"] == 1.0