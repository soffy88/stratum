"""Reasoning models return the answer in ``reasoning_content``.

deepseek-v4.1-flash, nemotron-3-super and the qwen3-thinking family put their
chain of thought in ``reasoning_content`` and, under json_mode, land the payload
there verbatim with ``content`` set to null. The OpenAI-compatible extractor has
to fall back to that field, or every chapter fails with "unexpected envelope"
even though the model answered correctly.
"""

from stratum.services.bu_v2_provider import OpenAICompatibleProvider


class _Stub(OpenAICompatibleProvider):
    """Returns a fixed envelope; never touches the network."""

    name = "stub"

    def __init__(self, envelope):
        super().__init__(model="m", base_url="http://x/v1", api_key="k")
        self.envelope = envelope

    def _url(self):
        return self.base_url + "/chat/completions"

    def _headers(self, json_mode):
        return {}

    def _post(self, url, payload, headers):
        return self.envelope


def _env(content, reasoning=None):
    msg = {"role": "assistant", "content": content}
    if reasoning is not None:
        msg["reasoning_content"] = reasoning
    return {"choices": [{"index": 0, "message": msg}], "usage": {}}


def test_content_present_is_used():
    p = _Stub(_env('{"a": 1}', reasoning="ignored chain of thought"))
    assert p._extract(p.envelope) == '{"a": 1}'


def test_null_content_falls_back_to_reasoning():
    p = _Stub(_env(None, reasoning='{"a": 1}'))
    assert p._extract(p.envelope) == '{"a": 1}'


def test_empty_content_falls_back_to_reasoning():
    p = _Stub(_env("   ", reasoning='{"a": 1}'))
    assert p._extract(p.envelope) == '{"a": 1}'


def test_both_absent_returns_none_not_crash():
    # A genuinely empty answer must surface as None so the caller raises
    # ProviderError, rather than exploding on a missing key.
    p = _Stub(_env(None))
    assert p._extract(p.envelope) is None


def test_complete_parses_reasoning_only_json():
    p = _Stub(_env(None, reasoning='{"concepts": [{"name": "Limit"}]}'))
    r = p.complete("prompt", json_mode=True, max_tokens=100)
    assert r.json() == {"concepts": [{"name": "Limit"}]}
