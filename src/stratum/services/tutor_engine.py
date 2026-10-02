"""P9 Adaptive Learning (§§84-85, §§91-93): tutor state machine + diagnosis.

- Tutor loop (§91): SELECT_OBJECTIVE -> DIAGNOSE -> TEACH -> GUIDED_EXAMPLE
  -> ACTIVE_RESPONSE -> JUDGE -> {TRANSFER -> NEXT | ERROR_CLASSIFY ->
  REMEDIATE -> loop} -> MASTERY. Illegal transitions rejected.
- Diagnose (§84): pick high-centrality x high-prerequisite-value x
  high-discrimination objects.
- Minimum subgraph (§83) reuses learning_compiler.minimum_subgraph.
- Prerequisite repair (§85): recurse X -> P1 -> P2 to the knowledge boundary.
- Error policy (§92): C-warehouse error taxonomy -> remediation actions.
- Confident-wrong (§93): wrong + high confidence -> MISCONCEPTION_CANDIDATE
  with contrastive strategy; feedback is mandatory (§88).
- MasteryDimensions (§86) is a derived, non-persisted assessment view —
  the sole mastery authority stays cx.learning_progress.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from stratum.knowledge.bu_v2_models import (
    ErrorKind, MasteryDimensions, MisconceptionCandidate, TutorSession,
    TutorState,
)

_TUTOR_TRANSITIONS = {
    TutorState.SELECT_OBJECTIVE: frozenset({TutorState.DIAGNOSE}),
    TutorState.DIAGNOSE: frozenset({TutorState.TEACH, TutorState.SELECT_OBJECTIVE}),
    TutorState.TEACH: frozenset({TutorState.GUIDED_EXAMPLE}),
    TutorState.GUIDED_EXAMPLE: frozenset({TutorState.ACTIVE_RESPONSE}),
    TutorState.ACTIVE_RESPONSE: frozenset({TutorState.JUDGE}),
    TutorState.JUDGE: frozenset({TutorState.TRANSFER, TutorState.REMEDIATE}),
    TutorState.TRANSFER: frozenset({TutorState.MASTERY, TutorState.NEXT}),
    TutorState.REMEDIATE: frozenset({TutorState.TEACH, TutorState.GUIDED_EXAMPLE,
                                     TutorState.DIAGNOSE}),
    TutorState.MASTERY: frozenset({TutorState.NEXT}),
    TutorState.NEXT: frozenset({TutorState.SELECT_OBJECTIVE}),
}

_ERROR_POLICY = {
    ErrorKind.KNOWLEDGE_STRUCTURAL: ["prerequisite repair"],
    ErrorKind.UNDERSTANDING_DEVIATION: ["contrast", "counterexample"],
    ErrorKind.APPLICATION_ERROR: ["worked example", "faded example", "independent problem"],
    ErrorKind.METACOGNITIVE: ["confidence calibration"],
}


def tutor_transition(session: TutorSession, to_state: TutorState,
                     note: str = "") -> TutorSession:
    allowed = _TUTOR_TRANSITIONS.get(session.current_state, frozenset())
    if to_state not in allowed:
        raise ValueError(
            f"Illegal tutor transition: {session.current_state.value} -> {to_state.value}.")
    data = session.model_dump()
    data["current_state"] = to_state
    data["history"] = session.history + [f"{session.current_state.value}->{to_state.value}" + (f":{note}" if note else "")]
    return TutorSession(**data)


def diagnose(candidates: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    """§84: score = centrality * prerequisite_value * discrimination.
    Each candidate: {ref, centrality, prereq_value, discrimination}."""
    if not candidates:
        return None
    return max(candidates, key=lambda c: (
        c.get("centrality", 0.0) * c.get("prereq_value", 0.0) * c.get("discrimination", 0.0)))


def repair_prerequisites(stuck_ref: str, prereq_map: Dict[str, List[str]],
                         mastered: List[str]) -> List[str]:
    """§85: recurse to the true knowledge boundary (first unmastered chain)."""
    chain: List[str] = []
    stack = [stuck_ref]
    seen = set()
    while stack:
        node = stack.pop()
        if node in seen or node in mastered:
            continue
        seen.add(node)
        if node != stuck_ref:
            chain.append(node)
        stack.extend(prereq_map.get(node, []))
    return chain


def error_policy(kind: ErrorKind) -> List[str]:
    """§92 taxonomy -> remediation actions."""
    return list(_ERROR_POLICY[kind])


def confident_wrong(answer: str, correct: bool,
                    confidence_before: float) -> MisconceptionCandidate:
    """§93: wrong + high confidence -> MISCONCEPTION_CANDIDATE."""
    is_candidate = (not correct) and confidence_before >= 0.7
    return MisconceptionCandidate(
        answer=answer, correctness=correct,
        confidence_before_answer=confidence_before,
        is_candidate=is_candidate,
        strategy=("contrastive explanation -> counterexample -> immediate "
                  "retest -> delayed retest" if is_candidate else ""))


def assess_dimensions(ref: str, evidence: Dict[str, float]) -> MasteryDimensions:
    """§86 eight-dimension derived view. Pure function of caller-supplied
    evidence (e.g. aggregated from cx.learning_progress reads) — never a
    store, never an authority."""
    keys = ("recognition", "recall", "explanation", "discrimination",
            "application", "transfer", "stability", "confidence")
    clamped = {k: min(1.0, max(0.0, float(evidence.get(k, 0.0)))) for k in keys}
    return MasteryDimensions(ref=ref, **clamped)


def judge_response(expected: str, given: str,
                   confidence_before: float) -> Tuple[bool, List[str], MisconceptionCandidate]:
    """JUDGE node: correctness + mandatory feedback (§88) + misconception watch."""
    correct = expected.strip().lower() == given.strip().lower()
    feedback = (["correct: transfer probe next"] if correct
                else ["incorrect: corrective feedback required"] + error_policy(ErrorKind.UNDERSTANDING_DEVIATION))
    return correct, feedback, confident_wrong(given, correct, confidence_before)
