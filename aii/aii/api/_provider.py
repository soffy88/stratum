import os
import logging
from obase import ProviderRegistry
from oprim.vector_encode import vector_encode

logger = logging.getLogger(__name__)

def register_providers():
    """Register computational providers for AII (A24 Routing)."""
    
    # 1. LLM Provider (DeepSeek)
    api_key = os.getenv("DEEPSEEK_API_KEY")
    # Note: we still register a dict for LLM as oprim/oskill LLM callers usually handle it
    ProviderRegistry.register("llm", "default", {
        "provider_type": "openai_compatible",
        "base_url": "https://api.deepseek.com",
        "api_key": api_key,
        "model": "deepseek-chat"
    })
    
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
