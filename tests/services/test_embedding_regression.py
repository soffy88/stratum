"""Embedding Space Regression Test.

Ensures retrieval/query and index/embedding generators use identical
BGE-M3 model/dimension to prevent silent drift.
"""

from __future__ import annotations

import math

import pytest

from stratum.services.layer_generator import _get_embedding as lg_get_embedding
from stratum.services.retrieval_engine import get_embedding as re_get_embedding

pytestmark = pytest.mark.external_provider


def _is_finite_vector(vec: list[float]) -> bool:
    return all(math.isfinite(x) for x in vec)


def test_embedding_regression_bge_m3_identity():
    """Query and index generators must use same BGE-M3 model/dimension."""
    query_text = "What is the capital of France?"
    doc_text = "Paris is the capital and most populous city of France."

    q_vec = re_get_embedding(query_text)
    d_vec = re_get_embedding(doc_text)
    lg_q = lg_get_embedding(query_text)
    lg_d = lg_get_embedding(doc_text)

    assert q_vec is not None, "retrieval_engine.get_embedding failed"
    assert d_vec is not None, "retrieval_engine.get_embedding failed"
    assert lg_q is not None, "layer_generator._get_embedding failed"
    assert lg_d is not None, "layer_generator._get_embedding failed"

    # Dimension must be 1024 (BGE-M3 dense output)
    assert len(q_vec) == 1024, f"Expected dim=1024, got {len(q_vec)}"
    assert len(d_vec) == 1024, f"Expected dim=1024, got {len(d_vec)}"
    assert len(lg_q) == 1024, f"Expected dim=1024, got {len(lg_q)}"
    assert len(lg_d) == 1024, f"Expected dim=1024, got {len(lg_d)}"

    # Vectors must be finite (no NaN/Inf)
    assert _is_finite_vector(q_vec), "retrieval query vector non-finite"
    assert _is_finite_vector(d_vec), "retrieval doc vector non-finite"
    assert _is_finite_vector(lg_q), "layer query vector non-finite"
    assert _is_finite_vector(lg_d), "layer doc vector non-finite"

    # L2 norm should be ~[1.0] (BGE-M3 normalizes)
    q_norm = math.sqrt(sum(x * x for x in q_vec))
    d_norm = math.sqrt(sum(x * x for x in d_vec))
    assert 0.9 <= q_norm <= 1.1, f"Query norm {q_norm:.3f} not ~1.0"
    assert 0.9 <= d_norm <= 1.1, f"Doc norm {d_norm:.3f} not ~1.0"

    # Critical: retrieval and layer generators must produce IDENTICAL vectors
    # for the same input (proves same model/code path)
    assert q_vec == lg_q, "retrieval/query vs layer/query vectors differ"
    assert d_vec == lg_d, "retrieval/doc vs layer/doc vectors differ"


def test_embedding_different_inputs_produce_different_vectors():
    """Sanity: different inputs should (very likely) yield different vectors."""
    v1 = re_get_embedding("alpha")
    v2 = re_get_embedding("beta")
    assert v1 != v2, "Identical vectors for different inputs (collision?)"


if __name__ == "__main__":
    test_embedding_regression_bge_m3_identity()
    test_embedding_different_inputs_produce_different_vectors()
    print("Embedding regression test: PASS")
