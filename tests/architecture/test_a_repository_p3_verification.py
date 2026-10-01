"""A Repository P3 — KU Candidate Verification.

Contract tests for the P3 verification layer (migration 072):
- schema: table exists, FK exists, status CHECK exists
- authority: the decision reads the evidence chain and nothing else
- lifecycle: PENDING -> VERIFIED / REJECTED, and no way back
- replay: same input, same candidate, same verification id
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[2]
PKG = ROOT / "src" / "stratum" / "knowledge" / "a_repository"
MIGRATION = ROOT / "src" / "stratum" / "db" / "pg_migrations" / "072_a_ku_verification.sql"

from stratum.knowledge.a_repository import pilot_corpus as C  # noqa: E402
from stratum.knowledge.a_repository.quality_runner import (  # noqa: E402
    build_quality_baseline,
)
from stratum.knowledge.a_repository.types import (  # noqa: E402
    KIClassification,
    PipelineStage,
)
from stratum.knowledge.a_repository.verification import (  # noqa: E402
    TERMINAL_STATUSES,
    VERIFIER_VERSION,
    AVerificationPipeline,
    VerificationStatus,
    VerificationViolation,
    deterministic_id,
    find_definition_span,
    split_proposition,
)
from stratum.knowledge.a_repository.verification_runner import (  # noqa: E402
    build_verification_baseline,
    report,
)


@pytest.fixture
def verified():
    result = build_verification_baseline()
    return {
        "base": result["base"],
        "pipeline": result["base"]["pipeline"],
        "vp": result["verification"],
        "report": report(result),
    }


def _fresh_pipeline():
    """A P2 chain with no decisions taken yet."""
    upstream = build_quality_baseline()
    return (upstream["base"]["pipeline"], upstream["quality"],
            AVerificationPipeline(upstream["base"]["pipeline"],
                                  upstream["quality"]))


# ── schema ───────────────────────────────────────────────────────────────────

def test_072_declares_the_verification_table():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS stratum.ku_verification" in sql
    for field in ("id TEXT PRIMARY KEY", "candidate_id TEXT NOT NULL",
                  "verification_status TEXT NOT NULL",
                  "verification_method TEXT NOT NULL",
                  "verifier_version TEXT NOT NULL",
                  "verification_trace JSONB NOT NULL",
                  "created_at TIMESTAMP NOT NULL"):
        assert field in sql, f"072 missing column declaration: {field}"


def test_072_has_the_candidate_foreign_key():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert re.search(
        r"candidate_id TEXT NOT NULL\s*"
        r"REFERENCES stratum\.ku_candidate\(id\)", sql)


def test_072_status_check_is_the_closed_lifecycle():
    sql = MIGRATION.read_text(encoding="utf-8")
    listed = set(re.findall(
        r"'([A-Z]+)'", sql.split("verification_status IN (")[1]))
    assert listed == {s.value for s in VerificationStatus}
    assert listed == {"PENDING", "VERIFIED", "REJECTED"}


def test_072_is_add_only():
    """072 creates one table and never alters an existing A table."""
    sql = MIGRATION.read_text(encoding="utf-8")
    statements = re.sub(r"--.*", "", sql)
    assert "ALTER TABLE" not in statements
    assert statements.count("CREATE TABLE") == 1
    # The classification columns of 071 are read, never modified.
    assert "classification" not in statements


def test_072_does_not_touch_migrations_060_to_071():
    for migration in sorted(
            (ROOT / "src" / "stratum" / "db" / "pg_migrations").glob("0[67]*.sql")):
        assert migration.exists()
    assert MIGRATION.name == "072_a_ku_verification.sql"


def test_072_verified_071_as_a_predecessor():
    assert (ROOT / "src" / "stratum" / "db" / "pg_migrations"
            / "071_a_evidence_quality.sql").exists()


# ── authority ────────────────────────────────────────────────────────────────

FORBIDDEN_TOKENS = ("knowledge_claims", "b_repository", "c_repository",
                    "merge", "dedup", "deduplicate")


@pytest.mark.parametrize("name", ["verification.py", "verification_runner.py"])
def test_p3_code_names_no_external_authority(name):
    text = (PKG / name).read_text(encoding="utf-8")
    for token in FORBIDDEN_TOKENS:
        assert token not in text, f"{name} references external authority: {token}"


def test_072_names_no_external_authority():
    sql = MIGRATION.read_text(encoding="utf-8")
    for token in FORBIDDEN_TOKENS:
        assert token not in sql, f"072 references external authority: {token}"


def test_decision_reads_only_the_evidence_chain(verified):
    """The only authority is the candidate, its evidence and the rules."""
    pipeline, vp, store = (verified["pipeline"], verified["vp"],
                           verified["pipeline"].store)
    candidate_id = next(iter(store.ku_candidates))
    candidate = store.ku_candidates[candidate_id]
    candidate_obj, evidence_obj, quality = vp.load_candidate(candidate_id)
    assert candidate_obj is candidate
    assert evidence_obj is store.evidence[candidate.evidence_id]
    assert set(quality) >= {"source_trace_score", "locator_score",
                            "completeness_score", "confidence_score"}
    assert quality["source_trace_score"] == 1.0


def test_candidate_without_evidence_cannot_be_decided(verified):
    vp = verified["vp"]
    with pytest.raises(VerificationViolation):
        vp.load_candidate("kc_does_not_exist")
    with pytest.raises(VerificationViolation):
        vp.verify("kc_does_not_exist")


def test_traceability_runs_candidate_to_evidence_to_source(verified):
    store = verified["pipeline"].store
    run_id = verified["base"]["reading_run_id"]
    trace = verified["vp"].traceability(run_id)
    assert trace["candidates"] == 17
    assert trace["decided"] == 17
    assert trace["trace_complete"] == 17
    assert trace["percent"] == 100.0
    for verification in store.verifications.values():
        candidate = store.ku_candidates[verification.candidate_id]
        evidence = store.evidence[candidate.evidence_id]
        assert evidence.source_version_id in store.source_versions
        assert evidence.locator["content_hash"] == C.CHECKSUM
        assert verification.verification_trace["evidence_ids"] == [
            candidate.evidence_id]


def test_verification_requires_the_p2_quality_row(verified):
    """A candidate with no scored evidence cannot pass Stage 2."""
    pipeline, quality, vp = _fresh_pipeline()
    candidate = next(iter(pipeline.store.ku_candidates.values()))
    evidence_id = candidate.evidence_id
    del pipeline.store.quality[pipeline.store._quality_by_evidence[evidence_id]]
    del pipeline.store._quality_by_evidence[evidence_id]

    verification = vp.verify(candidate.id)
    assert verification.verification_status == VerificationStatus.REJECTED.value
    assert "NO_QUALITY_ROW" in verification.verification_trace["failed_rules"]
    assert "QUALITY_BELOW_THRESHOLD" in verification.verification_trace["failed_rules"]


def test_below_threshold_quality_is_rejected(verified):
    assert AVerificationPipeline.quality_score({}) == 0.0
    assert AVerificationPipeline.quality_score(
        {"source_trace_score": 1.0, "locator_score": 1.0,
         "completeness_score": 1.0, "confidence_score": 1.0}) == 1.0
    assert AVerificationPipeline.quality_score(
        {"source_trace_score": 1.0, "locator_score": 1.0,
         "completeness_score": 1.0, "confidence_score": 0.1}) == 0.1


def test_broken_trace_is_rejected(verified):
    pipeline, quality, vp = _fresh_pipeline()
    candidate = next(iter(pipeline.store.ku_candidates.values()))
    evidence = pipeline.store.evidence[candidate.evidence_id]
    evidence.locator = {"physical_locator": "p.4"}  # no content hash
    verification = vp.verify(candidate.id)
    assert verification.verification_status == VerificationStatus.REJECTED.value
    assert "NO_CONTENT_HASH" in verification.verification_trace["failed_rules"]


# ── lifecycle ────────────────────────────────────────────────────────────────

def _pending_row(vp, candidate_id, verification_id):
    from stratum.knowledge.a_repository.verification import KnowledgeUnitVerification
    vp.store.verifications[verification_id] = KnowledgeUnitVerification(
        id=verification_id, candidate_id=candidate_id,
        verification_status=VerificationStatus.PENDING.value,
        verification_method="test", verifier_version=VERIFIER_VERSION,
        verification_trace={})
    return verification_id


def test_pending_to_verified_is_legal():
    pipeline, quality, vp = _fresh_pipeline()
    candidate = next(iter(pipeline.store.ku_candidates.values()))
    _pending_row(vp, candidate.id, "kv_pending_a")
    vp.transition("kv_pending_a", VerificationStatus.VERIFIED)
    assert vp.store.verifications["kv_pending_a"].verification_status == "VERIFIED"


def test_a_decided_candidate_is_verified_or_rejected():
    """verify() settles the row; it never leaves one PENDING."""
    pipeline, quality, vp = _fresh_pipeline()
    candidate = next(iter(pipeline.store.ku_candidates.values()))
    verification = vp.verify(candidate.id)
    assert verification.verification_status in {
        VerificationStatus.VERIFIED.value,
        VerificationStatus.REJECTED.value}


def test_pending_to_rejected_is_legal():
    pipeline, quality, vp = _fresh_pipeline()
    _pending_row(vp, "kc_manual", "kv_pending_b")
    vp.transition("kv_pending_b", VerificationStatus.REJECTED)
    assert vp.store.verifications["kv_pending_b"].verification_status == "REJECTED"


def test_verified_to_pending_fails(verified):
    vp = verified["vp"]
    verified_row = next(v for v in vp.store.verifications.values()
                        if v.verification_status == "VERIFIED")
    with pytest.raises(VerificationViolation):
        vp.transition(verified_row.id, VerificationStatus.PENDING)
    with pytest.raises(VerificationViolation):
        vp.reopen(verified_row.id)
    assert verified_row.verification_status == "VERIFIED"


def test_rejected_to_verified_fails(verified):
    vp = verified["vp"]
    rejected_row = next(v for v in vp.store.verifications.values()
                        if v.verification_status == "REJECTED")
    with pytest.raises(VerificationViolation):
        vp.transition(rejected_row.id, VerificationStatus.VERIFIED)
    with pytest.raises(VerificationViolation):
        vp.overturn(rejected_row.id)
    assert rejected_row.verification_status == "REJECTED"


def test_terminal_states_are_terminal():
    from stratum.knowledge.a_repository.verification import LEGAL_TRANSITIONS
    assert TERMINAL_STATUSES == frozenset(
        {VerificationStatus.VERIFIED, VerificationStatus.REJECTED})
    for terminal in TERMINAL_STATUSES:
        assert LEGAL_TRANSITIONS[terminal] == frozenset()
    assert LEGAL_TRANSITIONS[VerificationStatus.PENDING] == frozenset(
        {VerificationStatus.VERIFIED, VerificationStatus.REJECTED})


def test_rejection_always_carries_a_reason_and_a_trace(verified):
    vp, store = verified["vp"], verified["pipeline"].store
    rejected = [v for v in store.verifications.values()
                if v.verification_status == "REJECTED"]
    assert rejected, "the frozen baseline must exercise the reject path"
    for verification in rejected:
        assert verification.verification_trace["failed_rules"]
        assert verification.verification_trace["verifier_version"] \
            == VERIFIER_VERSION
        assert verification.verification_trace["candidate_id"] \
            == verification.candidate_id
        assert verification.verification_trace["evidence_ids"]


# ── replay ───────────────────────────────────────────────────────────────────

def test_replay_produces_identical_decisions():
    first = report(build_verification_baseline())
    second = report(build_verification_baseline())
    assert first == second


def test_replay_adds_no_new_rows():
    upstream = build_quality_baseline()
    base, quality = upstream["base"], upstream["quality"]
    vp = AVerificationPipeline(base["pipeline"], quality)
    candidate_ids = sorted(base["candidate_ids"].values())

    first = vp.verify_all(candidate_ids)
    assert len(vp.store.verifications) == 17
    assert len(vp.store._verification_by_candidate) == 17
    snapshot = {v.id: (v.verification_status, dict(v.verification_trace))
                for v in vp.store.verifications.values()}
    events_after_first = len(vp.events)

    second = vp.verify_all(candidate_ids)

    assert len(vp.store.verifications) == 17, "replay created a new row"
    assert [v.id for v in first] == [v.id for v in second]
    assert {v.id: (v.verification_status, dict(v.verification_trace))
            for v in vp.store.verifications.values()} == snapshot
    assert len(vp.events) == events_after_first, "replay emitted new events"
    assert all(vp.has_verification(cid) for cid in candidate_ids)


def test_verification_id_is_content_derived(verified):
    store = verified["pipeline"].store
    candidate_id = next(iter(store._verification_by_candidate))
    assert store._verification_by_candidate[candidate_id] == deterministic_id(
        "kv", candidate_id, VERIFIER_VERSION)


def test_settled_decision_is_never_rewritten(verified):
    """A second verify() returns the stored row, not a fresh decision."""
    vp, store = verified["vp"], verified["pipeline"].store
    candidate_id = next(iter(store._verification_by_candidate))
    stored = vp.store.verifications[vp.store._verification_by_candidate[candidate_id]]
    stored.verification_status = "REJECTED"
    again = vp.verify(candidate_id)
    assert again is stored
    assert again.verification_status == "REJECTED"
    assert len(vp.store.verifications) == 17


# ── semantic integrity ───────────────────────────────────────────────────────

def test_verified_candidate_carries_a_locatable_unit(verified):
    store = verified["pipeline"].store
    for verification in store.verifications.values():
        if verification.verification_status != "VERIFIED":
            continue
        slots = verification.verification_trace["slots"]
        assert slots.get("ANCHORED") == "True"
        assert "QUALITY_PASS" in verification.verification_trace["rules"]
        assert "TRACE_COMPLETE" in verification.verification_trace["rules"]
        assert "HAS_SOURCE_SPAN" in verification.verification_trace["rules"]


def test_proposition_split_finds_the_relation():
    subject, predicate, obj = split_proposition("汉谟拉比限制利率")
    assert (subject, predicate, obj) == ("汉谟拉比", "限制", "利率")
    assert split_proposition("谷物贷款每年33.333%") == ("", "", "")


def test_definition_span_is_only_a_definition():
    assert find_definition_span("复利是指对利息本身计息") == "是指对利息本身计息"
    assert find_definition_span("巴比伦允许土地作为抵押") == ""


def test_required_slots_per_kind():
    required = AVerificationPipeline.required_slots
    assert required(KIClassification.FACT.value) == (
        "ANCHORED", "SUBJECT", "PREDICATE", "OBJECT")
    assert required(KIClassification.CONCEPT.value) == (
        "ANCHORED", "DEFINITION_SPAN")
    assert required(KIClassification.EVENT.value) == (
        "ANCHORED", "ACTOR", "TIME", "ACTION")
    assert required("UNKNOWN_KIND") == ("ANCHORED",)


def test_event_candidate_needs_actor_time_action(verified):
    """A candidate typed EVENT is rejected without all three slots."""
    pipeline, quality, vp = _fresh_pipeline()
    candidate = next(iter(pipeline.store.ku_candidates.values()))
    candidate.classification = KIClassification.EVENT.value
    verification = vp.verify(candidate.id)
    trace = verification.verification_trace
    if verification.verification_status == "REJECTED":
        assert {"MISSING_ACTOR", "MISSING_TIME", "MISSING_ACTION"} & set(
            trace["failed_rules"])


def test_verification_emits_an_event_per_decision(verified):
    events = verified["vp"].events
    assert len(events) == 17
    assert {e.stage for e in events} == {PipelineStage.VERIFY}
    assert sum(1 for e in events if e.payload["status"] == "VERIFIED") \
        == verified["report"]["verified"]
    assert sum(1 for e in events if e.payload["status"] == "REJECTED") \
        == verified["report"]["rejected"]


# ── pilot outcome ────────────────────────────────────────────────────────────

def test_every_candidate_is_decided_exactly_once(verified):
    vp = verified["vp"]
    run_id = verified["base"]["reading_run_id"]
    report_ = verified["report"]
    assert report_["candidate_count"] == 17
    assert report_["verification_count"] == 17
    assert vp.verification_count(run_id) == 17
    assert vp.orphan_verifications() == []
    assert sum(report_["status_breakdown"].values()) == 17
    assert report_["status_breakdown"]["PENDING"] == 0
    assert report_["verified"] + report_["rejected"] == 17


def test_pilot_book_is_the_frozen_first_book(verified):
    assert verified["report"]["book"].startswith("利率史")
    assert verified["report"]["verifier_version"] == VERIFIER_VERSION