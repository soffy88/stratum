import pytest

from scripts.apply_eval_reviews import apply_reviews


def test_apply_parser_reviews_requires_complete_explicit_annotations():
    manifest = [
        {
            "id": "p-1",
            "path": "p.pdf",
            "source_ref": "fixture:p-1",
            "layout": "unknown",
            "language": "unknown",
            "structure_elements": [],
            "required_markers": [],
            "review_status": "candidate",
        }
    ]
    result = apply_reviews(
        manifest,
        [
            {
                "id": "p-1",
                "reviewer": "alice",
                "review_status": "reviewed",
                "layout": "single_column",
                "language": "en",
                "structure_elements": ["heading"],
                "required_markers": ["Results"],
            }
        ],
        kind="parser",
    )
    assert result[0]["layout"] == "single_column"
    assert result[0]["reviewer"] == "alice"
    assert result[0]["review_status"] == "reviewed"


def test_apply_retrieval_reviews_requires_mapping_rationale_and_reviewer():
    result = apply_reviews(
        [
            {
                "query_id": "q-1",
                "query": "What is cost?",
                "relevant_substrate_ids": ["candidate"],
                "source_ref": "fixture:q-1",
                "review_status": "candidate",
            }
        ],
        [
            {
                "query_id": "q-1",
                "reviewer": "bob",
                "review_status": "reviewed",
                "relevant_substrate_ids": ["verified"],
                "rationale": "The source directly answers the query.",
            }
        ],
        kind="retrieval",
    )
    assert result[0]["relevant_substrate_ids"] == ["verified"]
    assert result[0]["rationale"].startswith("The source")


def test_apply_reviews_rejects_missing_unknown_and_invalid_decisions():
    manifest = [
        {
            "id": "p-1",
            "path": "p.pdf",
            "layout": "unknown",
            "language": "unknown",
            "structure_elements": [],
            "required_markers": [],
        }
    ]
    with pytest.raises(ValueError, match="missing case"):
        apply_reviews(manifest, [], kind="parser")
    with pytest.raises(ValueError, match="unknown case"):
        apply_reviews(manifest, [{"id": "other"}], kind="parser", allow_partial=True)
    with pytest.raises(ValueError, match="review_status"):
        apply_reviews(
            manifest,
            [
                {
                    "id": "p-1",
                    "reviewer": "alice",
                    "review_status": "candidate",
                    "layout": "single",
                    "language": "en",
                    "structure_elements": [],
                    "required_markers": [],
                }
            ],
            kind="parser",
        )


def test_apply_reviews_rejects_malformed_source_instead_of_dropping_it():
    with pytest.raises(ValueError, match="source manifest is invalid"):
        apply_reviews(
            [{"id": "p-1"}, "not-an-object"],
            [],
            kind="parser",
            allow_partial=True,
        )
