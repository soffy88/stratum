"""P2 KU segmentation behavior tests (§§7-9, §12)."""

import pytest

from stratum.services.ku_segmentation import (
    DeterministicAnalyzer,
    assert_quote_author_separation,
    detect_discourse_role,
    detect_epistemic_role,
    extract_scope_conditions,
    qualified_ku_gate,
    recover_context,
    split_propositions,
    split_sentences,
)


def test_sentence_split_abbreviation_guard():
    sents = split_sentences("See Fig. 3. It shows growth. Dr. Smith agrees.")
    assert len(sents) == 3
    assert sents[0] == "See Fig. 3."


def test_proposition_forks_on_contrast():
    props = split_propositions("Growth was strong but inflation remained high and persistent.")
    assert len(props) == 2


def test_single_sentence_single_proposition():
    assert split_propositions("Photosynthesis converts light into energy.") == [
        "Photosynthesis converts light into energy."]


def test_discourse_roles():
    assert detect_discourse_role("Inflation is defined as a sustained rise.") == "DEFINITION"
    assert detect_discourse_role("The study shows growth accelerated.") == "EVIDENCE"
    assert detect_discourse_role("What causes inflation?") == "QUESTION"
    assert detect_discourse_role("For example, consider 1970s oil.") == "EXAMPLE"
    assert detect_discourse_role("Therefore policy must adapt.") == "CONCLUSION"
    assert detect_discourse_role("Growth is steady.") == "CLAIM"


def test_epistemic_roles_and_speaker():
    role, speaker = detect_epistemic_role("According to Friedman, inflation is monetary.")
    assert role == "QUOTED_POSITION"
    assert speaker == "Friedman"
    role2, _ = detect_epistemic_role("We reject the Phillips tradeoff.")
    assert role2 == "AUTHOR_REJECTED"
    role3, _ = detect_epistemic_role("Growth is steady.")
    assert role3 == "AUTHOR_ASSERTED"


def test_quote_without_speaker_is_stance_error():
    with pytest.raises(ValueError, match="STANCE_ERROR"):
        assert_quote_author_separation("QUOTED_POSITION", "")


def test_scope_conditions_quantifier():
    sc = extract_scope_conditions("If taxes rise, demand usually falls, except for luxuries.")
    assert sc["conditions"] and sc["qualifiers"] == ["usually"]
    assert sc["exceptions"]
    sc2 = extract_scope_conditions("All markets clear always.")
    assert sc2["quantifier"] == "universal"
    sc3 = extract_scope_conditions("Some firms exit.")
    assert sc3["quantifier"] == "existential"


def test_context_recovery_by_overlap_not_all():
    cand = {"proposition": "Inflation erodes purchasing power rapidly."}
    priors = [
        {"ku_id": "k1", "proposition": "Inflation expectations drive wages."},
        {"ku_id": "k2", "proposition": "Unrelated baseball scores."},
        {"ku_id": "k3", "proposition": "Purchasing power falls with inflation."},
    ]
    refs = recover_context(cand, priors)
    assert "k2" not in refs
    assert set(refs) <= {"k1", "k3"}


def test_analyzer_end_to_end_candidate():
    an = DeterministicAnalyzer()
    ctx = {"source_id": "s1", "chapter_id": "ch1",
           "fragment_refs": ["f1"], "page_range": [3, 4],
           "default_scope": {"domain": "macro"}}
    cands = an.analyze("Inflation is defined as a sustained rise. It erodes savings.", ctx)
    assert len(cands) == 2
    assert cands[0]["discourse_role"] == "DEFINITION"
    assert cands[0]["grounding_status"] == "grounded"


def test_qualified_gate_pass_and_failures():
    good = {"proposition": "X causes Y.", "fragment_refs": ["f1"],
            "context_status": "recovered", "epistemic_role": "AUTHOR_ASSERTED",
            "stance": "author", "scope": {"domain": "d"}, "conditions": [],
            "source_id": "s", "chapter_id": "c", "extraction_run_id": "r",
            "concepts": ["c1"]}
    ok, failures = qualified_ku_gate(good, known_concepts=["c1"])
    assert ok and failures == []
    bad = {"proposition": "", "context_status": "unresolved",
           "epistemic_role": "QUOTED_POSITION", "speaker": "",
           "stance": "", "scope": {}, "source_id": "s",
           "concepts": ["invented"]}
    ok2, failures2 = qualified_ku_gate(bad, known_concepts=["c1"])
    assert not ok2
    assert "SOURCE_GROUNDED" in failures2
    assert "SPEAKER_RESOLVED" in failures2
    assert any(f.startswith("NO_HALLUCINATED_CONTENT") for f in failures2)
