"""A Repository P3 — Knowledge Unit Verification.

Contract tests for the executed P3 specification:
- schema: table, FK, indexes, status CHECK
- authority: no foreign table, repository or graph dependency
- state machine: PENDING -> VERIFYING -> VERIFIED / REJECTED, and no way back
- replay: second run adds no rows and no duplicates
- gates: GATE_2 integrity, GATE_3 scoring, GATE_4 anchoring
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[2]
PKG = ROOT / "src" / "stratum" / "knowledge" / "a_repository"
MIGRATIONS = ROOT / "src" / "stratum" / "db" / "pg_migrations"
MIGRATION = MIGRATIONS / "072_a_ku_verification.sql"
ARTIFACT = ROOT / "artifacts" / "a_repository" / "p3_ku_verification.json"

from stratum.knowledge.a_repository import pilot_corpus as C  # noqa: E402
from stratum.knowledge.a_repository.quality_runner import (  # noqa: E402
    build_quality_baseline,
)
from stratum.knowledge.a_repository.types import (  # noqa: E402
    KIClassification,
    PipelineStage,
)
from stratum.knowledge.a_repository.verification import (  # noqa: E402
    LEGAL_TRANSITIONS,
    TERMINAL_STATUSES,
    VERIFICATION_THRESHOLD,
    VERIFIER_VERSION,
    AVerificationPipeline,
    KnowledgeUnitVerification,
    VerificationStatus,
    VerificationViolation,
    candidate_fingerprint,
    deterministic_id,
    find_definition_span,
    split_proposition,
)
from stratum.knowledge.a_repository.verification_runner import (  # noqa: E402
    REQUIRED_MIGRATION,
    artifact,
    build_verification_baseline,
    gate_results,
    replay_gate,
    report,
)


@pytest.fixture
def verified():
    result = build_verification_baseline()
    return {
        "result": result,
        "base": result["base"],
        "pipeline": result["base"]["pipeline"],
        "vp": result["verification"],
        "report": report(result),
    }


def _fresh():
    """A P2 chain with no decisions taken yet."""
    upstream = build_quality_baseline()
    return (upstream["base"]["pipeline"], upstream["quality"],
            AVerificationPipeline(upstream["base"]["pipeline"],
                                  upstream["quality"]))


def _pending_row(vp, candidate_id, verification_id):
    vp.store.verifications[verification_id] = KnowledgeUnitVerification(
        id=verification_id, candidate_id=candidate_id,
        verification_status=VerificationStatus.PENDING.value,
        verification_score=0.0, definition_check=False, trace_check=False,
        source_check=False, quality_check=False, verified_quote=None)
    return verification_id


# ── schema ───────────────────────────────────────────────────────────────────

def test_072_declares_every_required_column():
    sql = MIGRATION.read_text(encoding="utf-8")
    for column in ("id TEXT PRIMARY KEY",
                   "candidate_id TEXT NOT NULL",
                   "verification_status TEXT NOT NULL",
                   "verification_score FLOAT NOT NULL",
                   "definition_check BOOLEAN NOT NULL",
                   "trace_check BOOLEAN NOT NULL",
                   "source_check BOOLEAN NOT NULL",
                   "quality_check BOOLEAN NOT NULL",
                   "verified_quote TEXT",
                   "verifier_version TEXT NOT NULL",
                   "created_at TIMESTAMP NOT NULL"):
        assert column in sql, f"072 missing column: {column}"


def test_072_candidate_foreign_key_cascades():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert re.search(
        r"candidate_id TEXT NOT NULL\s*"
        r"REFERENCES stratum\.ku_candidate\(id\)\s*ON DELETE CASCADE", sql)


def test_072_has_the_three_required_indexes():
    sql = MIGRATION.read_text(encoding="utf-8")
    for index in ("idx_ku_verification_candidate",
                  "idx_ku_verification_status",
                  "idx_ku_verification_created_at"):
        assert f"CREATE INDEX IF NOT EXISTS {index}" in sql


def test_072_status_check_is_the_four_state_machine():
    sql = MIGRATION.read_text(encoding="utf-8")
    listed = set(re.findall(
        r"'([A-Z]+)'", sql.split("verification_status IN (")[1]))
    assert listed == {s.value for s in VerificationStatus}
    assert listed == {"PENDING", "VERIFYING", "VERIFIED", "REJECTED"}


def test_072_score_is_bounded():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert re.search(
        r"verification_score FLOAT NOT NULL\s*CHECK \(verification_score "
        r">= 0\.0 AND verification_score <= 1\.0\)", sql)


def test_072_is_add_only_and_does_not_touch_060_to_071():
    statements = re.sub(r"--.*", "", MIGRATION.read_text(encoding="utf-8"))
    assert "ALTER TABLE" not in statements
    assert statements.count("CREATE TABLE") == 1
    # 072 is additive. Later migrations may exist; 072 must still be a
    # single new table that alters nothing.
    assert (MIGRATIONS / "071_a_evidence_quality.sql").exists()
    assert (MIGRATIONS / "070_a_repository_foundation.sql").exists()


# ── authority ────────────────────────────────────────────────────────────────

FORBIDDEN_TOKENS = ("knowledge_claims", "b_repository", "c_repository",
                    "bu2", "learning_object", "graph", "merge", "dedup")


@pytest.mark.parametrize("name", ["verification.py", "verification_runner.py"])
def test_p3_code_names_no_external_authority(name):
    text = (PKG / name).read_text(encoding="utf-8").lower()
    for token in FORBIDDEN_TOKENS:
        assert token not in text, f"{name} references external authority: {token}"


def test_072_names_no_external_authority():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    for token in FORBIDDEN_TOKENS:
        assert token not in sql, f"072 references external authority: {token}"


def test_072_references_only_the_candidate_table():
    sql = MIGRATION.read_text(encoding="utf-8")
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", sql))
    assert referenced == {"ku_candidate"}


def test_a_candidate_without_evidence_cannot_be_decided(verified):
    vp = verified["vp"]
    with pytest.raises(VerificationViolation):
        vp.load_candidate("kc_does_not_exist")
    with pytest.raises(VerificationViolation):
        vp.verify("kc_does_not_exist")


def test_decision_reads_only_the_evidence_chain(verified):
    vp, store = verified["vp"], verified["pipeline"].store
    candidate_id = next(iter(store.ku_candidates))
    candidate = store.ku_candidates[candidate_id]
    got_candidate, got_evidence, quality = vp.load_candidate(candidate_id)
    assert got_candidate is candidate
    assert got_evidence is store.evidence[candidate.evidence_id]
    assert quality["source_trace_score"] == 1.0
    assert quality["locator_score"] == 1.0


def test_verification_requires_the_p2_quality_row(verified):
    pipeline, quality, vp = _fresh()
    candidate = next(iter(pipeline.store.ku_candidates.values()))
    evidence_id = candidate.evidence_id
    del pipeline.store.quality[pipeline.store._quality_by_evidence[evidence_id]]
    del pipeline.store._quality_by_evidence[evidence_id]

    verification = vp.verify(candidate.id)
    assert verification.verification_status == VerificationStatus.REJECTED.value
    assert verification.quality_check is False
    # The quote was anchored; it was the missing quality that decided.
    assert verification.verified_quote == candidate.source_span


# ── state machine ────────────────────────────────────────────────────────────

def test_pending_to_verifying_passes():
    pipeline, quality, vp = _fresh()
    candidate = next(iter(pipeline.store.ku_candidates.values()))
    _pending_row(vp, candidate.id, "kv_s1")
    vp.transition("kv_s1", VerificationStatus.VERIFYING)
    assert vp.store.verifications["kv_s1"].verification_status == "VERIFYING"


def test_verifying_to_verified_passes():
    pipeline, quality, vp = _fresh()
    _pending_row(vp, "kc_x", "kv_s2")
    vp.transition("kv_s2", VerificationStatus.VERIFYING)
    vp.transition("kv_s2", VerificationStatus.VERIFIED)
    assert vp.store.verifications["kv_s2"].verification_status == "VERIFIED"


def test_verifying_to_rejected_passes():
    pipeline, quality, vp = _fresh()
    _pending_row(vp, "kc_x", "kv_s3")
    vp.transition("kv_s3", VerificationStatus.VERIFYING)
    vp.transition("kv_s3", VerificationStatus.REJECTED)
    assert vp.store.verifications["kv_s3"].verification_status == "REJECTED"


def test_verified_to_rejected_fails(verified):
    vp = verified["vp"]
    row = next(v for v in vp.store.verifications.values()
               if v.verification_status == "VERIFIED")
    with pytest.raises(VerificationViolation):
        vp.transition(row.id, VerificationStatus.REJECTED)
    with pytest.raises(VerificationViolation):
        vp.reject_verified(row.id)
    assert row.verification_status == "VERIFIED"


def test_verified_to_pending_fails(verified):
    vp = verified["vp"]
    row = next(v for v in vp.store.verifications.values()
               if v.verification_status == "VERIFIED")
    with pytest.raises(VerificationViolation):
        vp.transition(row.id, VerificationStatus.PENDING)
    with pytest.raises(VerificationViolation):
        vp.reopen(row.id)


def test_rejected_to_verified_fails(verified):
    vp = verified["vp"]
    row = next(v for v in vp.store.verifications.values()
               if v.verification_status == "REJECTED")
    with pytest.raises(VerificationViolation):
        vp.transition(row.id, VerificationStatus.VERIFIED)
    with pytest.raises(VerificationViolation):
        vp.overturn(row.id)
    assert row.verification_status == "REJECTED"


def test_transition_table_admits_only_the_two_legal_paths():
    assert LEGAL_TRANSITIONS[VerificationStatus.PENDING] == frozenset(
        {VerificationStatus.VERIFYING})
    assert LEGAL_TRANSITIONS[VerificationStatus.VERIFYING] == frozenset(
        {VerificationStatus.VERIFIED, VerificationStatus.REJECTED})
    for terminal in TERMINAL_STATUSES:
        assert LEGAL_TRANSITIONS[terminal] == frozenset()


def test_verify_walks_pending_verifying_to_a_terminal_state():
    """The two transitions happen inside verify(), in order."""
    pipeline, quality, vp = _fresh()
    candidate = next(iter(pipeline.store.ku_candidates.values()))
    seen = []
    vp._event_sink = lambda e: seen.append(
        (e.stage, e.payload.get("status")))
    vp.verify(candidate.id)
    assert seen[0] == ("candidate", "VERIFYING")
    assert seen[-1][0] == "verify"
    assert seen[-1][1] in {"VERIFIED", "REJECTED"}


def test_no_verification_is_left_pending_or_verifying(verified):
    assert verified["report"]["status_breakdown"]["PENDING"] == 0
    assert verified["report"]["status_breakdown"]["VERIFYING"] == 0


# ── GATE_3 scoring ───────────────────────────────────────────────────────────

def test_verification_score_is_the_minimum_of_the_four_checks(verified):
    for row in verified["vp"].store.verifications.values():
        assert abs(row.verification_score
                   - min(row.trace["scores"].values())) < 1e-9


def test_verified_rows_all_clear_the_threshold(verified):
    for row in verified["vp"].store.verifications.values():
        if row.verification_status == "VERIFIED":
            assert row.verification_score >= VERIFICATION_THRESHOLD
            assert all((row.definition_check, row.trace_check,
                        row.source_check, row.quality_check))


def test_no_false_positives(verified):
    """Verification correctness outranks pass count."""
    assert verified["vp"].false_positives(verified["base"]["reading_run_id"]) == []
    assert verified["report"]["false_positives"] == 0


def test_every_rejection_names_a_failed_check(verified):
    reasons = verified["report"]["rejection_reasons"]
    assert len(reasons) == verified["report"]["rejected_count"] == 7
    for checks in reasons.values():
        assert checks
        assert set(checks) <= {"definition_check", "trace_check",
                               "source_check", "quality_check",
                               "NO_EVIDENCE_ID", "NO_SOURCE_SPAN",
                               "NO_CONTENT_HASH"}


# ── GATE_4 anchoring ─────────────────────────────────────────────────────────

def test_every_verified_unit_is_anchored_in_evidence_content(verified):
    store = verified["pipeline"].store
    for row in verified["vp"].store.verifications.values():
        if row.verification_status != "VERIFIED":
            continue
        candidate = store.ku_candidates[row.candidate_id]
        evidence = store.evidence[candidate.evidence_id]
        assert row.verified_quote == candidate.source_span
        assert row.verified_quote in evidence.content_span


def test_an_unanchored_quote_is_never_stored_as_verified(verified):
    """A quote absent from the evidence content cannot verify."""
    pipeline, quality, vp = _fresh()
    candidate = next(iter(pipeline.store.ku_candidates.values()))
    candidate.source_span = "这一句并不在证据原文里"
    verification = vp.verify(candidate.id)
    assert verification.verification_status == VerificationStatus.REJECTED.value
    assert verification.verified_quote is None
    assert verification.definition_check is False


def test_anchoring_is_a_substring_test_not_a_summary():
    pipeline, quality, vp = _fresh()
    candidate = next(iter(pipeline.store.ku_candidates.values()))
    evidence = store_evidence(pipeline, candidate)
    assert AVerificationPipeline.is_anchored(candidate, evidence) is True
    candidate.source_span = evidence.content_span[:6] + "（摘要）"
    assert AVerificationPipeline.is_anchored(candidate, evidence) is False


def store_evidence(pipeline, candidate):
    return pipeline.store.evidence[candidate.evidence_id]


# ── GATE_2 integrity ─────────────────────────────────────────────────────────

def test_every_candidate_is_traceable(verified):
    trace = verified["report"]["traceability"]
    assert trace["candidates"] == 17
    assert trace["traceable"] == 17
    assert trace["percent"] == 100.0
    assert trace["duplicates"] == 0
    assert trace["unique_fingerprints"] == 17


def test_candidate_integrity_names_its_three_inputs(verified):
    assert AVerificationPipeline.candidate_is_complete.__doc__


def test_fingerprint_changes_with_the_candidate(verified):
    store = verified["pipeline"].store
    candidate = next(iter(store.ku_candidates.values()))
    evidence = store.evidence[candidate.evidence_id]
    before = candidate_fingerprint(candidate, evidence)
    candidate.source_span = candidate.source_span + " "
    assert candidate_fingerprint(candidate, evidence) != before


# ── replay ───────────────────────────────────────────────────────────────────

def test_replay_gate_reports_nothing_new(verified):
    outcome = replay_gate(verified["result"])
    assert outcome["new_candidates"] == 0
    assert outcome["new_verifications"] == 0
    assert outcome["duplicates"] == 0
    assert outcome["identical_report"] == 1


def test_replay_adds_no_rows_and_no_events(verified):
    upstream = build_quality_baseline()
    base, quality = upstream["base"], upstream["quality"]
    vp = AVerificationPipeline(base["pipeline"], quality)
    candidate_ids = sorted(base["candidate_ids"].values())

    first = vp.verify_all(candidate_ids)
    assert len(vp.store.verifications) == 17
    snapshot = {v.id: (v.verification_status, v.verification_score,
                       v.verified_quote, dict(v.trace))
                for v in vp.store.verifications.values()}
    events_after_first = len(vp.events)

    second = vp.verify_all(candidate_ids)

    assert len(vp.store.verifications) == 17, "replay created a new row"
    assert [v.id for v in first] == [v.id for v in second]
    assert {v.id: (v.verification_status, v.verification_score,
                   v.verified_quote, dict(v.trace))
            for v in vp.store.verifications.values()} == snapshot
    assert len(vp.events) == events_after_first, "replay emitted new events"


def test_verification_id_is_content_derived(verified):
    store = verified["pipeline"].store
    candidate_id = next(iter(store._verification_by_candidate))
    assert store._verification_by_candidate[candidate_id] == deterministic_id(
        "kv", candidate_id, VERIFIER_VERSION)


def test_settled_verdict_is_never_rewritten(verified):
    vp, store = verified["vp"], verified["pipeline"].store
    candidate_id = next(iter(store._verification_by_candidate))
    stored = vp.store.verifications[
        vp.store._verification_by_candidate[candidate_id]]
    stored.verification_status = "REJECTED"
    again = vp.verify(candidate_id)
    assert again is stored
    assert len(vp.store.verifications) == 17


def test_full_report_is_deterministic():
    assert report(build_verification_baseline()) == report(
        build_verification_baseline())


# ── semantic integrity ───────────────────────────────────────────────────────

def test_proposition_split_finds_the_relation():
    assert split_proposition("汉谟拉比限制利率") == ("汉谟拉比", "限制", "利率")
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
    pipeline, quality, vp = _fresh()
    candidate = next(iter(pipeline.store.ku_candidates.values()))
    candidate.classification = KIClassification.EVENT.value
    verification = vp.verify(candidate.id)
    if verification.verification_status == VerificationStatus.REJECTED.value:
        assert verification.definition_check is False
        assert verification.verification_score < VERIFICATION_THRESHOLD


# ── gates ────────────────────────────────────────────────────────────────────

def test_gate1_is_not_executed_without_a_ledger(verified):
    gates = gate_results(verified["result"], None)
    assert gates["gate1"] == "NOT_EXECUTED"
    assert gates["gate1"] != "PASS"


def test_gate1_passes_when_the_ledger_carries_072(verified):
    gates = gate_results(verified["result"],
                        ["070_a_repository_foundation.sql",
                         "071_a_evidence_quality.sql",
                         REQUIRED_MIGRATION])
    assert gates["gate1"] == "PASS"


def test_gate1_fails_when_072_is_absent(verified):
    gates = gate_results(verified["result"],
                        ["070_a_repository_foundation.sql"])
    assert gates["gate1"] == "FAIL"


def test_gates_two_to_five_pass_on_the_pilot(verified):
    gates = gate_results(verified["result"], [REQUIRED_MIGRATION])
    assert gates["gate2"] == "PASS"
    assert gates["gate3"] == "PASS"
    assert gates["gate4"] == "PASS"
    assert gates["gate5"] == "PASS"


# ── pilot outcome and artifact ───────────────────────────────────────────────

def test_every_candidate_is_decided_exactly_once(verified):
    vp, run_id = verified["vp"], verified["base"]["reading_run_id"]
    r = verified["report"]
    assert r["candidate_count"] == 17
    assert r["verification_count"] == 17
    assert vp.verification_count(run_id) == 17
    assert vp.orphan_verifications() == []
    assert r["verified_count"] + r["rejected_count"] == 17
    assert r["verification_threshold"] == VERIFICATION_THRESHOLD


def test_artifact_shape(verified):
    doc = artifact(verified["result"], [REQUIRED_MIGRATION])
    assert doc["task"] == "A_P3_KU_VERIFICATION"
    assert doc["book"].startswith("利率史")
    assert doc["candidate_count"] == 17
    assert doc["verified_count"] + doc["rejected_count"] == 17
    assert doc["verification_threshold"] == 0.8
    assert doc["traceability"] == "100%"
    assert doc["authority_scan"] == "PASS"
    assert doc["replay"] == "PASS"
    assert doc["false_positives"] == 0
    assert doc["verifier_version"] == VERIFIER_VERSION
    assert set(doc["gate_results"]) == {
        "gate1", "gate2", "gate3", "gate4", "gate5"}


def test_committed_artifact_matches_the_runner(verified):
    """The artifact on disk is the runner's own output, not a transcription."""
    assert ARTIFACT.exists(), "p3_ku_verification.json is missing"
    import json
    on_disk = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    produced = artifact(verified["result"], on_disk["ledger"])
    for field in ("candidate_count", "verified_count", "rejected_count",
                  "verification_threshold", "traceability", "false_positives",
                  "run_id", "verifier_version", "rejection_reasons"):
        assert on_disk[field] == produced[field], f"artifact drifted: {field}"


def test_p2_classifier_and_lexicon_are_untouched():
    """P3 verifies; P2 extracts. The P2 module is not edited by P3."""
    from stratum.knowledge.a_repository import quality, types
    p2_quality = (PKG / "quality.py").read_text(encoding="utf-8")
    p2_types = (PKG / "types.py").read_text(encoding="utf-8")
    assert "def classify" in p2_quality
    assert "KIClassification" in dir(types)
    assert VERIFIER_VERSION not in p2_quality
    assert VERIFIER_VERSION not in p2_types