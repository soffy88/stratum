"""P7 projection contract tests (§§59-67, §§69-72)."""

from stratum.services.understanding_projection import (
    FIDELITY_KEYS, LADDER, argument_map, book_structure_map, check_fidelity,
    compile_ladder, compression_loss, concept_map, mechanism_map, project,
)
from stratum.knowledge.bu_v2_models import ExpressionProfile


def _bu():
    return {
        "governing_questions": ["Why do nations fail?"],
        "central_theses": ["Institutions decide."],
        "major_arguments": ["arg1", "arg2"],
        "mechanisms": ["mech1"],
        "concepts": ["c1", "c2", "c3"],
        "evidence_refs": ["e1", "e2"],
    }


def test_ladder_is_prefix_narrowing_no_drift():
    ladder = compile_ladder(_bu())
    assert set(ladder.keys()) == set(LADDER)
    assert ladder["FULL"] and ladder["1MIN"]
    refs_full = [i["ref"] for i in ladder["FULL"]]
    for rung in ("30MIN", "15MIN", "5MIN", "1MIN"):
        assert all(i["ref"] in refs_full for i in ladder[rung])
    sizes = [len(ladder[r]) for r in LADDER]
    assert sizes == sorted(sizes, reverse=True)
    assert ladder["1MIN"][0]["kind"] == "thesis"  # core survives deepest cut


def test_compression_loss_reports_omissions():
    ladder = compile_ladder(_bu())
    loss = compression_loss(ladder["FULL"], ladder["1MIN"])
    assert loss.omitted_concepts or loss.omitted_evidence
    assert loss.thesis_preserved is True
    assert loss.mechanism_preserved in (True, False)


def test_fidelity_rejects_invented_claims():
    bu_refs = ["ct:0", "arg:0", "ev:0"]
    good = check_fidelity(["ct:0", "arg:0", "ev:0"], bu_refs,
                          "Institutions decide.", ["Institutions decide."],
                          mechanisms_kept=True)
    assert good["NO_INVENTED_CLAIMS"] is True
    assert good["THESIS_PRESERVED"] is True
    assert set(good.keys()) == set(FIDELITY_KEYS)
    bad = check_fidelity(["ct:0", "invented:9"], bu_refs,
                         "Something else.", ["Institutions decide."],
                         mechanisms_kept=False)
    assert bad["NO_INVENTED_CLAIMS"] is False
    assert bad["THESIS_PRESERVED"] is False
    assert bad["MECHANISM_PRESERVED"] is False


def test_project_same_thesis_across_kinds():
    bu = _bu()
    ladder = compile_ladder(bu)
    prof = ExpressionProfile(purpose="FAST_UNDERSTAND", duration="5MIN")
    a = project("bu_1", "PODCAST", prof, ladder["5MIN"], bu)
    b = project("bu_1", "SLIDES", prof, ladder["5MIN"], bu)
    assert a.thesis == b.thesis == "Institutions decide."
    assert a.bu_id == b.bu_id == "bu_1"
    assert a.compression_loss.thesis_preserved is True


def test_four_maps_answer_different_questions():
    struct = book_structure_map(
        [{"chapter_id": "ch1", "primary_role": "DEFINE", "chapter_thesis": "T"}],
        [{"source_chapter": "ch1", "target_chapter": "ch2"}],
        [{"step": "Problem"}])
    assert struct["map"] == "BookStructureMap"
    assert struct["chapters"][0]["role"] == "DEFINE"
    cmap = concept_map([{"concept": "c1"}], [{"concept_ref": "c1"}])
    assert cmap["map"] == "ConceptMap" and cmap["evolution"]
    amap = argument_map([{"id": "a", "question": "Q", "premises": ["P"],
                          "warrants": ["W"], "evidence_refs": ["e"],
                          "inference_steps": ["I"], "conclusion": ["C"]}])
    assert amap["map"] == "ArgumentMap"
    assert amap["arguments"][0]["conclusion"] == ["C"]
    mmap = mechanism_map([{"id": "m"}], {"entities": ["firm"]})
    assert mmap["map"] == "MechanismMap"
    assert mmap["situation"]["entities"] == ["firm"]
