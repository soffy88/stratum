"""Tests for Book Understanding 2.0 P4-P9 Foundation Contract + Repair Round 2.

Covers model contracts AND behavioral gates:
D1 (P1/P2/P6 artifact gates), D2 (VSU save/read-back), D5 (book_id),
D6 (verification hard gate CASE A-G), D7 (gap lifecycle + blocking),
D8 (BU -> LO -> RI projection, no A/B mutation, idempotent),
STATE (invalid transition preserves state), RESUME (missing artifacts).
"""

import json
import pytest
from pydantic import ValidationError

from stratum.knowledge.bu_v2_models import (
    ChapterUnderstanding, ChapterDelta, BookUnderstandingV2,
    UnderstandingGap, LearningObject, RetrievalItem, VisualSemanticUnit,
    VerificationArtifact, VerificationOutcome,
    BUStatus, GapStatus, GapType, Severity, Difficulty, LearningImportance,
    InteractionType, Scope
)
from stratum.services.bu_v2_pipeline import BU2PipelineStateMachine, PipelineTransitionError, PipelineRunState
import stratum.services.bu_v2_pipeline as P
import stratum.services.bu_v2_repositories as R

def test_chapter_understanding_contract():
    # P4 Contract: Cannot use random dicts, must follow schema
    cu = ChapterUnderstanding(
        id="cu_1",
        run_id="run_1",
        chapter_id="ch_1",
        chapter_question="What is X?",
        chapter_goal="Define X",
        chapter_thesis="X is Y",
        primary_role="DEFINE",
        major_ku_refs=["ku_1", "ku_2"]
    )
    assert cu.primary_role == "DEFINE"
    assert "ku_1" in cu.major_ku_refs

def test_chapter_delta_contract():
    # P4 Contract: Must define new/revised concepts and claims, not a summary
    cd = ChapterDelta(
        id="cd_1",
        run_id="run_1",
        chapter_id="ch_1",
        new_concepts_refs=["concept_a"],
        revises_prior_refs=["claim_x"]
    )
    assert "concept_a" in cd.new_concepts_refs

def test_book_understanding_v2_contract():
    # P5 Contract: Working vs Verified BU, with run/book/substrate provenance
    bu = BookUnderstandingV2(
        id="bu_1",
        run_id="run_1",
        book_id="book_1",
        substrate_id="sub_1",
        status=BUStatus.DRAFT,
        governing_questions=["Why do nations fail?"],
        argument_architecture={"root_arguments": ["arg_1"], "supporting_arguments": []}
    )
    assert bu.status == BUStatus.DRAFT
    assert bu.book_id == "book_1"

    # ENUM Validation Failure
    with pytest.raises(ValidationError):
        BookUnderstandingV2(
            id="bu_2",
            run_id="run_1",
            book_id="book_1",
            substrate_id="sub_2",
            status="INVALID_STATUS"
        )

    # D5: book_id is required at the model layer
    with pytest.raises(ValidationError):
        BookUnderstandingV2(
            id="bu_3",
            run_id="run_1",
            substrate_id="sub_3",
        )

def test_book_understanding_repository_rejects_empty_provenance():
    # D5: repository rejects empty run_id / book_id / substrate_id
    good = dict(id="bu_x", run_id="r", book_id="b", substrate_id="s")
    for field in ("run_id", "book_id", "substrate_id"):
        bad = dict(good)
        bad[field] = ""
        with pytest.raises(ValueError):
            R.BookUnderstandingRepository.save(BookUnderstandingV2(**bad))

def test_verification_gap_contract():
    # P6 Contract: Verification lifecycle
    gap = UnderstandingGap(
        id="gap_1",
        run_id="run_1",
        type=GapType.MISSING_EVIDENCE,
        severity=Severity.HIGH,
        question="Where is the proof for claim X?",
        status=GapStatus.OPEN
    )
    assert gap.severity == Severity.HIGH

    with pytest.raises(ValidationError):
        UnderstandingGap(
            id="gap_2",
            run_id="run_1",
            type="RANDOM_GAP", # Fails GapType Enum
            severity=Severity.LOW,
            question="Bad gap"
        )

def test_learning_contract():
    # P8/P9 Contract, with run/book provenance (D8)
    lo = LearningObject(
        id="lo_1",
        bu_id="bu_1",
        run_id="run_1",
        book_id="book_1",
        learning_goal="Understand X",
        knowledge_type="conceptual",
        importance=LearningImportance.CORE,
        difficulty=Difficulty.HARD
    )
    assert lo.importance == LearningImportance.CORE

    ri = RetrievalItem(
        id="ri_1",
        learning_object_id="lo_1",
        interaction_type=InteractionType.EXPLAIN_WHY,
        payload={"question": "Why?", "expected_answer": "Because."}
    )
    assert ri.interaction_type == InteractionType.EXPLAIN_WHY

    # D8: LearningObject without provenance cannot persist
    with pytest.raises(ValueError):
        R.LearningObjectRepository.save(LearningObject(
            id="lo_2", bu_id="bu_1",
            learning_goal="G", knowledge_type="conceptual",
            importance=LearningImportance.CORE, difficulty=Difficulty.EASY,
        ))

def test_pipeline_state_machine_invalid_transition(monkeypatch):
    # Mock the repository to simulate state
    class MockRepo:
        state = PipelineRunState.CREATED

        @classmethod
        def get_status(cls, run_id):
            return cls.state

        @classmethod
        def update_status(cls, run_id, new_status, failure_reason=None):
            cls.state = new_status
            MockRepo.state = new_status

    class MockRunRepo(MockRepo):
        @staticmethod
        def check_reading_ledger_exists(run_id):
            return True

        @staticmethod
        def check_inspection_exists(run_id):
            return True

        @staticmethod
        def check_deep_read_exists(run_id):
            return True

    class MockVSURepo:
        @staticmethod
        def check_exists(run_id):
            return True

    monkeypatch.setattr("stratum.services.bu_v2_pipeline.PipelineRunRepository", MockRunRepo)
    monkeypatch.setattr("stratum.services.bu_v2_pipeline.VisualSemanticUnitRepository", MockVSURepo)

    sm = BU2PipelineStateMachine(run_id="run_1")

    # Valid transition (CREATED -> PERCEIVED)
    sm.execute_pass_0()
    assert MockRepo.state == PipelineRunState.PERCEIVED

    # Invalid transition (PERCEIVED -> DEEP_READ_COMPLETE directly)
    with pytest.raises(PipelineTransitionError):
        sm.execute_pass_2()

def test_pipeline_failure_persistence(monkeypatch):
    class MockRepo:
        state = PipelineRunState.PERCEIVED
        failure = None

        @classmethod
        def get_status(cls, run_id):
            return cls.state

        @classmethod
        def update_status(cls, run_id, new_status, failure_reason=None):
            cls.state = new_status
            cls.failure = failure_reason

        @staticmethod
        def check_inspection_exists(run_id):
            return True

    monkeypatch.setattr("stratum.services.bu_v2_pipeline.PipelineRunRepository", MockRepo)

    sm = BU2PipelineStateMachine(run_id="run_2")

    # Force a failure
    def failing_action():
        raise ValueError("Simulated Extraction Failure")

    monkeypatch.setattr(sm, "_assert_and_transition", lambda expected, target: failing_action())

    with pytest.raises(ValueError):
        sm.execute_pass_1()

    assert MockRepo.state == PipelineRunState.FAILED
    assert MockRepo.failure == "Simulated Extraction Failure"


# ── Repair Round 2: harness ───────────────────────────────────────────────────

def _install_run_repo(monkeypatch, state, ledger=True, inspected=True, deep=True,
                      fail_update=False):
    """Fake PipelineRunRepository with gate flags and optional commit failure."""
    class FakeRun:
        pass
    FakeRun.state = state
    FakeRun.failure = None
    FakeRun.fail_update = fail_update
    FakeRun.ledger = ledger
    FakeRun.inspected = inspected
    FakeRun.deep = deep

    @classmethod
    def get_status(cls, run_id):
        return cls.state

    @classmethod
    def update_status(cls, run_id, new_status, failure_reason=None):
        if cls.fail_update:
            raise RuntimeError("DB down")
        cls.state = new_status
        cls.failure = failure_reason

    FakeRun.get_status = get_status
    FakeRun.update_status = update_status
    FakeRun.check_reading_ledger_exists = staticmethod(lambda rid: FakeRun.ledger)
    FakeRun.check_inspection_exists = staticmethod(lambda rid: FakeRun.inspected)
    FakeRun.check_deep_read_exists = staticmethod(lambda rid: FakeRun.deep)
    monkeypatch.setattr(P, "PipelineRunRepository", FakeRun)
    return FakeRun


def _install_simple_gates(monkeypatch, vsu=True, cu=True, cd=True, bu=True):
    class FakeVSU:
        @staticmethod
        def check_exists(rid):
            return vsu
    class FakeCU:
        @staticmethod
        def check_exists(rid):
            return cu
    class FakeCD:
        @staticmethod
        def check_exists(rid):
            return cd
    class FakeBU:
        @staticmethod
        def check_exists(rid):
            return bu

        @staticmethod
        def get_by_run(rid):
            return None
    monkeypatch.setattr(P, "VisualSemanticUnitRepository", FakeVSU)
    monkeypatch.setattr(P, "ChapterUnderstandingRepository", FakeCU)
    monkeypatch.setattr(P, "ChapterDeltaRepository", FakeCD)
    monkeypatch.setattr(P, "BookUnderstandingRepository", FakeBU)


def _pass_artifact(va_id="va_1", run_id="run_1", book_id="book_1",
                   status=VerificationOutcome.PASS, gaps=0):
    return VerificationArtifact(
        id=va_id, run_id=run_id, book_id=book_id, status=status,
        checked_artifacts=["chapter_understandings", "book_understandings_v2"],
        unresolved_gap_count=gaps, verification_timestamp="2026-01-01T00:00:00Z",
    )


def _bu_row(run_id="run_1", book_id="book_1", bu_id="bu_1",
            questions=None, theses=None):
    return {
        "id": bu_id, "run_id": run_id, "book_id": book_id,
        "substrate_id": "sub_1", "version": 1,
        "governing_questions_json": json.dumps(questions if questions is not None else ["Why?"]),
        "central_theses_json": json.dumps(theses if theses is not None else ["Because."]),
    }


def _install_verify_ctx(monkeypatch, bu, va, blocking=0):
    class FakeBURepo:
        @staticmethod
        def check_exists(rid):
            return bu is not None

        @staticmethod
        def get_by_run(rid):
            return bu
    class FakeVerif:
        @staticmethod
        def check_exists(rid):
            return va is not None and va.run_id == rid

        @staticmethod
        def get_latest(rid):
            if va is not None and va.run_id == rid:
                return va
            return None
    class FakeGap:
        @staticmethod
        def get_blocking_gaps_count(rid):
            return blocking
    monkeypatch.setattr(P, "BookUnderstandingRepository", FakeBURepo)
    monkeypatch.setattr(P, "VerificationRepository", FakeVerif)
    monkeypatch.setattr(P, "UnderstandingGapRepository", FakeGap)
    return FakeBURepo, FakeVerif, FakeGap


# ── D1: P1 / P2 gates ─────────────────────────────────────────────────────────

def test_d1_p1_missing_inspection_rejected_state_preserved(monkeypatch):
    fr = _install_run_repo(monkeypatch, PipelineRunState.PERCEIVED, inspected=False)
    sm = BU2PipelineStateMachine(run_id="run_1")
    with pytest.raises(PipelineTransitionError):
        sm.execute_pass_1()
    assert fr.state == PipelineRunState.PERCEIVED
    assert fr.failure is None


def test_d1_p1_inspection_present_advances(monkeypatch):
    fr = _install_run_repo(monkeypatch, PipelineRunState.PERCEIVED, inspected=True)
    sm = BU2PipelineStateMachine(run_id="run_1")
    sm.execute_pass_1()
    assert fr.state == PipelineRunState.INSPECTED


def test_d1_p2_missing_deep_read_rejected_state_preserved(monkeypatch):
    fr = _install_run_repo(monkeypatch, PipelineRunState.INSPECTED, deep=False)
    sm = BU2PipelineStateMachine(run_id="run_1")
    with pytest.raises(PipelineTransitionError):
        sm.execute_pass_2()
    assert fr.state == PipelineRunState.INSPECTED
    assert fr.failure is None


def test_d1_p2_deep_read_present_advances(monkeypatch):
    fr = _install_run_repo(monkeypatch, PipelineRunState.INSPECTED, deep=True)
    sm = BU2PipelineStateMachine(run_id="run_1")
    sm.execute_pass_2()
    assert fr.state == PipelineRunState.DEEP_READ_COMPLETE


def test_d1_p0_missing_vsu_rejected_state_preserved(monkeypatch):
    fr = _install_run_repo(monkeypatch, PipelineRunState.CREATED)
    _install_simple_gates(monkeypatch, vsu=False)
    sm = BU2PipelineStateMachine(run_id="run_1")
    with pytest.raises(PipelineTransitionError):
        sm.execute_pass_0()
    assert fr.state == PipelineRunState.CREATED


# ── D2: VSU save / read-back ──────────────────────────────────────────────────

def _install_vsu_store(monkeypatch):
    store = {}
    saved = []

    def fake_insert(table, row):
        saved.append((table, dict(row)))
        store.setdefault(table, []).append(dict(row))

    def fake_read(table, rid, id_column="id"):
        for row in store.get(table, []):
            if row.get(id_column) == rid:
                return dict(row)
        return None

    def fake_query(sql, params=None):
        params = params or {}
        if "visual_semantic_unit" in sql:
            if "WHERE run_id" in sql:
                rows = [r for r in store.get("visual_semantic_unit", [])
                        if r.get("run_id") == params.get("run_id")]
                if "LIMIT 1" in sql:
                    return rows[:1]
                return [dict(r) for r in rows]
            return [dict(r) for r in store.get("visual_semantic_unit", [])]
        return []

    monkeypatch.setattr(R, "insert", fake_insert)
    monkeypatch.setattr(R, "read", fake_read)
    monkeypatch.setattr(R, "query", fake_query)
    return store, saved


def _sample_vsu(vsu_id="vsu_1"):
    return VisualSemanticUnit(
        id=vsu_id, type="chart",
        variables=["price", "quantity"],
        entities=["firm_a"],
        relations=["supply_curve"],
        trends=["increasing"],
        comparisons=["q1_vs_q2"],
        textual_claims_supported=["claim_1"],
        ku_refs=["ku_1"], argument_refs=["arg_1"],
    )


def test_d2_vsu_save_read_roundtrip(monkeypatch):
    _install_vsu_store(monkeypatch)
    vsu = _sample_vsu()
    R.VisualSemanticUnitRepository.save(vsu, run_id="run_1", substrate_id="sub_1")

    back = R.VisualSemanticUnitRepository.get("vsu_1")
    assert back is not None
    assert back.id == vsu.id
    assert back.type == vsu.type
    assert back.variables == ["price", "quantity"]
    assert back.entities == ["firm_a"]
    assert back.relations == ["supply_curve"]
    assert back.trends == ["increasing"]
    assert back.comparisons == ["q1_vs_q2"]
    assert back.textual_claims_supported == ["claim_1"]
    assert back.ku_refs == ["ku_1"]
    assert back.argument_refs == ["arg_1"]

    # run scoping: other run's rows are not listed
    R.VisualSemanticUnitRepository.save(_sample_vsu("vsu_2"), run_id="run_2", substrate_id="sub_1")
    mine = R.VisualSemanticUnitRepository.list_for_run("run_1")
    assert [v.id for v in mine] == ["vsu_1"]
    assert R.VisualSemanticUnitRepository.check_exists("run_1") is True
    assert R.VisualSemanticUnitRepository.check_exists("run_9") is False
    assert R.VisualSemanticUnitRepository.get("nope") is None


def test_d2_vsu_save_rejects_empty_provenance():
    with pytest.raises(ValueError):
        R.VisualSemanticUnitRepository.save(_sample_vsu(), run_id="", substrate_id="sub_1")
    with pytest.raises(ValueError):
        R.VisualSemanticUnitRepository.save(_sample_vsu(), run_id="run_1", substrate_id="")


# ── D6: verification hard gate CASE A-G ───────────────────────────────────────

def test_d6_case_a_no_artifact_not_verified(monkeypatch):
    fr = _install_run_repo(monkeypatch, PipelineRunState.BOOK_INTEGRATED)
    _install_verify_ctx(monkeypatch, bu=_bu_row(), va=None, blocking=0)
    sm = BU2PipelineStateMachine(run_id="run_1")
    with pytest.raises(PipelineTransitionError, match="CASE A"):
        sm.execute_pass_5_verify()
    # Entered VERIFICATION_PENDING, but NOT VERIFIED and NOT FAILED
    assert fr.state == PipelineRunState.VERIFICATION_PENDING
    assert fr.failure is None


def test_d6_case_b_fail_outcome_not_verified(monkeypatch):
    fr = _install_run_repo(monkeypatch, PipelineRunState.BOOK_INTEGRATED)
    _install_verify_ctx(monkeypatch, bu=_bu_row(),
                        va=_pass_artifact(status=VerificationOutcome.FAIL), blocking=0)
    sm = BU2PipelineStateMachine(run_id="run_1")
    with pytest.raises(PipelineTransitionError, match="CASE B"):
        sm.execute_pass_5_verify()
    assert fr.state == PipelineRunState.VERIFICATION_PENDING


def test_d6_case_c_blocked_outcome_not_verified(monkeypatch):
    fr = _install_run_repo(monkeypatch, PipelineRunState.BOOK_INTEGRATED)
    _install_verify_ctx(monkeypatch, bu=_bu_row(),
                        va=_pass_artifact(status=VerificationOutcome.BLOCKED), blocking=0)
    sm = BU2PipelineStateMachine(run_id="run_1")
    with pytest.raises(PipelineTransitionError, match="CASE C"):
        sm.execute_pass_5_verify()
    assert fr.state == PipelineRunState.VERIFICATION_PENDING


def test_d6_case_d_blocking_gaps_not_verified(monkeypatch):
    fr = _install_run_repo(monkeypatch, PipelineRunState.BOOK_INTEGRATED)
    _install_verify_ctx(monkeypatch, bu=_bu_row(),
                        va=_pass_artifact(status=VerificationOutcome.PASS), blocking=2)
    sm = BU2PipelineStateMachine(run_id="run_1")
    with pytest.raises(PipelineTransitionError, match="CASE D"):
        sm.execute_pass_5_verify()
    assert fr.state == PipelineRunState.VERIFICATION_PENDING


def test_d6_case_e_valid_pass_verified(monkeypatch):
    fr = _install_run_repo(monkeypatch, PipelineRunState.BOOK_INTEGRATED)
    _install_verify_ctx(monkeypatch, bu=_bu_row(),
                        va=_pass_artifact(status=VerificationOutcome.PASS), blocking=0)
    sm = BU2PipelineStateMachine(run_id="run_1")
    sm.execute_pass_5_verify()
    assert fr.state == PipelineRunState.VERIFIED


def test_d6_case_f_wrong_run_not_verified(monkeypatch):
    # Artifact persisted for another run must not verify this run.
    fr = _install_run_repo(monkeypatch, PipelineRunState.VERIFICATION_PENDING)
    other = _pass_artifact(run_id="run_OTHER")
    class FakeBURepo:
        @staticmethod
        def get_by_run(rid):
            return _bu_row(run_id="run_1")
    class FakeVerif:
        @staticmethod
        def get_latest(rid):
            return other  # cross-run leak at the read layer
    class FakeGap:
        @staticmethod
        def get_blocking_gaps_count(rid):
            return 0
    monkeypatch.setattr(P, "BookUnderstandingRepository", FakeBURepo)
    monkeypatch.setattr(P, "VerificationRepository", FakeVerif)
    monkeypatch.setattr(P, "UnderstandingGapRepository", FakeGap)
    sm = BU2PipelineStateMachine(run_id="run_1")
    with pytest.raises(PipelineTransitionError, match="CASE F"):
        sm.execute_pass_5_verify()
    assert fr.state == PipelineRunState.VERIFICATION_PENDING


def test_d6_case_g_wrong_book_not_verified(monkeypatch):
    fr = _install_run_repo(monkeypatch, PipelineRunState.VERIFICATION_PENDING)
    _install_verify_ctx(monkeypatch, bu=_bu_row(book_id="book_1"),
                        va=_pass_artifact(book_id="book_OTHER"), blocking=0)
    # Fix up: get_latest scoping is by run; force-return the wrong-book artifact
    class FakeVerif2:
        @staticmethod
        def get_latest(rid):
            return _pass_artifact(book_id="book_OTHER")
    monkeypatch.setattr(P, "VerificationRepository", FakeVerif2)
    sm = BU2PipelineStateMachine(run_id="run_1")
    with pytest.raises(PipelineTransitionError, match="CASE G"):
        sm.execute_pass_5_verify()
    assert fr.state == PipelineRunState.VERIFICATION_PENDING


def test_d6_self_reported_gaps_not_verified(monkeypatch):
    fr = _install_run_repo(monkeypatch, PipelineRunState.BOOK_INTEGRATED)
    _install_verify_ctx(monkeypatch, bu=_bu_row(),
                        va=_pass_artifact(status=VerificationOutcome.PASS, gaps=3),
                        blocking=0)
    sm = BU2PipelineStateMachine(run_id="run_1")
    with pytest.raises(PipelineTransitionError, match="self-reports"):
        sm.execute_pass_5_verify()
    assert fr.state == PipelineRunState.VERIFICATION_PENDING


def test_d6_verification_save_propagates_db_error(monkeypatch):
    # D6: no silent swallow — persistence failure must raise.
    def boom(table, row):
        raise RuntimeError("table verification_artifacts missing")
    monkeypatch.setattr(R, "insert", boom)
    with pytest.raises(RuntimeError):
        R.VerificationRepository.save(_pass_artifact())


def test_d6_check_exists_propagates_schema_error(monkeypatch):
    def boom(sql, params=None):
        raise RuntimeError("relation does not exist")
    monkeypatch.setattr(R, "query", boom)
    with pytest.raises(RuntimeError):
        R.VerificationRepository.check_exists("run_1")


# ── D7: gap lifecycle ─────────────────────────────────────────────────────────

def _install_gap_store(monkeypatch, status="OPEN", run_id="run_1"):
    store = {"g1": {
        "id": "g1", "run_id": run_id, "type": "MISSING_EVIDENCE",
        "severity": "HIGH", "affected_component": "ch_1",
        "question": "Where is proof?",
        "evidence_targets_json": json.dumps(["ev_1"]),
        "required_action": "reread", "status": status,
    }}
    monkeypatch.setattr(R, "read", lambda t, rid, id_column="id": dict(store[rid]) if rid in store else None)
    monkeypatch.setattr(R, "update",
                        lambda t, rid, changes, id_column="id": store[rid].update(changes))
    return store


def test_d7_legal_gap_lifecycle(monkeypatch):
    _install_gap_store(monkeypatch, status="OPEN")
    g = R.UnderstandingGapRepository.transition("g1", "run_1", GapStatus.TARGETED_REREAD_REQUIRED)
    assert g.status == GapStatus.TARGETED_REREAD_REQUIRED
    g = R.UnderstandingGapRepository.transition("g1", "run_1", GapStatus.REREAD_IN_PROGRESS)
    assert g.status == GapStatus.REREAD_IN_PROGRESS
    g = R.UnderstandingGapRepository.transition("g1", "run_1", GapStatus.RESOLVED)
    assert g.status == GapStatus.RESOLVED


def test_d7_illegal_open_to_resolved_rejected(monkeypatch):
    store = _install_gap_store(monkeypatch, status="OPEN")
    with pytest.raises(R.GapTransitionError):
        R.UnderstandingGapRepository.transition("g1", "run_1", GapStatus.RESOLVED)
    assert store["g1"]["status"] == "OPEN"


def test_d7_terminal_states_reject_further_transitions(monkeypatch):
    _install_gap_store(monkeypatch, status="RESOLVED")
    with pytest.raises(R.GapTransitionError):
        R.UnderstandingGapRepository.transition("g1", "run_1", GapStatus.OPEN)
    with pytest.raises(R.GapTransitionError):
        R.UnderstandingGapRepository.transition("g1", "run_1", GapStatus.REJECTED)


def test_d7_gap_transition_scoped_to_run(monkeypatch):
    _install_gap_store(monkeypatch, status="OPEN", run_id="run_1")
    with pytest.raises(R.GapTransitionError):
        R.UnderstandingGapRepository.transition("g1", "run_OTHER", GapStatus.TARGETED_REREAD_REQUIRED)


def test_d7_blocking_statuses_cover_lifecycle():
    # Blocking = unresolved work; RESOLVED / REJECTED / WONTFIX never block.
    assert set(R.BLOCKING_GAP_STATUSES) == {
        "OPEN", "TARGETED_REREAD_REQUIRED", "REREAD_IN_PROGRESS",
        "TARGETED_REREAD_DISPATCHED",
    }
    for terminal in ("RESOLVED", "REJECTED", "WONTFIX", "RECONCILED"):
        assert terminal not in R.BLOCKING_GAP_STATUSES


# ── D8 + P6: projection chain ─────────────────────────────────────────────────

def _install_projection_store(monkeypatch):
    store = {}
    inserts = []
    update_calls = []

    def fake_read(table, rid, id_column="id"):
        return store.get((table, rid))

    def fake_insert(table, row):
        inserts.append((table, dict(row)))
        store[(table, row["id"])] = dict(row)

    monkeypatch.setattr(P, "read", fake_read)
    monkeypatch.setattr(R, "insert", fake_insert)
    monkeypatch.setattr(R, "read", fake_read)
    monkeypatch.setattr(R, "update",
                        lambda t, rid, changes, id_column="id": update_calls.append((t, rid, changes)))
    base_query = R.query
    monkeypatch.setattr(R, "query", lambda sql, params=None: [])
    # LO/RI existence checks go through R.query in repository helpers
    return store, inserts, update_calls


def test_d8_bu_to_lo_to_ri_chain(monkeypatch):
    fr = _install_run_repo(monkeypatch, PipelineRunState.VERIFIED)
    _install_verify_ctx(monkeypatch, bu=_bu_row(questions=["Why?", "How?"], theses=["T1"]),
                        va=_pass_artifact(), blocking=0)
    store, inserts, update_calls = _install_projection_store(monkeypatch)
    # repository existence checks use R.query: answer from the fake store
    def fake_query(sql, params=None):
        params = params or {}
        if "learning_objects" in sql and "bu_id" in sql:
            rows = [r for (t, _), r in store.items()
                    if t == "learning_objects" and r.get("bu_id") == params.get("bu_id")]
            return rows[:1] if "LIMIT 1" in sql else rows
        return []
    monkeypatch.setattr(R, "query", fake_query)

    sm = BU2PipelineStateMachine(run_id="run_1")
    sm.execute_pass_6()
    assert fr.state == PipelineRunState.COMPRESSION_TESTED

    lo_inserts = [r for t, r in inserts if t == "learning_objects"]
    ri_inserts = [r for t, r in inserts if t == "retrieval_items"]
    # 2 questions + 1 thesis -> 3 LOs, each with 1 retrieval item
    assert len(lo_inserts) == 3
    assert len(ri_inserts) == 3
    for lo in lo_inserts:
        assert lo["bu_id"] == "bu_1"
        assert lo["run_id"] == "run_1"      # provenance, not an empty default
        assert lo["book_id"] == "book_1"
    lo_ids = {lo["id"] for lo in lo_inserts}
    for ri in ri_inserts:
        assert ri["learning_object_id"] in lo_ids


def test_d8_projection_is_idempotent(monkeypatch):
    fr = _install_run_repo(monkeypatch, PipelineRunState.VERIFIED)
    _install_verify_ctx(monkeypatch, bu=_bu_row(questions=["Why?"], theses=[]),
                        va=_pass_artifact(), blocking=0)
    store, inserts, update_calls = _install_projection_store(monkeypatch)
    # Pretend a previous resume already projected everything.
    store[("learning_objects", "bu_1::lo::q0")] = {"id": "bu_1::lo::q0", "bu_id": "bu_1"}
    store[("retrieval_items", "bu_1::lo::q0::ri::recall")] = {
        "id": "bu_1::lo::q0::ri::recall", "learning_object_id": "bu_1::lo::q0"}
    monkeypatch.setattr(R, "query", lambda sql, params=None: [{"1": 1}])

    sm = BU2PipelineStateMachine(run_id="run_1")
    sm.execute_pass_6()
    assert fr.state == PipelineRunState.COMPRESSION_TESTED
    assert inserts == []  # resume twice persists no duplicates


def test_d8_projection_does_not_mutate_ab_truth(monkeypatch):
    fr = _install_run_repo(monkeypatch, PipelineRunState.VERIFIED)
    _install_verify_ctx(monkeypatch, bu=_bu_row(), va=_pass_artifact(), blocking=0)
    store, inserts, update_calls = _install_projection_store(monkeypatch)
    monkeypatch.setattr(R, "query", lambda sql, params=None: [{"1": 1}])
    # Pre-seed projection so pass_6 only validates + transitions.
    store[("learning_objects", "bu_1::lo::q0")] = {"id": "bu_1::lo::q0", "bu_id": "bu_1"}

    sm = BU2PipelineStateMachine(run_id="run_1")
    sm.execute_pass_6()
    ab_tables = {"substrates", "knowledge_claims", "chapter_understandings",
                 "chapter_deltas", "book_understandings_v2", "evidence_trajectory",
                 "arguments", "author_mechanisms"}
    touched = {t for t, _, _ in update_calls}
    assert not (touched & ab_tables)
    written = {t for t, _ in inserts}
    assert written <= {"learning_objects", "retrieval_items"}


def test_d1_p6_missing_terminal_verification_rejected(monkeypatch):
    # RESUME Scenario 3: VERIFIED state but artifact gone -> never COMPRESSION_TESTED.
    fr = _install_run_repo(monkeypatch, PipelineRunState.VERIFIED)
    _install_verify_ctx(monkeypatch, bu=_bu_row(), va=None, blocking=0)
    sm = BU2PipelineStateMachine(run_id="run_1")
    with pytest.raises(PipelineTransitionError):
        sm.execute_pass_6()
    assert fr.state == PipelineRunState.VERIFIED
    assert fr.failure is None


# ── STATE: rejection must not poison ──────────────────────────────────────────

def test_state_invalid_transition_preserves_state(monkeypatch):
    fr = _install_run_repo(monkeypatch, PipelineRunState.PERCEIVED)
    sm = BU2PipelineStateMachine(run_id="run_1")
    with pytest.raises(PipelineTransitionError):
        sm.execute_pass_2()  # expects INSPECTED; gate fails first (no deep-read)
    assert fr.state == PipelineRunState.PERCEIVED
    assert fr.failure is None


def test_state_operational_commit_failure_marks_failed(monkeypatch):
    # Only the first commit fails (transient DB error); the FAILED marking
    # itself must still persist with a reason. A DB that is down for every
    # write cannot persist anything — that case is untestable by definition.
    fr = _install_run_repo(monkeypatch, PipelineRunState.PERCEIVED,
                           inspected=True)
    calls = {"n": 0}
    orig_update = fr.update_status

    @classmethod
    def flaky_update(cls, run_id, new_status, failure_reason=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("DB down")
        return orig_update(run_id, new_status, failure_reason=failure_reason)

    fr.update_status = flaky_update
    sm = BU2PipelineStateMachine(run_id="run_1")
    with pytest.raises(RuntimeError):
        sm.execute_pass_1()
    assert fr.state == PipelineRunState.FAILED
    assert fr.failure is not None and "DB down" in fr.failure


# ── RESUME ────────────────────────────────────────────────────────────────────

def test_resume_missing_chapter_artifact_preserves_state(monkeypatch):
    # Scenario 1: CHAPTER_MODELLED but ChapterUnderstanding missing.
    fr = _install_run_repo(monkeypatch, PipelineRunState.CHAPTER_MODELLED)
    _install_simple_gates(monkeypatch, vsu=True, cu=False, cd=True, bu=True)
    sm = BU2PipelineStateMachine(run_id="run_1")
    with pytest.raises(PipelineTransitionError):
        sm.resume()
    assert fr.state == PipelineRunState.CHAPTER_MODELLED
    assert fr.failure is None


def test_resume_book_integrated_without_verification_stays_pending(monkeypatch):
    # Scenario 2: BOOK_INTEGRATED, no verification artifact -> PENDING, never VERIFIED.
    fr = _install_run_repo(monkeypatch, PipelineRunState.BOOK_INTEGRATED)
    _install_verify_ctx(monkeypatch, bu=_bu_row(), va=None, blocking=0)
    sm = BU2PipelineStateMachine(run_id="run_1")
    with pytest.raises(PipelineTransitionError):
        sm.resume()
    assert fr.state == PipelineRunState.VERIFICATION_PENDING
    assert fr.failure is None
