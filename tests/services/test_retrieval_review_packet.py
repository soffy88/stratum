from scripts.build_retrieval_review_packet import build_review_packet


def test_retrieval_review_packet_preserves_candidate_mapping_and_review_status():
    packet = build_review_packet(
        [
            {
                "query_id": "q-1",
                "query": "What is marginal cost?",
                "relevant_substrate_ids": ["substrate-1"],
                "source_ref": "legacy:1",
                "review_status": "candidate",
                "rationale": "Verify the mapping before release.",
            }
        ]
    )

    assert packet["packet_type"] == "retrieval_human_review"
    assert packet["review_required"] is True
    assert packet["annotations_unchanged"] is True
    assert packet["cases"] == [
        {
            "query_id": "q-1",
            "query": "What is marginal cost?",
            "source_ref": "legacy:1",
            "reviewer": None,
            "review_status": "candidate",
            "rationale": "Verify the mapping before release.",
            "proposed_relevant_substrate_ids": ["substrate-1"],
            "mapping_review_required": True,
        }
    ]


def test_retrieval_review_packet_does_not_require_a_reviewer_to_build():
    packet = build_review_packet(
        [
            {
                "query": "q",
                "relevant_substrate_ids": ["s"],
                "review_status": "candidate",
            }
        ]
    )
    assert packet["cases"][0]["reviewer"] is None
    assert packet["cases"][0]["mapping_review_required"] is True
