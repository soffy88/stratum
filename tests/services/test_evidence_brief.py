from __future__ import annotations

import pytest

from stratum.services.evidence_brief import (
    EvidenceBriefInvariantError,
    EvidenceBriefRequest,
    build_evidence_brief,
    render_evidence_brief_markdown,
)


def _valid_response(req):
    assert req.query == "black holes"
    assert req.user_id == "user-1"
    return {
        "query": req.query,
        "trajectory_id": "traj-1",
        "results": [
            {
                "title": "Source A",
                "score": 0.91,
                "snippet": "fallback snippet",
                "substrate_id": "source-a",
                "fragment_id": "frag-1",
                "layer": "L2",
                "paragraph_index": 3,
                "char_start": 10,
                "char_end": 30,
                "deep_link": "stratum://substrate/source-a#p3",
                "citation": {
                    "source_id": "source-a",
                    "fragment_id": "frag-1",
                    "quote": "direct evidence",
                },
                "provenance": {
                    "source_id": "source-a",
                    "fragment_id": "frag-1",
                    "layer": "L2",
                },
            }
        ],
    }


def test_build_evidence_brief_uses_knowledge_view_contract() -> None:
    brief = build_evidence_brief(
        EvidenceBriefRequest(query="black holes", user_id="user-1", top_k=5),
        search_fn=_valid_response,
    )
    assert brief["authority"] == "KnowledgeView"
    assert brief["result_count"] == 1
    assert brief["trajectory_id"] == "traj-1"
    assert brief["items"][0]["quote"] == "direct evidence"
    assert brief["items"][0]["source_id"] == "source-a"
    assert brief["items"][0]["fragment_id"] == "frag-1"


def test_evidence_brief_fails_closed_without_citation() -> None:
    def search(_):
        return {
            "query": "q",
            "results": [
                {
                    "substrate_id": "source-a",
                    "provenance": {"source_id": "source-a"},
                }
            ],
        }

    with pytest.raises(EvidenceBriefInvariantError, match="valid citation"):
        build_evidence_brief(EvidenceBriefRequest(query="q", user_id="user-1"), search_fn=search)


def test_evidence_brief_fails_closed_without_provenance() -> None:
    def search(_):
        return {
            "query": "q",
            "results": [
                {
                    "substrate_id": "source-a",
                    "citation": {"source_id": "source-a"},
                }
            ],
        }

    with pytest.raises(EvidenceBriefInvariantError, match="valid provenance"):
        build_evidence_brief(EvidenceBriefRequest(query="q", user_id="user-1"), search_fn=search)


@pytest.mark.parametrize(
    "case",
    [
        EvidenceBriefRequest(query="", user_id="user-1"),
        EvidenceBriefRequest(query="q", user_id="default"),
        EvidenceBriefRequest(query="q", user_id=""),
        EvidenceBriefRequest(query="q", user_id="user-1", top_k=0),
        EvidenceBriefRequest(query="q", user_id="user-1", top_k=101),
    ],
)
def test_evidence_brief_rejects_invalid_requests(case) -> None:
    with pytest.raises(EvidenceBriefInvariantError):
        build_evidence_brief(case, search_fn=lambda _: {"results": []})


def test_render_markdown_preserves_evidence_refs() -> None:
    brief = build_evidence_brief(
        EvidenceBriefRequest(query="black holes", user_id="user-1"),
        search_fn=_valid_response,
    )
    text = render_evidence_brief_markdown(brief)
    assert "# Evidence Brief: black holes" in text
    assert "> direct evidence" in text
    assert "source_id: `source-a`" in text
    assert "fragment_id: `frag-1`" in text
    assert "stratum://substrate/source-a#p3" in text
