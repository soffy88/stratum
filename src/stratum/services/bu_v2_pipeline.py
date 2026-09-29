"""Book Understanding 2.0 - Strict 7-Pass Pipeline Orchestrator."""

import logging
from typing import Optional, Dict
from pydantic import ValidationError

from stratum.knowledge.bu_v2_models import PipelineRunState
from stratum.services.bu_v2_repositories import PipelineRunRepository

log = logging.getLogger(__name__)

# Define strict legal transitions
VALID_TRANSITIONS: Dict[PipelineRunState, PipelineRunState] = {
    PipelineRunState.CREATED: PipelineRunState.PERCEIVED,
    PipelineRunState.PERCEIVED: PipelineRunState.INSPECTED,
    PipelineRunState.INSPECTED: PipelineRunState.DEEP_READ_COMPLETE,
    PipelineRunState.DEEP_READ_COMPLETE: PipelineRunState.CHAPTER_MODELLED,
    PipelineRunState.CHAPTER_MODELLED: PipelineRunState.BOOK_INTEGRATED,
    PipelineRunState.BOOK_INTEGRATED: PipelineRunState.VERIFICATION_PENDING,
    PipelineRunState.VERIFICATION_PENDING: PipelineRunState.VERIFIED,
    PipelineRunState.VERIFIED: PipelineRunState.COMPRESSION_TESTED
}

class PipelineTransitionError(Exception):
    pass

class BU2PipelineStateMachine:
    """Strict Orchestrator enforcing the 7-pass Book Understanding 2.0 Pipeline contract."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        
    def _assert_and_transition(self, expected_current: PipelineRunState, target_next: PipelineRunState):
        current_state = PipelineRunRepository.get_status(self.run_id)
        if current_state is None:
            raise PipelineTransitionError(f"Run {self.run_id} not found.")
            
        if current_state == PipelineRunState.FAILED:
            raise PipelineTransitionError(f"Run {self.run_id} is in FAILED state. Cannot transition.")
            
        if current_state != expected_current:
            # If already at or past the target, idempotency logic could apply, but for strictness:
            raise PipelineTransitionError(f"Invalid transition: {current_state.value} -> {target_next.value}")
            
        # Execute transition logic
        PipelineRunRepository.update_status(self.run_id, target_next)

    def _fail_pipeline(self, reason: str):
        log.error(f"Pipeline {self.run_id} FAILED: {reason}")
        PipelineRunRepository.update_status(self.run_id, PipelineRunState.FAILED, failure_reason=reason)

    def execute_pass_0(self):
        """PASS 0 PERCEIVE"""
        try:
            # Implement real perceive logic (e.g., multimodal inventory generation)
            # Contract: Must produce VisualSemanticUnit, update ReadingLedger.
            self._assert_and_transition(PipelineRunState.CREATED, PipelineRunState.PERCEIVED)
        except Exception as e:
            self._fail_pipeline(str(e))
            raise

    def execute_pass_1(self):
        """PASS 1 INSPECT"""
        try:
            self._assert_and_transition(PipelineRunState.PERCEIVED, PipelineRunState.INSPECTED)
        except Exception as e:
            self._fail_pipeline(str(e))
            raise

    def execute_pass_2(self):
        """PASS 2 DEEP_READ"""
        try:
            # Contract: Deep Read to extract Argument, AuthorMechanism, etc.
            self._assert_and_transition(PipelineRunState.INSPECTED, PipelineRunState.DEEP_READ_COMPLETE)
        except Exception as e:
            self._fail_pipeline(str(e))
            raise

    def execute_pass_3(self):
        """PASS 3 CHAPTER_MODEL"""
        try:
            # Contract: Generate ChapterUnderstanding & ChapterDelta
            self._assert_and_transition(PipelineRunState.DEEP_READ_COMPLETE, PipelineRunState.CHAPTER_MODELLED)
        except Exception as e:
            self._fail_pipeline(str(e))
            raise

    def execute_pass_4(self):
        """PASS 4 BOOK_INTEGRATE"""
        try:
            # Contract: Generate BookUnderstandingV2
            self._assert_and_transition(PipelineRunState.CHAPTER_MODELLED, PipelineRunState.BOOK_INTEGRATED)
        except Exception as e:
            self._fail_pipeline(str(e))
            raise

    def execute_pass_5_verify(self):
        """PASS 5 ADVERSARIAL_VERIFY"""
        try:
            # Contract: Check verification gaps, transition to VERIFICATION_PENDING -> VERIFIED
            self._assert_and_transition(PipelineRunState.BOOK_INTEGRATED, PipelineRunState.VERIFICATION_PENDING)
            # Run verifications...
            self._assert_and_transition(PipelineRunState.VERIFICATION_PENDING, PipelineRunState.VERIFIED)
        except Exception as e:
            self._fail_pipeline(str(e))
            raise

    def execute_pass_6(self):
        """PASS 6 COMPRESSION_TEACH_TEST"""
        try:
            # Contract: Cognitive compression and projection extraction
            self._assert_and_transition(PipelineRunState.VERIFIED, PipelineRunState.COMPRESSION_TESTED)
        except Exception as e:
            self._fail_pipeline(str(e))
            raise

    def resume(self):
        """Resume pipeline from last durable checkpoint."""
        state = PipelineRunRepository.get_status(self.run_id)
        if state == PipelineRunState.FAILED:
            log.warning("Cannot resume a FAILED pipeline automatically.")
            return

        if state == PipelineRunState.CREATED:
            self.execute_pass_0()
            state = PipelineRunState.PERCEIVED
            
        if state == PipelineRunState.PERCEIVED:
            self.execute_pass_1()
            state = PipelineRunState.INSPECTED
            
        if state == PipelineRunState.INSPECTED:
            self.execute_pass_2()
            state = PipelineRunState.DEEP_READ_COMPLETE
            
        if state == PipelineRunState.DEEP_READ_COMPLETE:
            self.execute_pass_3()
            state = PipelineRunState.CHAPTER_MODELLED
            
        if state == PipelineRunState.CHAPTER_MODELLED:
            self.execute_pass_4()
            state = PipelineRunState.BOOK_INTEGRATED
            
        if state in (PipelineRunState.BOOK_INTEGRATED, PipelineRunState.VERIFICATION_PENDING):
            self.execute_pass_5_verify()
            state = PipelineRunState.VERIFIED
            
        if state == PipelineRunState.VERIFIED:
            self.execute_pass_6()
