"""Model provider for deck writing.

Reuses the BU2 ``ModelProvider`` boundary (and its transient-error retry) rather
than a second HTTP client. The default is the local ``veya-fllm`` profile: the
freellmapi gateway, OpenAI-compatible, model ``auto:veya-fllm``, reachable from
the backend containers at the docker bridge gateway.

Environment (all optional):

``PPT_LLM_PROVIDER``  provider family (default ``openai`` = OpenAI-compatible)
``PPT_LLM_MODEL``     model id (default ``auto:veya-fllm``)
``PPT_LLM_BASE_URL``  base URL (default ``OPENAI_BASE_URL`` then the gateway)
``PPT_LLM_API_KEY``   key (default ``OPENAI_API_KEY``)
"""

from __future__ import annotations

import os

from stratum.services.bu_v2_provider import ModelProvider, resolve_provider

DEFAULT_MODEL = "auto:veya-fllm"
DEFAULT_BASE_URL = "http://172.19.0.1:3001/v1"
_OPENAI_FAMILY = {"openai", "openai-compatible"}


def ppt_provider_config() -> dict[str, str]:
    """The resolved configuration, without the key (safe to log or return)."""
    kind = (os.environ.get("PPT_LLM_PROVIDER") or "openai").strip().lower()
    model = os.environ.get("PPT_LLM_MODEL") or DEFAULT_MODEL
    base = (
        os.environ.get("PPT_LLM_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or DEFAULT_BASE_URL
    )
    return {"provider": kind, "model": model, "base_url": base}


def resolve_ppt_provider() -> ModelProvider:
    """Build the provider deck writing uses. Raises ``ProviderUnavailable``."""
    cfg = ppt_provider_config()
    if cfg["provider"] in _OPENAI_FAMILY:
        key = os.environ.get("PPT_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
        return resolve_provider(
            cfg["provider"], model=cfg["model"], base_url=cfg["base_url"], api_key=key or None
        )
    return resolve_provider(cfg["provider"], model=cfg["model"])
