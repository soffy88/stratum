"""P8 compiler + P9 tutor + benchmark gold tests (§§80-87, §§91-93, §§113-120)."""

import pytest

from stratum.knowledge.bu_v2_models import (
    BookGold, ErrorKind, EvidenceGold, ResolutionGold, TutorSession,
    TutorState,
)
from stratum.services.benchmark_gold import (
    baseline_registry, score_book, score_resolution, score_trajectory,
)
from stratum.services.learning_compiler import (
    compile_graph, compile_path, interaction_for, minimum_subgraph,
    strategy_router,
)
from stratum.services.tutor_engine import (
    assess_dimensions, confident_wrong, diagnose, error_policy,
    judge_response, repair_prerequisites, tutor_transition,
)
from stratum.knowledge.bu_v2_models import InteractionType


def _bu():
    return {"governing_questions": ["Why?"],
            "concepts": ["cA", "cB"],
            "mechanisms": ["m1"], "major_arguments": ["a1"]}


def test_strategy_router_per_knowledge_type():
    assert strategy_router("factual") == ["recall", "discrimination", "spacing"]
    assert "counterfactual" in strategy_router("rationale")
    assert "teach-back" in strategy_router("rationale")
    assert strategy_router("unknown-type") == ["self-explanation", "teach-back"]
    assert interaction_for("argument") == InteractionType.ARGUMENT_RECONSTRUCTION
    assert interaction_for("procedural") == InteractionType.SOLVE


def test_compile_graph_ordering():
    g = compile_graph("g1", "bu_1", _bu())
    refs = [n.learning_object_ref for n in g.nodes]
    assert refs[0].endswith("::lo::problem")
    assert refs.index("bu_1::lo::thesis") > refs.index("bu_1::lo::concept0")
    assert any(e.relation == "QUALIFIES" for e in g.edges)
    assert any(e.relation == "APPLIES" for e in g.edges)
    # dedup: compile twice over same content keeps node set stable
    g2 = compile_graph("g1", "bu_1", _bu())
    assert {n.learning_object_ref for n in g2.nodes} == set(refs)


def test_minimum_subgraph_skips_mastered_keeps_prereqs():
    g = compile_graph("g1", "bu_1", _bu())
    full = minimum_subgraph(g, ["bu_1::lo::thesis"], [])
    assert "bu_1::lo::thesis" in full and "bu_1::lo::problem" in full
    assert "bu_1::lo::application" not in full  # unneeded for goal
    partial = minimum_subgraph(g, ["bu_1::lo::thesis"],
                               ["bu_1::lo::concept0", "bu_1::lo::problem"])
    assert "bu_1::lo::concept0" not in partial
    assert "bu_1::lo::thesis" in partial


def test_compile_path_budget_and_error_priority():
    g = compile_graph("g1", "bu_1", _bu())
    p = compile_path("p1", "bu_1", "g1", "understand thesis",
                     ["bu_1::lo::thesis"], 16, g, [], [])
    assert len(p.ordered_lo_refs) <= 2  # 16 min / 8 per item
    assert "mastered skipped" in p.rationale
    p2 = compile_path("p1", "bu_1", "g1", "goal",
                      ["bu_1::lo::thesis"], 120, g, [],
                      ["bu_1::lo::mech0"])
    assert p2.ordered_lo_refs.index("bu_1::lo::mech0") < p2.ordered_lo_refs.index(
        "bu_1::lo::thesis")  # repair chain first


def test_tutor_legal_walk_and_illegal_rejected():
    s = TutorSession(session_id="t1", bu_id="bu_1")
    walk = [TutorState.DIAGNOSE, TutorState.TEACH, TutorState.GUIDED_EXAMPLE,
            TutorState.ACTIVE_RESPONSE, TutorState.JUDGE, TutorState.TRANSFER,
            TutorState.MASTERY, TutorState.NEXT, TutorState.SELECT_OBJECTIVE]
    for st in walk:
        s = tutor_transition(s, st)
    assert s.current_state == TutorState.SELECT_OBJECTIVE
    assert len(s.history) == len(walk)
    s2 = TutorSession(session_id="t2")
    with pytest.raises(ValueError, match="Illegal tutor transition"):
        tutor_transition(s2, TutorState.TEACH)  # must DIAGNOSE first
    with pytest.raises(ValueError, match="Illegal tutor transition"):
        tutor_transition(TutorSession(session_id="t3",
                                      current_state=TutorState.JUDGE),
                         TutorState.MASTERY)  # must TRANSFER or REMEDIATE


def test_diagnose_and_repair():
    cands = [{"ref": "a", "centrality": 0.9, "prereq_value": 0.9, "discrimination": 0.5},
             {"ref": "b", "centrality": 0.5, "prereq_value": 0.9, "discrimination": 0.9},
             {"ref": "c", "centrality": 0.9, "prereq_value": 0.9, "discrimination": 0.9}]
    assert diagnose(cands)["ref"] == "c"
    assert diagnose([]) is None
    chain = repair_prerequisites("X", {"X": ["P1"], "P1": ["P2"], "P2": []},
                                 mastered=["P2"])
    assert chain == ["P1"]  # stops at mastered boundary
    assert repair_prerequisites("X", {"X": []}, []) == []


def test_error_policy_and_confident_wrong():
    assert error_policy(ErrorKind.KNOWLEDGE_STRUCTURAL) == ["prerequisite repair"]
    assert "counterexample" in error_policy(ErrorKind.UNDERSTANDING_DEVIATION)
    assert "faded example" in error_policy(ErrorKind.APPLICATION_ERROR)
    mc = confident_wrong("Paris", False, 0.9)
    assert mc.is_candidate is True and "counterexample" in mc.strategy
    mc2 = confident_wrong("Paris", False, 0.3)
    assert mc2.is_candidate is False
    mc3 = confident_wrong("Paris", True, 0.9)
    assert mc3.is_candidate is False


def test_judge_mandatory_feedback_and_dimensions_pure():
    ok, fb, _ = judge_response("Paris", "paris", 0.8)
    assert ok is True and any("transfer" in f for f in fb)
    ok2, fb2, mc = judge_response("Paris", "London", 0.85)
    assert ok2 is False and mc.is_candidate is True
    assert any("feedback" in f for f in fb2)
    d1 = assess_dimensions("lo1", {"recall": 0.8, "transfer": 1.5, "stability": -1})
    d2 = assess_dimensions("lo1", {"recall": 0.8, "transfer": 1.5, "stability": -1})
    assert d1 == d2  # pure derived view, no store
    assert d1.transfer == 1.0 and d1.stability == 0.0  # clamped


def test_benchmark_registry_and_scoring():
    reg = baseline_registry()
    assert len(reg) == 7 and "B6_BU_2_0" in " ".join(reg.keys())
    gold = BookGold(book_id="b1", critical_ku_refs=["k1", "k2"],
                    qualifications=["q1"], revisions=["r1"],
                    major_arguments=["a1"], mechanisms=["m1"],
                    visual_evidence=["v1"], negative_knowledge=["n1"],
                    chapter_roles={"ch1": "DEFINE"},
                    cross_chapter_deps=["ch1->ch2"])
    bu = {"major_ku_refs": ["k1", "k2"], "supporting_ku_refs": [],
          "qualifications": ["q1"], "claim_evolution": [{"claim_ref": "r1"}],
          "rejected_claims": ["n1"], "limitations": [],
          "chapter_roles": {"ch1": "DEFINE"},
          "chapter_dependencies": [{"source_chapter": "ch1", "target_chapter": "ch2"}],
          "visual_refs": ["v1"]}
    scores = {s.metric: s.score for s in score_book(gold, bu, ["a1"], ["m1"])}
    assert scores["KU_RECALL"] == 1.0
    assert scores["QUALIFICATION_RECALL"] == 1.0
    assert scores["CHAPTER_ROLE_ACCURACY"] == 1.0
    bu_missing = dict(bu, qualifications=[])
    scores2 = {s.metric: s.score for s in score_book(gold, bu_missing, ["a1"], ["m1"])}
    assert scores2["QUALIFICATION_RECALL"] == 0.0
    res = {s.metric: s.score for s in score_resolution(
        ResolutionGold(book_id="b1", root=["R"], branch=["B"], leaf_sample=["L1", "L2"]),
        {"ROOT": ["R"], "BRANCH": [], "LEAF": ["L1"]})}
    assert res["ROOT_COMPREHENSION"] == 1.0
    assert res["BRANCH_COMPREHENSION"] == 0.0
    assert res["LEAF_COMPREHENSION"] == 0.5
    traj = {s.metric: s.score for s in score_trajectory(
        EvidenceGold(question="Q", required_pages=[3], required_regions=["fig1"],
                     required_facts=["f1"], required_ku=["k1"],
                     expected_reasoning_relation="supports"),
        {"source_pages": [3], "evidence_regions": ["fig1"],
         "extracted_facts": ["f1"], "ku_refs": ["k1"]})}
    assert all(v == 1.0 for v in traj.values())
