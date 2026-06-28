"""Unit tests for the Layer-4 retrieval enhancers (service/rerank.py).

Inject a fake LLM so no API keys / network are needed. Verifies the previously
inert /search `rerank` and `expand` paths now actually reorder / expand.
"""
from types import SimpleNamespace

from stratum.service.rerank import expand_query, rerank_results


def _result(rid, title, highlight, score=0.0):
    return SimpleNamespace(id=rid, title=title, highlight=highlight, score=score)


def test_rerank_reorders_by_judge_scores():
    # llm_judge_rerank parses lines "index: score"; give doc1 the high score.
    def fake_llm(*, messages, **_):
        return {"content": "0: 1\n1: 9"}

    results = [_result("a", "irrelevant", "noise"),
               _result("b", "relevant", "the answer")]
    out = rerank_results("q", results, top_k=2, llm=fake_llm)
    assert [r.id for r in out] == ["b", "a"]


def test_rerank_llm_error_falls_back_to_original_order():
    results = [_result(str(i), f"t{i}", "h") for i in range(5)]

    def boom(*, messages, **_):
        raise RuntimeError("no key")

    out = rerank_results("q", results, top_k=3, llm=boom)
    assert [r.id for r in out] == ["0", "1", "2"]


def test_rerank_empty():
    assert rerank_results("q", [], llm=lambda **_: {"content": ""}) == []


def test_expand_returns_original_plus_variants():
    def fake_llm(*, messages, **_):
        return {"content": "variant one\nvariant two"}

    out = expand_query("original", num_variants=2, llm=fake_llm)
    assert out[0] == "original"
    assert "variant one" in out and "variant two" in out


def test_expand_dedups_echoed_original():
    def fake_llm(*, messages, **_):
        return {"content": "original\nsomething else"}

    out = expand_query("original", llm=fake_llm)
    # "original" appears once even though the LLM echoed it.
    assert out.count("original") == 1


def test_expand_fallback_on_error():
    def boom(*, messages, **_):
        raise RuntimeError("no key")

    assert expand_query("q", llm=boom) == ["q"]
