"""Adversarial tests for the application retrieval boundary."""

import pytest

from stratum.services.knowledge_view import (
    KnowledgeViewInvariantError,
    KnowledgeViewRequest,
    KnowledgeViewResult,
    validate_knowledge_view_result,
)


def _result() -> KnowledgeViewResult:
    return KnowledgeViewResult(
        id="source-a",
        title="A",
        type="substrate",
        score=1.0,
        snippet="evidence",
        substrate_id="source-a",
        citation={"source_id": "source-a", "quote": "evidence"},
        provenance={"source_id": "source-a", "fragment_id": "fragment-a"},
    )


def test_knowledge_view_result_requires_owned_citable_source():
    assert validate_knowledge_view_result(_result(), "alice", {"source-a": "alice"}) == []
    assert validate_knowledge_view_result(_result(), "alice", {"source-a": "bob"})


def test_knowledge_view_result_rejects_missing_provenance_and_citation():
    result = _result()
    result.citation = None
    result.provenance = None
    errors = validate_knowledge_view_result(result, "alice", {"source-a": "alice"})
    assert "result missing valid citation" in errors
    assert "result missing valid provenance" in errors


def test_unscoped_requests_are_rejected_before_retrieval():
    from stratum.services.knowledge_view import search_knowledge_view

    with pytest.raises(KnowledgeViewInvariantError, match="authenticated user_id"):
        search_knowledge_view(KnowledgeViewRequest(query="secret"))
