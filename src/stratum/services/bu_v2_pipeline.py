"""Book Understanding 2.0 - Strict 7-Pass Pipeline Orchestrator."""

import json
import logging
from typing import Optional, Dict
from pydantic import ValidationError

from stratum.knowledge.bu_v2_models import (
    PipelineRunState,
    BUStatus,
    VerificationOutcome,
    LearningObject,
    RetrievalItem,
    LearningImportance,
    Difficulty,
    InteractionType,
    InteractionPayload,
)
from stratum.services.bu_v2_repositories import (
    PipelineRunRepository,
    VisualSemanticUnitRepository,
    ChapterUnderstandingRepository,
    ChapterDeltaRepository,
    BookUnderstandingRepository,
    VerificationRepository,
    UnderstandingGapRepository,
    LearningObjectRepository,
    RetrievalItemRepository,
)
from stratum.db import read

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
    PipelineRunState.VERIFIED: PipelineRunState.COMPRESSION_TESTED,
}


class PipelineTransitionError(Exception):
    """Validation rejection: wrong state, missing artifact, failed gate.

    A PipelineTransitionError NEVER marks the run FAILED; the persisted
    state is left unchanged so resume/repair stays possible.
    """

    pass


class BU2PipelineStateMachine:
    """Strict Orchestrator enforcing the 7-pass Book Understanding 2.0 Pipeline contract."""

    def __init__(self, run_id: str):
        self.run_id = run_id

    def _assert_and_transition(
        self, expected_current: PipelineRunState, target_next: PipelineRunState
    ):
        """Validate current state, then commit the transition.

        Validation failures raise PipelineTransitionError with state unchanged.
        Only the operational commit failure marks the run FAILED.
        """
        try:
            current_state = PipelineRunRepository.get_status(self.run_id)
        except Exception as e:
            self._fail_pipeline(f"Read run status failed: {e}")
            raise
        if current_state is None:
            raise PipelineTransitionError(f"Run {self.run_id} not found.")

        if current_state == PipelineRunState.FAILED:
            raise PipelineTransitionError(
                f"Run {self.run_id} is in FAILED state. Cannot transition."
            )

        if current_state != expected_current:
            raise PipelineTransitionError(
                f"Invalid transition: {current_state.value} -> {target_next.value}"
            )

        # Execute transition logic
        try:
            PipelineRunRepository.update_status(self.run_id, target_next)
        except Exception as e:
            self._fail_pipeline(
                f"Persist transition {expected_current.value} -> {target_next.value} failed: {e}"
            )
            raise

    def _fail_pipeline(self, reason: str):
        log.error(f"Pipeline {self.run_id} FAILED: {reason}")
        try:
            PipelineRunRepository.update_status(
                self.run_id, PipelineRunState.FAILED, failure_reason=reason
            )
        except Exception as e:
            log.error(f"Pipeline {self.run_id}: could not persist FAILED state: {e}")

    def _guarded_pass(
        self, gate, expected_current: PipelineRunState, target_next: PipelineRunState
    ):
        """WORK(order via gate) -> VALIDATE -> TRANSITION.

        gate() performs persisted-artifact validation and raises
        PipelineTransitionError (state unchanged). Operational failures
        (gate read errors, commit errors) mark the run FAILED.
        """
        try:
            gate()
        except PipelineTransitionError:
            raise
        except Exception as e:
            self._fail_pipeline(f"Artifact gate read failed: {e}")
            raise
        try:
            self._assert_and_transition(expected_current, target_next)
        except PipelineTransitionError:
            raise
        except Exception as e:
            self._fail_pipeline(str(e))
            raise

    # ── Artifact gates (validation only; never mark FAILED) ───────────────

    def _gate_pass_0(self):
        # Artifact Gate: MUST have persisted VSU and ReadingLedger for this run.
        if not VisualSemanticUnitRepository.check_exists(self.run_id):
            raise PipelineTransitionError(
                "Cannot transition to PERCEIVED: Missing VisualSemanticUnit artifacts."
            )
        if not PipelineRunRepository.check_reading_ledger_exists(self.run_id):
            raise PipelineTransitionError(
                "Cannot transition to PERCEIVED: Missing ReadingLedger artifacts."
            )

    def _gate_pass_1(self):
        # P1 INSPECT gate: at least one ledger item durably inspected.
        if not PipelineRunRepository.check_inspection_exists(self.run_id):
            raise PipelineTransitionError(
                "Cannot transition to INSPECTED: Missing persisted inspection artifacts."
            )

    def _gate_pass_2(self):
        # P2 DEEP_READ gate: explanation-structure output persisted for this run.
        if not PipelineRunRepository.check_deep_read_exists(self.run_id):
            raise PipelineTransitionError(
                "Cannot transition to DEEP_READ_COMPLETE: Missing persisted deep-read artifacts."
            )

    def _gate_pass_3(self):
        # Artifact Gate: ChapterUnderstanding + ChapterDelta persisted.
        if not ChapterUnderstandingRepository.check_exists(self.run_id):
            raise PipelineTransitionError("Missing ChapterUnderstanding artifacts.")
        if not ChapterDeltaRepository.check_exists(self.run_id):
            raise PipelineTransitionError("Missing ChapterDelta artifacts.")

    def _gate_pass_4(self):
        # Artifact Gate: canonical BookUnderstandingV2 persisted, AND its
        # chapter-model inputs (CU + CD) still present — chained custody, so
        # resume from CHAPTER_MODELLED can never skip into BOOK_INTEGRATED
        # when the chapter artifacts are gone (Scenario 1).
        if not ChapterUnderstandingRepository.check_exists(self.run_id):
            raise PipelineTransitionError("Missing ChapterUnderstanding artifacts.")
        if not ChapterDeltaRepository.check_exists(self.run_id):
            raise PipelineTransitionError("Missing ChapterDelta artifacts.")
        if not BookUnderstandingRepository.check_exists(self.run_id):
            raise PipelineTransitionError("Missing BookUnderstandingV2 artifacts.")

    def execute_pass_0(self):
        """PASS 0 PERCEIVE"""
        self._guarded_pass(self._gate_pass_0, PipelineRunState.CREATED, PipelineRunState.PERCEIVED)

    def execute_pass_1(self):
        """PASS 1 INSPECT"""
        self._guarded_pass(
            self._gate_pass_1, PipelineRunState.PERCEIVED, PipelineRunState.INSPECTED
        )

    def execute_pass_2(self):
        """PASS 2 DEEP_READ"""
        self._guarded_pass(
            self._gate_pass_2, PipelineRunState.INSPECTED, PipelineRunState.DEEP_READ_COMPLETE
        )

    def execute_pass_3(self):
        """PASS 3 CHAPTER_MODEL"""
        self._guarded_pass(
            self._gate_pass_3,
            PipelineRunState.DEEP_READ_COMPLETE,
            PipelineRunState.CHAPTER_MODELLED,
        )

    def execute_pass_4(self):
        """PASS 4 BOOK_INTEGRATE"""
        self._guarded_pass(
            self._gate_pass_4, PipelineRunState.CHAPTER_MODELLED, PipelineRunState.BOOK_INTEGRATED
        )

    # ── P5 verification hard gate ──────────────────────────────────────────

    def _load_verification_context(self):
        """Read BU + verification artifact + blocking gaps (operational).

        Read failures mark FAILED; missing/invalid content is a validation
        rejection handled by _require_verified().
        """
        try:
            bu = BookUnderstandingRepository.get_by_run(self.run_id)
            va = VerificationRepository.get_latest(self.run_id)
            blocking = UnderstandingGapRepository.get_blocking_gaps_count(self.run_id)
        except Exception as e:
            self._fail_pipeline(f"Verification read failed: {e}")
            raise
        return bu, va, blocking

    def _require_verified(self, bu, va, blocking: int):
        """CASE A-G hard gate. Raises PipelineTransitionError (state unchanged)
        unless: artifact exists AND outcome == PASS AND artifact run/book match
        the canonical BU AND zero unresolved gaps (artifact self-report + live
        blocking count)."""
        if bu is None:
            raise PipelineTransitionError(
                f"NOT VERIFIED: missing BookUnderstandingV2 for run {self.run_id}."
            )
        expected_book = bu.get("book_id")
        if not expected_book:
            raise PipelineTransitionError(
                f"NOT VERIFIED: BookUnderstandingV2 {bu.get('id')} has no book provenance; repair required."
            )
        if va is None:
            raise PipelineTransitionError(
                f"NOT VERIFIED (CASE A): no verification artifact for run {self.run_id}."
            )
        if va.run_id != self.run_id:
            raise PipelineTransitionError(
                f"NOT VERIFIED (CASE F): verification artifact {va.id} belongs to run {va.run_id}."
            )
        if va.book_id != expected_book:
            raise PipelineTransitionError(
                f"NOT VERIFIED (CASE G): verification artifact {va.id} book {va.book_id} "
                f"!= canonical book {expected_book}."
            )
        if va.status == VerificationOutcome.FAIL:
            raise PipelineTransitionError(
                f"NOT VERIFIED (CASE B): verification artifact {va.id} outcome is FAIL."
            )
        if va.status == VerificationOutcome.BLOCKED:
            raise PipelineTransitionError(
                f"NOT VERIFIED (CASE C): verification artifact {va.id} outcome is BLOCKED."
            )
        if va.status != VerificationOutcome.PASS:
            raise PipelineTransitionError(
                f"NOT VERIFIED: verification artifact {va.id} outcome {va.status.value} is not PASS."
            )
        if (va.unresolved_gap_count or 0) != 0:
            raise PipelineTransitionError(
                f"NOT VERIFIED: verification artifact {va.id} self-reports "
                f"{va.unresolved_gap_count} unresolved gaps."
            )
        if blocking > 0:
            raise PipelineTransitionError(
                f"NOT VERIFIED (CASE D): {blocking} unresolved blocking gaps for run {self.run_id}."
            )

    def execute_pass_5_verify(self):
        """PASS 5 ADVERSARIAL_VERIFY"""
        try:
            current = PipelineRunRepository.get_status(self.run_id)
        except Exception as e:
            self._fail_pipeline(f"Read run status failed: {e}")
            raise
        if current == PipelineRunState.BOOK_INTEGRATED:
            try:
                PipelineRunRepository.update_status(
                    self.run_id, PipelineRunState.VERIFICATION_PENDING
                )
            except Exception as e:
                self._fail_pipeline(f"Enter VERIFICATION_PENDING failed: {e}")
                raise
        elif current != PipelineRunState.VERIFICATION_PENDING:
            raise PipelineTransitionError(
                f"Invalid transition into verification from {(current.value if current else None)}."
            )
        # Hard gate (validation only): CASE A-G.
        bu, va, blocking = self._load_verification_context()
        self._require_verified(bu, va, blocking)
        # Commit VERIFIED.
        self._guarded_pass(
            lambda: None, PipelineRunState.VERIFICATION_PENDING, PipelineRunState.VERIFIED
        )

    # ── P6 learning projection + terminal gate ─────────────────────────────

    def _project_learning(self, bu: dict):
        """Project canonical BU -> LearningObject -> RetrievalItem (P8/P9).

        Deterministic IDs + existence checks make resume idempotent: a second
        run persists nothing new. Projection never mutates A/B truth sources
        (substrates / knowledge claims / chapter or book understanding rows);
        it only inserts derived learning rows.
        """
        bu_id = bu["id"]
        run_id = bu["run_id"]
        book_id = bu.get("book_id")
        if not run_id or not book_id:
            raise PipelineTransitionError(
                f"Cannot project learning: BU {bu_id} lacks run/book provenance."
            )

        def _as_list(raw):
            if raw is None:
                return []
            if isinstance(raw, str):
                return json.loads(raw) if raw else []
            return list(raw)

        plans = []
        for i, q in enumerate(_as_list(bu.get("governing_questions_json"))):
            plans.append((f"{bu_id}::lo::q{i}", str(q), LearningImportance.CORE, Difficulty.MEDIUM))
        for i, t in enumerate(_as_list(bu.get("central_theses_json"))):
            plans.append((f"{bu_id}::lo::t{i}", str(t), LearningImportance.CORE, Difficulty.HARD))

        try:
            for lo_id, goal, importance, difficulty in plans:
                if read("learning_objects", lo_id) is None:
                    LearningObjectRepository.save(
                        LearningObject(
                            id=lo_id,
                            bu_id=bu_id,
                            run_id=run_id,
                            book_id=book_id,
                            learning_goal=goal,
                            knowledge_type="conceptual",
                            importance=importance,
                            difficulty=difficulty,
                            target_refs=[],
                            prerequisites_refs=[],
                            mastery_requirements=[goal],
                            assessment_modes=["EXPLAIN_WHY"],
                            source_refs=[bu_id],
                        )
                    )
                ri_id = f"{lo_id}::ri::recall"
                if read("retrieval_items", ri_id) is None:
                    RetrievalItemRepository.save(
                        RetrievalItem(
                            id=ri_id,
                            learning_object_id=lo_id,
                            interaction_type=InteractionType.FREE_RECALL,
                            payload=InteractionPayload(
                                question=f"Recall: {goal}",
                                options=[],
                                expected_answer="",
                            ),
                        )
                    )
        except PipelineTransitionError:
            raise
        except Exception as e:
            self._fail_pipeline(f"Learning projection failed: {e}")
            raise

    def execute_pass_6(self):
        """PASS 6 COMPRESSION_TEACH_TEST"""
        # Terminal gate: never trust VERIFIED state alone; the durable PASS
        # verification artifact must still exist (resume Scenario 3).
        bu, va, blocking = self._load_verification_context()
        self._require_verified(bu, va, blocking)
        assert bu is not None
        # WORK -> PERSIST (idempotent) -> VALIDATE -> TRANSITION.
        self._project_learning(bu)
        if not LearningObjectRepository.check_exists_for_bu(bu["id"]):
            raise PipelineTransitionError(
                f"Cannot transition to COMPRESSION_TESTED: learning projection missing for BU {bu['id']}."
            )
        self._guarded_pass(
            lambda: None, PipelineRunState.VERIFIED, PipelineRunState.COMPRESSION_TESTED
        )

    def resume(self):
        """Resume pipeline from last durable checkpoint idempotently."""
        state = PipelineRunRepository.get_status(self.run_id)
        if state == PipelineRunState.FAILED:
            log.warning("Cannot resume a FAILED pipeline automatically.")
            return

        if state == PipelineRunState.CREATED:
            self.execute_pass_0()
            state = PipelineRunRepository.get_status(self.run_id)

        if state == PipelineRunState.PERCEIVED:
            self.execute_pass_1()
            state = PipelineRunRepository.get_status(self.run_id)

        if state == PipelineRunState.INSPECTED:
            self.execute_pass_2()
            state = PipelineRunRepository.get_status(self.run_id)

        if state == PipelineRunState.DEEP_READ_COMPLETE:
            self.execute_pass_3()
            state = PipelineRunRepository.get_status(self.run_id)

        if state == PipelineRunState.CHAPTER_MODELLED:
            self.execute_pass_4()
            state = PipelineRunRepository.get_status(self.run_id)

        if state in (PipelineRunState.BOOK_INTEGRATED, PipelineRunState.VERIFICATION_PENDING):
            self.execute_pass_5_verify()
            state = PipelineRunRepository.get_status(self.run_id)

        if state == PipelineRunState.VERIFIED:
            self.execute_pass_6()
