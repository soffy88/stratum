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
    Legacy callers may also call the inner _call_sync(prompt: str) -> str directly.
    """
    _client = httpx.Client(trust_env=False, timeout=120)

    def _call_sync(prompt: str) -> str:
        """Synchronous DeepSeek call used as thread executor target."""
        resp = _client.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}]},
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    async def _call_async(messages=None, *, system: str = "", max_tokens: int = 4096, **_):
        """Async omodul-compatible LLM caller (Anthropic message format → Anthropic response dict)."""
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

    # Attach sync helper for legacy callers
    _call_async.call_sync = _call_sync
    return _call_async

def register_providers():
    """Register computational providers for AII (A24 Routing)."""

    # 1. LLM Provider (DeepSeek) — registered as callable(prompt)->str
    api_key = os.getenv("DEEPSEEK_API_KEY")
    ProviderRegistry.register("llm", "default", _make_deepseek_caller(api_key))
    
    # 2. Embedding Provider (Real BGE-M3)
    from oprim.embedding.bge_m3 import BgeM3Embedder
    try:
        embedder = BgeM3Embedder()
        ProviderRegistry.register("embedding", "default", embedder.embed)
        logger.info("REAL BGE-M3 Provider registered.")
    except Exception as e:
        logger.error(f"Failed to load REAL BGE-M3: {e}")
        # Fallback to dict might cause TypeError in vector_encode, 
        # so we let it fail or log clearly.
    
    logger.info("AII Providers registered: llm/default, embedding/default")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    register_providers()
    print(f"LLM default registered: {ProviderRegistry.has('llm', 'default')}")
    print(f"Embedding default registered: {ProviderRegistry.has('embedding', 'default')}")
