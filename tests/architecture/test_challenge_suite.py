"""P6 challenge suite behavior tests (§§54-58, §§117-118)."""

from stratum.knowledge.bu_v2_models import (
    HoldoutItem, MinimalPairCase, MutationCase, MutationType,
)
from stratum.services.challenge_suite import (
    chapter_ablation, holdout_probe, minimal_pair_check, mutation_verdict,
    plan_targeted_reread, premise_ablation, reconstruct_revision,
)


def test_holdout_exposes_gap_not_confident_completion():
    item = HoldoutItem(holdout_id="h1", category="visual",
                       probe_question="What does Fig 2 show?",
                       required_refs=["vsu_fig2", "k9"])
    r = holdout_probe(item, ["vsu_fig2", "k1"])
    assert r["passed"] is False and r["exposed_gap"] is True
    assert r["missing_refs"] == ["k9"]
    r2 = holdout_probe(item, ["vsu_fig2", "k9"])
    assert r2["passed"] is True


def _case(mt, mutated, cid="m1"):
    return MutationCase(id=cid, mutation_type=mt, target_ref="t1",
                        original_statement="orig", mutated_statement=mutated)


def test_all_mutation_types_rejected():
    assert mutation_verdict(_case(MutationType.WRONG_STANCE, "AUTHOR_ASSERTED"),
                            {"stance": "QUOTED_POSITION"}).rejected is True
    assert mutation_verdict(_case(MutationType.WRONG_QUANTIFIER, "all"),
                            {"quantifier": "some"}).rejected is True
    assert mutation_verdict(_case(MutationType.MISSING_CONDITION, "X"),
                            {"conditions": ["only if C"]}).rejected is True
    assert mutation_verdict(_case(MutationType.REVERSED_CAUSALITY, "B->A"),
                            {"causal_links": ["A->B"]}).rejected is True
    assert mutation_verdict(_case(MutationType.WRONG_CHAPTER_RELATION, "X REQUIRES Y"),
                            {"chapter_relations": ["X SUPPORTS Y"]}).rejected is True
    assert mutation_verdict(_case(MutationType.FAKE_EVIDENCE, "ev_fake"),
                            {"evidence_refs": ["ev1"]}).rejected is True
    assert mutation_verdict(_case(MutationType.OVERSTATED_CONCLUSION, "always"),
                            {"conclusion_strength": "qualified"}).rejected is True


def test_mutation_negative_controls_not_rejected():
    # Truth actually supports it -> must NOT reject (verifier is precise).
    assert mutation_verdict(_case(MutationType.WRONG_STANCE, "AUTHOR_ASSERTED"),
                            {"stance": "AUTHOR_ASSERTED"}).rejected is False
    assert mutation_verdict(_case(MutationType.FAKE_EVIDENCE, "ev1"),
                            {"evidence_refs": ["ev1"]}).rejected is False
    assert mutation_verdict(_case(MutationType.MISSING_CONDITION, "X"),
                            {"conditions": []}).rejected is False


def test_chapter_ablation_breaks_sole_sourced_thesis():
    theses = [{"id": "T1", "chapter_refs": ["ch2"]},
              {"id": "T2", "chapter_refs": ["ch2", "ch5"]}]
    args = [{"id": "a1", "chapter_refs": ["ch2"]}]
    deps = [{"source_chapter": "ch2", "target_chapter": "ch5"}]
    r = chapter_ablation("ch2", theses, args, deps)
    assert "T1" in r.impacted_theses and "T2" not in r.impacted_theses
    assert "a1" in r.broken_arguments
    assert r.verdict.value == "ARGUMENT_INVALID"
    r2 = chapter_ablation("ch9", theses, args, deps)
    assert r2.verdict.value == "NO_MEANINGFUL_EFFECT"


def test_premise_ablation_three_verdicts():
    full = {"id": "a", "premises": ["P1", "P2"], "warrants": ["W"]}
    assert premise_ablation(full, "P1").verdict.value == "SUPPORT_WEAKENED"
    last = {"id": "a", "premises": ["P1"], "warrants": []}
    assert premise_ablation(last, "P1").verdict.value == "ARGUMENT_INVALID"
    assert premise_ablation(full, "PX").verdict.value == "NO_MEANINGFUL_EFFECT"


def test_revision_chain_preserves_originals():
    steps = [{"claim_ref": "X", "evolution_type": "REFINE"},
             {"claim_ref": "X+C", "evolution_type": "QUALIFY"},
             {"claim_ref": "X'", "evolution_type": "REVISE"}]
    r = reconstruct_revision(steps)
    assert r["ok"] is True and r["originals_preserved"] is True
    assert len(r["chain"]) == 3
    bad = reconstruct_revision([{"claim_ref": "X", "evolution_type": "SUMMARIZE"}])
    assert bad["ok"] is False


def test_minimal_pairs():
    r = minimal_pair_check(MinimalPairCase(
        id="mp1", side_a="may", side_b="does", distinction="may/does"))
    assert r["distinguished"] is True and r["slots"] == ["possibility", "actuality"]
    r2 = minimal_pair_check(MinimalPairCase(
        id="mp2", side_a="x", side_b="x", distinction="some/all"))
    assert r2["distinguished"] is False
    r3 = minimal_pair_check(MinimalPairCase(
        id="mp3", side_a="a", side_b="b", distinction="unknown/thing"))
    assert r3["distinguished"] is False


def test_reread_plan_bounded_never_full():
    gap = {"id": "g1", "evidence_targets": ["ch2", "ch7"],
           "required_action": "reread figure context"}
    idx = {"ch2": ["ch2:pp10-12", "ch2:fig1"], "ch7": ["ch7:pp40"]}
    plan = plan_targeted_reread(gap, idx)
    assert plan["regions"] == ["ch2:pp10-12", "ch2:fig1", "ch7:pp40"]
    assert plan["full_rerun"] is False
    assert plan["steps"] == ["locate", "reread", "repair", "propagate", "reverify"]
