import asyncio
import concurrent.futures
import os
import logging
import httpx
from obase import ProviderRegistry
from oprim import vector_encode

logger = logging.getLogger(__name__)


def _make_deepseek_caller(api_key: str, model: str = "deepseek-chat") -> callable:
    """Return an async callable compatible with both omodul (messages/system/max_tokens kwargs)
    and the legacy synthesis_engine (single positional prompt string via executor).

    Signature: async (messages=None, *, system='', max_tokens=4096, **_) -> dict
    The returned dict has the Anthropic shape: {"content": [{"type": "text", "text": "..."}]}
    Legacy callers may also call the inner _call_sync_json(prompt: str) -> str directly.
    _call_sync_json uses response_format=json_object to fix ~70% retry rate in llm_extract_ku.
    _call_sync (used internally by _call_async for synthesis) does NOT force JSON mode.
    """
    _client = httpx.Client(trust_env=False, timeout=120)

    def _call_sync(prompt: str) -> str:
        """Synchronous DeepSeek call for synthesis (plain text, no JSON mode)."""
        resp = _client.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}]},
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def _call_sync_json(prompt: str) -> str:
        """Synchronous DeepSeek call for extraction (JSON mode → eliminates markdown fence retries)."""
        resp = _client.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    async def _call_async(messages=None, *, system: str = "", max_tokens: int = 4096, **_):
        """Async omodul-compatible LLM caller (Anthropic message format → Anthropic response dict).
        Uses plain-text _call_sync (not JSON mode) for synthesis compatibility."""
        parts: list[str] = []
        if system:
            parts.append(system)
        for msg in (messages or []):
            if isinstance(msg, dict) and msg.get("role") == "user":
                parts.append(msg.get("content", ""))
        combined = "\n\n".join(p for p in parts if p)
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            answer = await loop.run_in_executor(ex, _call_sync, combined)
        return {"content": [{"type": "text", "text": answer}]}

    # Extraction callers (llm_extract_ku) use call_sync → JSON mode
    _call_async.call_sync = _call_sync_json
    return _call_async


def _make_ollama_caller(model: str = "qwen2.5:7b", base_url: str = "http://localhost:11434") -> callable:
    """Return a caller backed by local Ollama (format=json guaranteed clean JSON output).

    Used as provider="ollama-local" for low-trust sources (video/audio/podcast).
    grade_cap=unverified is enforced upstream in auto_ingest; this caller just does extraction.
    """
    _client = httpx.Client(trust_env=False, timeout=120)  # 120s covers cold model load

    def _call_sync(prompt: str) -> str:
        resp = _client.post(
            f"{base_url}/api/generate",
            json={"model": model, "prompt": prompt[:3000], "stream": False, "format": "json"},
        )
        resp.raise_for_status()
        return resp.json()["response"]

    async def _call_async(messages=None, *, system: str = "", max_tokens: int = 4096, **_):
        """Async wrapper (for omodul compatibility; extraction uses call_sync directly)."""
        parts: list[str] = []
        if system:
            parts.append(system)
        for msg in (messages or []):
            if isinstance(msg, dict) and msg.get("role") == "user":
                parts.append(msg.get("content", ""))
        combined = "\n\n".join(p for p in parts if p)
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            answer = await loop.run_in_executor(ex, _call_sync, combined)
        return {"content": [{"type": "text", "text": answer}]}

    _call_async.call_sync = _call_sync
    return _call_async

def register_providers():
    """Register computational providers for AII (A24 Routing)."""

    # 1. LLM Provider (DeepSeek) — default, for paper/book/science
    api_key = os.getenv("DEEPSEEK_API_KEY")
    ProviderRegistry.register("llm", "default", _make_deepseek_caller(api_key))

    # 2. LLM Provider (Ollama qwen2.5:7b) — for low-trust sources (video/audio/podcast)
    #    grade_cap=unverified enforced upstream; this provider is fast + free + JSON-clean
    ollama_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    try:
        ProviderRegistry.register("llm", "ollama-local", _make_ollama_caller(ollama_model, ollama_base))
        logger.info("Ollama-local provider registered: %s @ %s", ollama_model, ollama_base)
    except Exception as e:
        logger.warning("Ollama-local registration failed (non-fatal): %s", e)

    # 3. Embedding Provider (Real BGE-M3)
    from oprim.embedding.bge_m3 import BgeM3Embedder
    try:
        embedder = BgeM3Embedder()
        ProviderRegistry.register("embedding", "default", embedder.embed)
        logger.info("REAL BGE-M3 Provider registered.")
    except Exception as e:
        logger.error(f"Failed to load REAL BGE-M3: {e}")

    logger.info("AII Providers registered: llm/default(DeepSeek), llm/ollama-local(qwen2.5:7b), embedding/default")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    register_providers()
    print(f"LLM default registered: {ProviderRegistry.has('llm', 'default')}")
    print(f"Embedding default registered: {ProviderRegistry.has('embedding', 'default')}")
