import json
from pathlib import Path

from scripts.import_legacy_retrieval_gold import convert_legacy_gold
from scripts.eval_retrieval import validate_golden_set


def test_legacy_import_preserves_source_and_marks_candidate():
    converted = convert_legacy_gold(
        [
            {
                "query": "What is marginal cost?",
                "gold_ku_id": "book::ku-1",
                "substrate_id": "book",
            }
        ],
        source_name="legacy/eval.json",
    )

    assert converted == [
        {
            "query_id": "legacy-aii-001",
            "query": "What is marginal cost?",
            "relevant_substrate_ids": ["book"],
            "source_ref": "legacy/eval.json#item-0;gold_ku_id=book::ku-1",
            "review_status": "candidate",
            "rationale": (
                "Imported from the legacy AII evaluation set; verify the substrate "
                "mapping and annotate a human reviewer before release."
            ),
        }
    ]
    assert validate_golden_set(converted) == []
    review_errors = validate_golden_set(converted, require_provenance=True)
    assert any("review_status" in error for error in review_errors)


def test_legacy_import_rejects_duplicate_questions():
    rows = [
        {"query": "same", "substrate_id": "a"},
        {"query": "same", "substrate_id": "b"},
    ]
    try:
        convert_legacy_gold(rows, source_name="legacy/eval.json")
    except ValueError as exc:
        assert "duplicated" in str(exc)
    else:
        raise AssertionError("duplicate legacy questions must be rejected")


def test_existing_legacy_set_produces_release_sized_candidate_batch():
    path = Path(__file__).parents[2] / "aii/scripts/eval/golden.json"
    legacy = json.loads(path.read_text(encoding="utf-8"))
    converted = convert_legacy_gold(legacy, source_name=str(path))

    assert len(converted) >= 50
    assert validate_golden_set(converted, min_queries=50) == []
    assert all(item["review_status"] == "candidate" for item in converted)
