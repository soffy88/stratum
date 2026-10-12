"""Accuracy and argument structure: claim verification against the anchored
passage, passage-level claim anchoring, reconstructed argument chains, the H7
gate, and the rule that a run failing a hard gate is never VERIFIED.

All offline: StaticProvider and in-memory chapters.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from stratum.knowledge.bu_v2_models import ChapterUnderstanding, EvidenceProgramItem
from stratum.services.bu_v2_argument_analyzer import ArgumentAnalyzer
from stratum.services.bu_v2_claim_verifier import ClaimVerifier, parse_verdict
from stratum.services.bu_v2_hard_gates import HardGateEvaluator
from stratum.services.bu_v2_producer import Chapter, ChapterUnderstandingProducer, EvidenceArtifact
from stratum.services.bu_v2_provider import StaticProvider

TEXT = (
    "3. Derivatives\n\n"
    "The derivative of a function f at a point x is the limit of the difference "
    "quotient as h approaches zero. When this limit exists we say f is "
    "differentiable at x. "
    "Theorem 1. If f is differentiable at x then f is continuous at x. "
    "Proof. Write f(x+h) - f(x) as the difference quotient times h and let h tend "
    "to zero; the product tends to the derivative times zero, which is zero. "
    "Hence f(x+h) tends to f(x), which is continuity. "
    "The converse is false: the absolute value function is continuous at zero but "
    "has no derivative there because its graph has a corner."
)


def _chapter() -> Chapter:
    return Chapter(chapter_id="ch3", number=3, title="3. Derivatives", text=TEXT, end=len(TEXT))


def test_parse_verdict_reads_first_yes_no_token():
    assert parse_verdict("YES") is True
    assert parse_verdict("thinking... the answer is NO.") is False
    assert parse_verdict("") is None


def test_best_passage_finds_supporting_sentence_for_paraphrase():
    ch = _chapter()
    found = ch.best_passage("Every differentiable function is continuous at that point")
    assert found is not None
    assert "continuous" in found[1] and "differentiable" in found[1]


def test_best_passage_refuses_unrelated_claim():
    assert _chapter().best_passage("Photosynthesis converts sunlight into sugar in leaves") is None


def _payload() -> dict:
    return {
        "chapter_question": "What is a derivative and what does differentiability imply?",
        "chapter_goal": "Know the definition and its link to continuity",
        "chapter_thesis": "Differentiability is a limit condition that implies continuity",
        "concepts": [{"name": "Derivative", "definition": "limit of the difference quotient"}],
        "claims": [
            {"text": "A differentiable function is continuous at that point", "quote": ""},
            {"text": "The absolute value function has no derivative at zero", "quote": ""},
        ],
        "arguments": [
            {
                "claim": "If f is differentiable at x then f is continuous at x",
                "premises": ["f is differentiable at x"],
                "steps": [
                    "write f(x+h)-f(x) as the difference quotient times h",
                    "let h tend to zero so the product tends to zero",
                ],
                "conclusion": "f(x+h) tends to f(x), so f is continuous at x",
                "quote": "If f is differentiable at x then f is continuous at x",
            },
            {"claim": "no steps given", "steps": [], "conclusion": "x"},
        ],
        "mechanisms": [],
    }


def test_producer_reconstructs_located_arguments_only():
    prod = ChapterUnderstandingProducer(provider=StaticProvider(json.dumps(_payload())))
    cu, _delta, evidence = prod.produce(_chapter(), run_id="br_t", book_id="b")
    assert len(cu.chapter_arguments) == 1  # the step-less one is dropped
    arg = cu.chapter_arguments[0]
    assert cu.arguments_refs == [arg.id]
    assert len(arg.inference_steps) == 2 and arg.conclusion
    ev_ids = {e.evidence_id for e in evidence}
    assert arg.evidence_refs[0] in ev_ids
    # Paraphrased claims are anchored on a supporting passage, not a term mention.
    kinds = {e.kind for e in evidence}
    assert "CLAIM_PASSAGE" in kinds or "CLAIM" in kinds


def test_argument_chain_per_reconstructed_argument():
    prod = ChapterUnderstandingProducer(provider=StaticProvider(json.dumps(_payload())))
    cu, _d, _ev = prod.produce(_chapter(), run_id="br_t", book_id="b")
    analysis = ArgumentAnalyzer().analyze([cu], run_id="br_t", book_id="b")
    arg_chains = [c for c in analysis.chains if c.claim.label.startswith("If f is differentiable")]
    assert len(arg_chains) == 1
    chain = arg_chains[0]
    assert chain.complete and len(chain.reasoning) == 2


def _cu_with_claims(n_good: int, n_bad: int) -> tuple[ChapterUnderstanding, list[EvidenceArtifact]]:
    evidence, program = [], []
    for i in range(n_good + n_bad):
        good = i < n_good
        ev = EvidenceArtifact.make(
            "r", "ch1", "CLAIM", f"char:{i}", "GOOD passage" if good else "BAD passage"
        )
        evidence.append(ev)
        program.append(
            EvidenceProgramItem(
                claim_ref=f"claim {i}", evidence_refs=[ev.evidence_id], is_supported=True
            )
        )
    cu = ChapterUnderstanding(id="cu", run_id="r", chapter_id="ch1", evidence_program=program)
    return cu, evidence


def test_claim_verifier_marks_unsupported_claims():
    cu, evidence = _cu_with_claims(3, 2)
    judge = lambda prompt: "YES" if "GOOD passage" in prompt else "NO"  # noqa: E731
    cv = ClaimVerifier(judge, workers=2).verify([cu], evidence)
    assert (cv.checked, cv.supported, cv.rejected) == (5, 3, 2)
    assert [ep.is_supported for ep in cu.evidence_program] == [True] * 3 + [False] * 2
    assert sum(1 for e in evidence if e.verified is False) == 2


def test_h7_fails_when_reading_over_reaches():
    cu, evidence = _cu_with_claims(1, 4)
    cv = ClaimVerifier(lambda p: "YES" if "GOOD" in p else "NO", workers=1).verify([cu], evidence)
    gate = HardGateEvaluator._h7_claims_supported(cv)
    assert not gate.passed
    cu2, ev2 = _cu_with_claims(9, 1)
    cv2 = ClaimVerifier(lambda p: "YES" if "GOOD" in p else "NO", workers=1).verify([cu2], ev2)
    assert HardGateEvaluator._h7_claims_supported(cv2).passed


def test_accuracy_samples_only_supported_claims():
    from stratum.services.bu_v2_hard_gates import _sample_claims
    import random

    cu, evidence = _cu_with_claims(2, 3)
    for ep in cu.evidence_program[2:]:
        ep.is_supported = False
    pairs = _sample_claims([cu], evidence, 30, random.Random(0))
    assert len(pairs) == 2


def test_failed_hard_gate_downgrades_verified_run():
    from tests.bu2 import test_real_book_pipeline as t

    result = t.run_pipeline(StaticProvider(t.chapter_payload()), persist=False)
    if result.hard_gates is not None and not result.hard_gates.all_passed:
        assert result.bu.status.value != "VERIFIED"
        assert any("hard gates FAIL" in f for f in result.failures)
    _ = SimpleNamespace


def test_claim_verifier_reanchors_to_a_supporting_passage():
    ch = _chapter()
    claim = "The absolute value function is continuous at zero but not differentiable there"
    ev = EvidenceArtifact.make(
        "r", "ch3", "CLAIM_TERM_ANCHOR", "char:0", "3. Derivatives The derivative of a function"
    )
    ep = EvidenceProgramItem(claim_ref=claim, evidence_refs=[ev.evidence_id], is_supported=True)
    cu = ChapterUnderstanding(id="cu", run_id="r", chapter_id="ch3", evidence_program=[ep])
    evidence = [ev]
    judge = lambda p: "YES" if "corner" in p.split("SOURCE:")[1].split("CLAIM:")[0] else "NO"  # noqa: E731
    cv = ClaimVerifier(judge, workers=1).verify([cu], evidence, texts={"ch3": ch})
    assert cv.supported == 1 and cv.reanchored == 1
    assert ep.is_supported and ep.evidence_refs[0] != ev.evidence_id
    assert "corner" in evidence[-1].quote
