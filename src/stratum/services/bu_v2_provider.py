"""ModelProvider boundary for the BU2 understanding engine.

Spec §7.2 forbids the pipeline calling a model SDK directly:

    openai()  deepseek()  ollama()   -- forbidden inside the pipeline

Everything goes through ``ModelProvider`` so the engine is testable without a
network and so swapping a backend is a constructor argument rather than a code
edit. Four families are supported: any OpenAI-compatible endpoint (OpenAI,
DeepSeek, NVIDIA NIM, vLLM, LM Studio), Anthropic, Google, and a local Ollama
daemon.

The engine depends on the ``ModelProvider`` protocol, never on a concrete class.
``resolve_provider`` reads no environment and imports no SDK at module scope, so
this file can be imported in an environment that has none of them installed.
"""

from __future__ import annotations

import json
import os
import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol


class ProviderError(RuntimeError):
    """A provider was reachable but did not produce usable output."""


class ProviderUnavailable(ProviderError):
    """No provider is configured, or the configured one cannot be reached."""


# Status codes a rotating gateway (freellmapi, OpenRouter) returns when one
# upstream is throttled or down. A retry lands on a different upstream, so these
# are retried with backoff instead of failing the chapter.
_TRANSIENT_HTTP = {408, 409, 425, 429, 500, 502, 503, 504, 520, 522, 524}


def _retry_budget() -> tuple[int, float]:
    try:
        attempts = max(1, int(os.environ.get("BU2_PROVIDER_ATTEMPTS", "5")))
    except ValueError:
        attempts = 5
    try:
        base = max(0.0, float(os.environ.get("BU2_PROVIDER_BACKOFF_S", "2")))
    except ValueError:
        base = 2.0
    return attempts, base


def _is_transient(exc: Exception) -> bool:
    if isinstance(exc, ProviderUnavailable):
        # Entitlement failures are permanent; network blips are not.
        return "no inference entitlement" not in str(exc) and "no API key" not in str(exc)
    code = getattr(exc, "http_status", None)
    if code is not None:
        return code in _TRANSIENT_HTTP
    return isinstance(exc, ProviderError) and "unexpected envelope" in str(exc)


def call_with_retry(
    fn,
    *,
    attempts: int | None = None,
    base: float | None = None,
    retry_if=_is_transient,
    sleep=time.sleep,
):
    """Run ``fn`` and retry transient provider failures with jittered backoff."""
    default_attempts, default_base = _retry_budget()
    attempts = attempts or default_attempts
    base = default_base if base is None else base
    last: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except ProviderError as exc:
            last = exc
            if i == attempts - 1 or not retry_if(exc):
                raise
            delay = getattr(exc, "retry_after", None)
            if delay is None:
                delay = base * (2**i)
            sleep(min(60.0, delay) * (0.75 + random.random() * 0.5))
    raise last  # pragma: no cover


@dataclass(frozen=True)
class ModelResponse:
    """One completion. ``raw`` keeps the provider envelope for auditing."""

    text: str
    model: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw: dict[str, Any] = field(default_factory=dict)

    def json(self) -> Any:
        """Parse ``text`` as JSON, tolerating a fenced block.

        Small models wrap JSON in ```json fences or add a sentence of prose.
        Both are stripped rather than failing the run, because a parse error on
        a 0.5B model is a formatting failure, not an understanding failure.
        """
        s = (self.text or "").strip()
        if s.startswith("```"):
            s = s.split("```", 2)[1] if s.count("```") >= 2 else s
            if s.lower().startswith("json"):
                s = s[4:]
        s = s.strip()
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pass
        for opener, closer in (("{", "}"), ("[", "]")):
            i, j = s.find(opener), s.rfind(closer)
            if i != -1 and j > i:
                try:
                    return json.loads(s[i : j + 1])
                except json.JSONDecodeError:
                    continue
        raise ProviderError(f"model output was not JSON: {s[:200]!r}")


class ModelProvider(Protocol):
    """The only interface the understanding engine may call."""

    name: str

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        json_mode: bool = False,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> ModelResponse: ...


class _HTTPProvider:
    """Shared HTTP plumbing. Subclasses supply URL, headers and payload shape."""

    name = "http"
    default_model = ""
    timeout = 300

    def __init__(self, *, model: str | None = None, base_url: str = "", api_key: str = ""):
        self.model = model or self.default_model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _post(self, url: str, payload: dict, headers: dict) -> dict:
        body = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode()[:300]
            # A 404 naming the account means the key lacks inference
            # entitlement for this deployment. That is an entitlement problem,
            # not a bad model, and the distinction decides the remedy.
            if exc.code == 404 and "for account" in detail:
                raise ProviderUnavailable(
                    f"{self.name}: key has no inference entitlement ({detail})"
                ) from exc
            err = ProviderError(f"{self.name}: HTTP {exc.code}: {detail}")
            err.http_status = exc.code
            ra = exc.headers.get("Retry-After") if exc.headers else None
            try:
                err.retry_after = float(ra) if ra else None
            except ValueError:
                err.retry_after = None
            raise err from exc
        except urllib.error.URLError as exc:
            raise ProviderUnavailable(f"{self.name}: {exc.reason}") from exc
        except TimeoutError as exc:
            raise ProviderUnavailable(f"{self.name}: timed out after {self.timeout}s") from exc

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        json_mode: bool = False,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> ModelResponse:
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}
        ]
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        def _once() -> tuple[dict, str]:
            data = self._post(self._url(), payload, self._headers(json_mode))
            try:
                text = self._extract(data)
            except (KeyError, IndexError, TypeError) as exc:
                raise ProviderError(f"{self.name}: unexpected envelope: {str(data)[:200]}") from exc
            return data, text

        data, text = call_with_retry(_once)
        usage = data.get("usage") or {}
        return ModelResponse(
            text=text,
            model=self.model,
            provider=self.name,
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            raw=data,
        )

    def _url(self) -> str:
        raise NotImplementedError

    def _headers(self, json_mode: bool) -> dict:
        raise NotImplementedError

    def _extract(self, data: dict) -> str:
        raise NotImplementedError


class OpenAICompatibleProvider(_HTTPProvider):
    """OpenAI and every endpoint that speaks its dialect.

    This covers OpenAI itself, DeepSeek, NVIDIA NIM, vLLM and LM Studio, which
    is why it is the default rather than a bespoke OpenAI class.
    """

    name = "openai-compatible"
    default_model = "gpt-4o-mini"

    def __init__(
        self,
        *,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        env_key: str = "OPENAI_API_KEY",
        env_base: str = "OPENAI_BASE_URL",
    ):
        super().__init__(
            model=model,
            base_url=base_url or os.environ.get(env_base, "https://api.openai.com/v1"),
            api_key=api_key if api_key is not None else os.environ.get(env_key, ""),
        )
        if not self.api_key:
            raise ProviderUnavailable(f"{self.name}: no API key ({env_key} unset)")

    def _url(self) -> str:
        return f"{self.base_url}/chat/completions"

    def _headers(self, json_mode: bool) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def _extract(self, data: dict) -> str:
        return data["choices"][0]["message"]["content"]


class DeepSeekProvider(OpenAICompatibleProvider):
    name = "deepseek"
    default_model = "deepseek-chat"

    def __init__(self, **kw):
        kw.setdefault("base_url", "https://api.deepseek.com/v1")
        kw.setdefault("env_key", "DEEPSEEK_API_KEY")
        super().__init__(**kw)


class NIMProvider(OpenAICompatibleProvider):
    timeout = 600
    name = "nvidia-nim"
    default_model = "meta/llama-3.2-90b-vision-instruct"

    def __init__(self, **kw):
        kw.setdefault("base_url", "https://integrate.api.nvidia.com/v1")
        kw.setdefault("env_key", "NVIDIA_NIM_API_KEY")
        super().__init__(**kw)


class AnthropicProvider(_HTTPProvider):
    name = "anthropic"
    default_model = "claude-sonnet-4-20250514"
    api_version = "2023-06-01"

    def __init__(self, *, model: str | None = None, api_key: str | None = None):
        super().__init__(
            model=model,
            base_url="https://api.anthropic.com/v1",
            api_key=api_key if api_key is not None else os.environ.get("ANTHROPIC_API_KEY", ""),
        )
        if not self.api_key:
            raise ProviderUnavailable("anthropic: ANTHROPIC_API_KEY unset")

    def _url(self) -> str:
        return f"{self.base_url}/messages"

    def _headers(self, json_mode: bool) -> dict:
        # Anthropic's JSON mode is a tool, not response_format. Rather than
        # emulate a tool call here, the engine asks for JSON in the prompt and
        # relies on ModelResponse.json() to strip fences.
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": self.api_version,
        }

    def _extract(self, data: dict) -> str:
        parts = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
        return "".join(parts)


class GeminiProvider(_HTTPProvider):
    name = "gemini"
    default_model = "gemini-2.0-flash"

    def __init__(self, *, model: str | None = None, api_key: str | None = None):
        super().__init__(
            model=model,
            base_url="https://generativelanguage.googleapis.com/v1beta",
            api_key=api_key if api_key is not None else os.environ.get("GEMINI_API_KEY", ""),
        )
        if not self.api_key:
            raise ProviderUnavailable("gemini: GEMINI_API_KEY unset")

    def _url(self) -> str:
        return f"{self.base_url}/models/{self.model}:generateContent"

    def _headers(self, json_mode: bool) -> dict:
        return {"Content-Type": "application/json", "x-goog-api-key": self.api_key}

    def _extract(self, data: dict) -> str:
        return data["candidates"][0]["content"]["parts"][0]["text"]


class OllamaProvider(_HTTPProvider):
    """Local daemon. Speaks its own dialect, not the OpenAI one."""

    name = "ollama"
    default_model = "llama3.2:1b"

    def __init__(
        self,
        *,
        model: str | None = None,
        base_url: str | None = None,
        # Measured on the trial book: the largest chapter takes 185s on a 7B
        # local model. The old 300s ceiling left no margin when the host is also
        # serving other work, and one timeout failed a whole chapter — which the
        # verification gate then correctly, and uselessly, reported as
        # "chapter_extraction_complete" failing.
        timeout: int = 900,
    ):
        super().__init__(
            model=model,
            base_url=base_url or os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        )
        # No API key: a local daemon has none, and requiring one would make
        # this provider unusable by construction.
        self.timeout = timeout

    def _url(self) -> str:
        return f"{self.base_url}/api/chat"

    def _headers(self, json_mode: bool) -> dict:
        return {"Content-Type": "application/json"}

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        json_mode: bool = False,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> ModelResponse:
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}
        ]
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if json_mode:
            payload["format"] = "json"
        data = self._post(self._url(), payload, self._headers(json_mode))
        usage = data.get("eval_count", 0)
        return ModelResponse(
            text=data.get("message", {}).get("content", ""),
            model=self.model,
            provider=self.name,
            completion_tokens=int(usage or 0),
            raw=data,
        )


class StaticProvider:
    """Returns a fixed payload. For tests and for reproducing a recorded run."""

    name = "static"

    def __init__(self, payload: Any, model: str = "static"):
        self._payload = payload
        self.model = model
        self.calls: list[dict] = []

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        json_mode: bool = False,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> ModelResponse:
        self.calls.append({"prompt": prompt, "system": system, "json_mode": json_mode})
        text = self._payload if isinstance(self._payload, str) else json.dumps(self._payload)
        return ModelResponse(text=text, model=self.model, provider=self.name, raw={})

    def json(self) -> Any:
        return self._payload if not isinstance(self._payload, str) else json.loads(self._payload)


_REGISTRY: dict[str, type] = {
    "openai": OpenAICompatibleProvider,
    "openai-compatible": OpenAICompatibleProvider,
    "deepseek": DeepSeekProvider,
    "nim": NIMProvider,
    "nvidia-nim": NIMProvider,
    "anthropic": AnthropicProvider,
    "claude": AnthropicProvider,
    "gemini": GeminiProvider,
    "google": GeminiProvider,
    "ollama": OllamaProvider,
    "local": OllamaProvider,
}


def resolve_provider(kind: str | None = None, **kw) -> ModelProvider:
    """Build a provider by name.

    ``kind`` defaults to ``BU2_MODEL_PROVIDER`` then ``ollama``. Local-first is
    deliberate: it is the only family that needs no credential and no network,
    which keeps the engine runnable on a clean machine.
    """
    name = (kind or os.environ.get("BU2_MODEL_PROVIDER") or "ollama").strip().lower()
    if name not in _REGISTRY:
        raise ProviderUnavailable(f"unknown provider {name!r}; known: {sorted(_REGISTRY)}")
    return _REGISTRY[name](**kw)


def available_providers() -> list[dict[str, Any]]:
    """Report which providers are configured, without contacting any of them.

    Used by the acceptance gate so a run can say "the key exists but has no
    inference entitlement" instead of failing as an opaque timeout.
    """
    out = []
    for name in sorted(set(_REGISTRY)):
        envs = {
            "openai": ["OPENAI_API_KEY"],
            "openai-compatible": ["OPENAI_API_KEY"],
            "deepseek": ["DEEPSEEK_API_KEY"],
            "nim": ["NVIDIA_NIM_API_KEY"],
            "nvidia-nim": ["NVIDIA_NIM_API_KEY"],
            "anthropic": ["ANTHROPIC_API_KEY"],
            "claude": ["ANTHROPIC_API_KEY"],
            "gemini": ["GEMINI_API_KEY"],
            "google": ["GEMINI_API_KEY"],
            "ollama": [],
            "local": [],
        }[name]
        out.append(
            {
                "provider": name,
                "requires_key": bool(envs),
                "keys_present": {e: bool(os.environ.get(e)) for e in envs},
                "usable_without_network": name in ("ollama", "local"),
            }
        )
    return out
