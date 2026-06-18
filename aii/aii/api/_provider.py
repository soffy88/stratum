import os
import json
import logging
import httpx
from obase import ProviderRegistry
from oprim import vector_encode

logger = logging.getLogger(__name__)

def _make_deepseek_caller(api_key: str, model: str = "deepseek-chat") -> callable:
    """Return a callable(prompt: str) -> str backed by DeepSeek via httpx.
    Uses a dedicated client with no proxy to avoid TLS interception by local proxies."""
    _client = httpx.Client(trust_env=False, timeout=60)

    def _call(prompt: str) -> str:
        resp = _client.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}]},
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    return _call

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
