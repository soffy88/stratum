"""Regression tests for deterministic retrieval quality protections."""

from stratum.services.retrieval_engine import (
    _contains_query_phrase,
    _lexical_match_score,
    _rrf_merge_channels,
)


def test_lexical_match_tolerates_cjk_punctuation_between_characters():
    score, exact = _lexical_match_score("鹽谷節山教授", "研究者：鹽谷節山·教授的成果")

    assert score > 0
    assert exact is True


def test_lexical_match_recovers_opaque_pdf_phrase_with_one_inserted_marker():
    query = "\x8a\x94\x8a\x1aS\x95\x16\x962\x1a\x19\x1a\x97 }\x98\x99\x9a("
    fragment = "\x8a\x94\x8a\x1aS\x95\x16\x962\x1a\x19\x1a\x97\x1d}\x98\x99\x9a("

    score, exact = _lexical_match_score(query, fragment)

    assert score >= 85
    assert exact is True


def test_claim_phrase_match_does_not_match_numeric_prefixes():
    assert _contains_query_phrase("What about claim statement 10?", "claim statement 1") is False
    assert _contains_query_phrase("What about claim statement 1?", "claim statement 1") is True


def test_rrf_exact_protection_keeps_canonical_claim_ahead_of_dense_noise():
    channels = {
        "dense_chunk": [
            {"substrate_id": "dense-noise", "score": 0.9},
        ],
        "claim": [{"substrate_id": f"claim-noise-{i}"} for i in range(49)]
        + [{"substrate_id": "claim-target", "score": 100.0, "exact_match": True}],
    }

    protected = _rrf_merge_channels(channels, top_k=2)
    unprotected = _rrf_merge_channels(channels, top_k=2, protect_exact=False)

    assert protected[0]["substrate_id"] == "claim-target"
    assert unprotected[0]["substrate_id"] == "dense-noise"
