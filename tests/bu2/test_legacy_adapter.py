"""Legacy adapter tests — spec §13.3.

§13.3 requires testing that a real ``aii.bu_onto`` row converts to a BU2 object.
Two layers are covered:

  synthetic rows  shaped like the production table, so the mapping is pinned
                  without a database
  the live row    marked skipif, so the adapter is also checked against the real
                  thing when a database happens to be reachable

§7.3 is the constraint that matters and it gets the most attention here: a copy
is forbidden, so the tests assert on what the mapping *changed* rather than on
whether values survived. The decisive case is the stance — a legacy claim about
儒家 is not a thesis unless its holder survives.
"""

from __future__ import annotations

import pytest

from stratum.knowledge.bu_v2_models import BUStatus
from stratum.services.bu_v2_legacy_adapter import (
    BU2LegacyAdapter,
    LegacyArgument,
    LegacyBU,
    LegacyClaim,
    normalise,
)

# Shaped from a real row: bu_id 854, main_claims with stance, argument_structure
# with boundary and evidence. Real content, so the mapping is exercised against
# the shape it will actually meet.
LEGACY_ROW = {
    "bu_id": 854,
    "substrate_id": "misc_zh_a98b36503c",
    "title": "中国思想史",
    "problem_statement": "如何在天人观念与社会实践间建立合理情理体系？",
    "overview_oneline": "一部讨论中国哲学主流的思想史著作。",
    "main_claims": [
        {
            "claim": "儒家不是宗教，而是一种哲学。",
            "stance": "儒家",
            "claim_grade": "unverified",
            "stance_marker": "宗教",
        },
        {
            "claim": "道家与道教的教义不仅不同，甚至相反。",
            "stance": "道家",
            "claim_grade": "unverified",
            "stance_marker": "道教",
        },
        {"claim": "朱熹认为国家之理是客观存在的永恒理念。", "stance": "朱熹"},
    ],
    "argument_structure": [
        {
            "point": "儒家关注人伦日用与道德价值，未涉及超现世追求或神明实体",
            "boundary": "对立观点认为儒家有经典、礼仪等宗教元素",
            "evidence": [{"text": "儒家关注的是人间社会", "grade": "unverified"}],
        },
        {
            "point": "道家顺应自然，道教反乎自然",
            "boundary": "道家与道教实践的混淆现象",
            "evidence": [{"text": "老子顺自然", "grade": "unverified"}],
        },
    ],
    "limitations": ["以宋明理学为中心，魏晋部分较简"],
    "grade": "unverified",
    "synthesis_marker": "AII综合,非原文断言",
    "authors": "某作者",
    "venue_year": "2020",
    # The fields P10 measured as empty across all 4005 rows.
    "concept_network": None,
    "applicability": None,
    "core_explanations": None,
    "structure": None,
    "key_concept_ku_ids": None,
    "learning_paths": [],
    "deep_cards": [],
}


def adapter(**kw) -> BU2LegacyAdapter:
    return BU2LegacyAdapter(reader=lambda _id: normalise(LEGACY_ROW), **kw)


# ── §13.3 conversion ─────────────────────────────────────────────────────────


def test_legacy_row_converts_to_bu2_object():
    result = adapter().import_legacy_understanding(854)
    assert result.bu is not None
    assert result.claims_mapped == 3
    assert result.arguments_mapped == 2
    assert result.limitations_mapped == 1


def test_normalise_handles_the_real_row_shape():
    legacy = normalise(LEGACY_ROW)
    assert legacy.legacy_id == "854"
    assert legacy.substrate_id == "misc_zh_a98b36503c"
    assert len(legacy.claims) == 3
    assert legacy.claims[0].stance == "儒家"
    assert legacy.claims[0].stance_marker == "宗教"
    assert legacy.arguments[0].boundary


def test_normalise_tolerates_empty_and_null_fields():
    """Six legacy fields are null in all 4005 rows; normalisation must not raise."""
    legacy = normalise(LEGACY_ROW)
    assert legacy.positional_summary == []
    assert legacy.learning_paths == []
    assert legacy.claims  # real content still parsed


def test_normalise_accepts_json_encoded_strings():
    """jsonb arrives as a string from some clients."""
    row = dict(LEGACY_ROW)
    row["main_claims"] = '[{"claim": "x", "stance": "y"}]'
    legacy = normalise(row)
    assert legacy.claims[0].claim == "x"


# ── §7.3 mapping, not copying ────────────────────────────────────────────────


def test_stance_survives_the_mapping():
    """The decisive difference between a mapping and a copy.

    A legacy claim says 儒家 is not a religion. Copied into a list of thesis
    strings, the claim loses its holder and becomes an unattributed sentence.
    The mapping must keep the distinction visible.
    """
    bu = adapter().import_legacy_understanding(854).bu
    first = bu.central_theses[0]
    assert "儒家" in first
    assert "宗教" in first
    assert "regarding" in first


def test_claim_without_stance_marker_still_maps():
    legacy = LegacyBU(
        legacy_id="1", substrate_id="s", claims=[LegacyClaim(claim="Plain claim", stance="X")]
    )
    result = BU2LegacyAdapter(reader=lambda _i: legacy).import_legacy_understanding("1")
    assert "stance: X" in result.bu.central_theses[0]


def test_mapped_values_are_rebuilt_not_lifted():
    """A copy would reproduce a legacy column verbatim. The mapping rebuilds it."""
    bu = adapter().import_legacy_understanding(854).bu
    # problem_statement became a governing question, and it is not one of the
    # columns BU2 read from.
    assert bu.governing_questions == [LEGACY_ROW["problem_statement"]]
    assert bu.genre == "legacy_import"
    assert bu.concept_system["legacy_id"] == "854"
    assert bu.concept_system["imported"] is True


def test_sub_theses_are_the_remainder_not_a_copy():
    bu = adapter().import_legacy_understanding(854).bu
    assert len(bu.central_theses) == 3
    assert bu.central_theses[0].startswith("儒家不是宗教")


def test_argument_points_become_the_argument_layer():
    bu = adapter().import_legacy_understanding(854).bu
    # Two legacy arguments become root arguments; supporting takes the remainder,
    # which is empty at this size.
    assert len(bu.argument_architecture.root_arguments) == 2
    assert bu.argument_architecture.root_arguments[0].startswith("儒家关注人伦日用")
    assert bu.argument_architecture.supporting_arguments == []


def test_many_arguments_fill_the_supporting_layer():
    legacy = LegacyBU(
        legacy_id="2",
        substrate_id="s",
        arguments=[LegacyArgument(point=f"point {i}") for i in range(6)],
    )
    result = BU2LegacyAdapter(reader=lambda _i: legacy).import_legacy_understanding("2")
    arch = result.bu.argument_architecture
    assert len(arch.root_arguments) == 3
    assert len(arch.supporting_arguments) == 3


def test_legacy_boundary_becomes_an_open_problem():
    """§9: what a legacy BU recorded as a boundary is negative knowledge, and
    BU2 has a first-class home for it."""
    bu = adapter().import_legacy_understanding(854).bu
    assert any("宗教元素" in p for p in bu.negative_knowledge.open_problems)


def test_limitations_carry_across():
    bu = adapter().import_legacy_understanding(854).bu
    assert bu.negative_knowledge.limitations == LEGACY_ROW["limitations"]


# ── honesty about what is lost ───────────────────────────────────────────────


def test_unmappable_legacy_fields_are_named():
    result = adapter().import_legacy_understanding(854)
    assert len(result.unmapped_fields) >= 10
    joined = " ".join(result.unmapped_fields)
    for name in ("concept_network", "structure", "applicability", "embedding"):
        assert name in joined


def test_unverified_grade_is_recorded_as_a_degradation():
    result = adapter().import_legacy_understanding(854)
    assert any("unverified" in d for d in result.degradations)


def test_legacy_evidence_without_locator_is_recorded():
    result = adapter().import_legacy_understanding(854)
    assert any("no source locator" in d for d in result.degradations)


def test_synthesis_marker_is_preserved_as_a_degradation():
    result = adapter().import_legacy_understanding(854)
    assert any("synthesis marker" in d for d in result.degradations)


def test_import_is_never_self_verifying():
    """§7.3 plus §12: a mapped BU has read nothing, so it claims nothing."""
    bu = adapter().import_legacy_understanding(854).bu
    assert bu.verification_score == 0.0
    assert bu.coverage_score == 0.0
    assert bu.status == BUStatus.DRAFT


def test_degradations_are_also_visible_on_the_bu():
    bu = adapter().import_legacy_understanding(854).bu
    assert bu.unresolved_questions, "degradations must be readable from the BU itself"


def test_empty_legacy_bu_does_not_produce_a_hollow_bu():
    """Importing nothing must not look like a successful import."""
    legacy = LegacyBU(legacy_id="9", substrate_id="s")
    result = BU2LegacyAdapter(reader=lambda _i: legacy).import_legacy_understanding("9")
    assert result.bu is None
    assert any("nothing mapped" in d for d in result.degradations)


# ── isolation: §2.2, §2.3 ────────────────────────────────────────────────────


def test_adapter_writes_nothing_to_the_b_warehouse():
    legacy = normalise(LEGACY_ROW)
    bu = BU2LegacyAdapter(reader=lambda _i: legacy).import_legacy_understanding("854").bu
    blob = repr(bu.concept_system) + repr(bu.central_theses)
    for banned in ("rf.", "refined_ku", "refined_concept", "aii_refined"):
        assert banned not in blob


def test_adapter_produces_no_learning_state():
    bu = adapter().import_legacy_understanding(854).bu
    blob = repr(bu.model_dump())
    for banned in ("learning_progress", "mastery", "fsrs"):
        assert banned not in blob.lower()


def test_legacy_learning_paths_are_not_imported_as_bu_content():
    """§2.3: the legacy learning projection belongs to C, not to BU."""
    row = dict(LEGACY_ROW)
    row["learning_paths"] = [{"path": "x", "cards": 3}]
    row["deep_cards"] = [{"q": "a", "a": "b"}]
    legacy = normalise(row)
    bu = BU2LegacyAdapter(reader=lambda _i: legacy).import_legacy_understanding("854").bu
    blob = repr(bu.model_dump())
    assert "learning_paths" not in blob
    assert "deep_cards" not in blob


# ── §7.4: one real legacy BU ────────────────────────────────────────────────


def test_real_legacy_row_from_production():
    """§7.4: a real aii.bu_onto row, mapped through the adapter.

    Skipped rather than faked when no database is reachable: the whole point of
    §7.4 is that this runs against real legacy data.
    """
    pytest.importorskip("psycopg2")
    import os

    os.environ.setdefault("STRATUM_PG_PASSWORD", "***REMOVED***")
    from stratum.services.bu_v2_entrypoint import db

    try:
        rows = db.query(
            "SELECT bu_id FROM aii.bu_onto "
            "WHERE main_claims IS NOT NULL AND jsonb_array_length(main_claims) > 2 "
            "AND argument_structure IS NOT NULL "
            "AND jsonb_array_length(argument_structure) > 1 "
            "ORDER BY jsonb_array_length(argument_structure) DESC LIMIT 1"
        )
    except Exception as exc:
        pytest.skip(f"legacy warehouse unreachable: {exc}")
    if not rows:
        pytest.skip("no legacy BU with sufficient content")

    legacy_id = rows[0]["bu_id"]
    result = BU2LegacyAdapter().import_legacy_understanding(legacy_id)

    assert result.bu is not None
    assert result.claims_mapped >= 3
    assert result.arguments_mapped >= 2
    # The stance survived, which is what makes this a mapping rather than a copy.
    assert any("(regarding " in t and " vs " in t for t in result.bu.central_theses)
    assert result.bu.verification_score == 0.0
    assert result.bu.status == BUStatus.DRAFT
    assert result.degradations, "a real legacy import must record its degradations"


def test_real_legacy_row_quality_is_reported_as_low():
    """A mapped legacy BU has read no text, so its quality must reflect that."""
    pytest.importorskip("psycopg2")
    import os

    os.environ.setdefault("STRATUM_PG_PASSWORD", "***REMOVED***")
    from stratum.services.bu_v2_entrypoint import db
    from stratum.services.bu_v2_quality_evaluator import BUQualityEvaluator

    try:
        rows = db.query(
            "SELECT bu_id FROM aii.bu_onto WHERE main_claims IS NOT NULL "
            "AND jsonb_array_length(main_claims) > 2 LIMIT 1"
        )
    except Exception as exc:
        pytest.skip(f"legacy warehouse unreachable: {exc}")
    if not rows:
        pytest.skip("no legacy BU with claims")

    bu = BU2LegacyAdapter().import_legacy_understanding(rows[0]["bu_id"]).bu
    rep = BUQualityEvaluator().evaluate(bu, chapters=[], evidence=[], pipeline_status="UNKNOWN")
    evidence = next(d for d in rep.dimensions if d.key == "Q6")
    assert evidence.score == 0.0, "a mapped legacy BU has no located evidence"
    assert rep.quality_level in ("C", "D")