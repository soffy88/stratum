import os
import logging
from obase import ProviderRegistry
from oprim.vector_encode import vector_encode

logger = logging.getLogger(__name__)

def register_providers():
    """Register computational providers for AII (A24 Routing)."""
    
    # 1. LLM Provider (DeepSeek via oprim/oskill standard mechanism)
    # Note: oprim/oskill usually look for provider configurations in ProviderRegistry
    # For DeepSeek, we expect it to be handled by the underlying LLM caller.
    # We register a placeholder/config for 'llm/default'
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key or api_key == "your_key_here":
        logger.warning("DEEPSEEK_API_KEY is not set correctly. LLM calls will fail.")
    
    # In 3O, we typically register a factory or a configuration for the provider.
    # Since we are using oprim/oskill's default behavior:
    ProviderRegistry.register("llm", "default", {
        "provider_type": "openai_compatible", # DeepSeek is OpenAI compatible
        "base_url": "https://api.deepseek.com",
        "api_key": api_key,
        "model": "deepseek-chat"
    })
    
    # 2. Embedding Provider (Local BGE-M3 via sentence-transformers)
    # We register the 'embedding/default'
    ProviderRegistry.register("embedding", "default", {
        "provider_type": "local",
        "model_name": "BAAI/bge-m3",
        "device": "cpu" # Default to CPU for stability in this env
    })
    
    logger.info("AII Providers registered: llm/default, embedding/default")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    register_providers()
    print(f"LLM default registered: {ProviderRegistry.has('llm', 'default')}")
    print(f"Embedding default registered: {ProviderRegistry.has('embedding', 'default')}")
