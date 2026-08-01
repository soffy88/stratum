"""P2: Mount AII routes into Stratum SL under /api/aii/* prefix.

AII's FastAPI routers are imported from the `aii` Python package (bind-mounted
at /opt/aii in the container). This module:
  1. Imports all AII route modules
  2. Provides mount_aii_routes(app) to include them with /api/aii prefix
  3. Provides init_aii_backend() for lifespan startup (asyncpg pool)
  4. Provides apply_aii_monkeypatch() for the oskill fix
  5. Provides register_aii_providers() for LLM/embedding providers
"""

import logging
import os

logger = logging.getLogger(__name__)

# ── Lazy imports (AII package may not be available in all environments) ──────

_import_failed = False


def _import_aii():
    """Import AII modules. Returns False if import fails."""
    global _import_failed
    if _import_failed:
        return False
    try:
        from aii.api.routes import (  # noqa: F401
            health,
            ingest,
            feed,
            query,
            chat,
            evolution,
            governance,
            stats,
            display,
            textbook_export,
            delete,
            pipelines,
            internal,
            learning,
            skills,
            classify,
            graph_concepts,
            context_recall,
        )
        return True
    except ImportError as e:
        logger.warning("AII package not importable — /api/aii/* routes disabled: %s", e)
        _import_failed = True
        return False


def mount_aii_routes(app) -> None:
    """Mount all AII routes at /api/* in stratum-sl.

    The Next.js rewrite for /api/aii/* strips the /api/aii prefix:
      client: GET /api/aii/api/stats/overview
      rewrite: GET stratum-sl/api/stats/overview

    So AII routes must be registered at /api/* in stratum-sl — matching
    exactly how they were in the standalone AII backend.
    """
    if not _import_aii():
        return

    from aii.api.routes import (
        health as aii_health,
        ingest as aii_ingest,
        feed as aii_feed,
        query as aii_query,
        chat as aii_chat,
        evolution as aii_evolution,
        governance as aii_governance,
        stats as aii_stats,
        display as aii_display,
        textbook_export as aii_textbook,
        delete as aii_delete,
        pipelines as aii_pipelines,
        internal as aii_internal,
        learning as aii_learning,
        skills as aii_skills,
        classify as aii_classify,
        graph_concepts as aii_graph_concepts,
        context_recall as aii_context_recall,
    )

    # Routes that were mounted with prefix="/api" in AII's standalone app.
    # After Next.js strips /api/aii, they arrive at /api/* in stratum-sl.
    api_routers = [
        (aii_pipelines, "aii-pipelines"),
        (aii_health, "aii-health"),
        (aii_ingest, "aii-ingest"),
        (aii_feed, "aii-feed"),
        (aii_query, "aii-query"),
        (aii_chat, "aii-chat"),
        (aii_evolution, "aii-evolution"),
        (aii_governance, "aii-governance"),
        (aii_stats, "aii-stats"),
        (aii_display, "aii-display"),
        (aii_textbook, "aii-textbook"),
        (aii_delete, "aii-delete"),
        (aii_learning, "aii-learning"),
        (aii_skills, "aii-skills"),
        (aii_classify, "aii-classify"),
        (aii_graph_concepts, "aii-graph"),
        (aii_context_recall, "aii-context"),
    ]

    for router_mod, tag in api_routers:
        app.include_router(
            router_mod.router,
            prefix="/api",
            tags=[tag],
        )

    # Internal routes (no /api prefix, e.g. /internal/embed)
    app.include_router(aii_internal.router, tags=["aii-internal"])

    logger.info("AII routes mounted at /api/* (via Next.js /api/aii/* rewrite)")


async def init_aii_backend() -> None:
    """Initialize AII's asyncpg connection pool.

    Must be called during app lifespan startup, after environment is loaded.
    """
    if not _import_aii():
        return

    from aii.api._dependencies import backend as aii_backend

    dsn = os.getenv("AII_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not dsn:
        logger.warning("AII_DATABASE_URL not set — AII routes will fail on DB access")
        return

    aii_backend.dsn = dsn
    await aii_backend._ensure_pool()
    logger.info("AII asyncpg pool initialized (dsn=%s...)", dsn[:40])


def apply_aii_monkeypatch() -> None:
    """Apply oskill monkey-patch that fixes internal module references.

    This was originally in AII's lifespan and must run before any KU extraction.
    """
    if not _import_aii():
        return

    try:
        import oskill.ku_extract_pipeline
        import oprim.structural_chunk
        import oprim.llm_extract_ku
        import oprim.ku_gate_validate

        oskill.ku_extract_pipeline.structural_chunk = oprim.structural_chunk.structural_chunk
        oskill.ku_extract_pipeline.llm_extract_ku = oprim.llm_extract_ku.llm_extract_ku
        oskill.ku_extract_pipeline.ku_gate_validate = oprim.ku_gate_validate.ku_gate_validate
        logger.info("AII oskill monkey-patch applied.")
    except Exception as e:
        logger.warning("AII oskill monkey-patch failed (non-fatal): %s", e)


def register_aii_providers() -> None:
    """Register AII's LLM and embedding providers.

    Safe to call even if Stratum already registered its own providers —
    AII providers use distinct names (deepseek-flash, nim, ollama-local).
    """
    if not _import_aii():
        return

    try:
        from aii.api._provider import register_providers
        register_providers()
        logger.info("AII providers registered.")
    except Exception as e:
        logger.warning("AII provider registration failed (non-fatal): %s", e)


async def shutdown_aii_backend() -> None:
    """Close AII's asyncpg pool. Call during app shutdown."""
    if _import_failed:
        return

    try:
        from aii.api._dependencies import backend as aii_backend
        if aii_backend._pool:
            await aii_backend._pool.close()
            logger.info("AII asyncpg pool closed.")
    except Exception as e:
        logger.warning("AII pool shutdown failed: %s", e)
