"""Tests for Book Understanding 2.0 P4-P9 Foundation Contract."""

import pytest
from pydantic import ValidationError

from stratum.knowledge.bu_v2_models import (
    ChapterUnderstanding, ChapterDelta, BookUnderstandingV2,
    UnderstandingGap, LearningObject, RetrievalItem,
    BUStatus, GapStatus, GapType, Severity, Difficulty, LearningImportance,
    InteractionType, Scope
)
from stratum.services.bu_v2_pipeline import BU2PipelineStateMachine, PipelineTransitionError, PipelineRunState

def test_chapter_understanding_contract():
    # P4 Contract: Cannot use random dicts, must follow schema
    cu = ChapterUnderstanding(
        id="cu_1",
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
        chapter_id="ch_1",
        new_concepts_refs=["concept_a"],
        revises_prior_refs=["claim_x"]
    )
    assert "concept_a" in cd.new_concepts_refs

def test_book_understanding_v2_contract():
    # P5 Contract: Working vs Verified BU
    bu = BookUnderstandingV2(
        id="bu_1",
        substrate_id="sub_1",
        status=BUStatus.DRAFT,
        governing_questions=["Why do nations fail?"],
        argument_architecture={"root_arguments": ["arg_1"], "supporting_arguments": []}
    )
    assert bu.status == BUStatus.DRAFT
    
    # ENUM Validation Failure
    with pytest.raises(ValidationError):
        BookUnderstandingV2(
            id="bu_2",
            substrate_id="sub_2",
            status="INVALID_STATUS"
        )

def test_verification_gap_contract():
    # P6 Contract: Verification lifecycle
    gap = UnderstandingGap(
        id="gap_1",
        type=GapType.MISSING_EVIDENCE,
        severity=Severity.HIGH,
        question="Where is the proof for claim X?",
        status=GapStatus.OPEN
    )
    assert gap.severity == Severity.HIGH
    
    with pytest.raises(ValidationError):
        UnderstandingGap(
            id="gap_2",
            type="RANDOM_GAP", # Fails GapType Enum
            severity=Severity.LOW,
            question="Bad gap"
        )

def test_learning_contract():
    # P8/P9 Contract
    lo = LearningObject(
        id="lo_1",
        bu_id="bu_1",
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
            
    monkeypatch.setattr("stratum.services.bu_v2_pipeline.PipelineRunRepository", MockRepo)
    
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
