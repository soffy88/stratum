"""Structured logging setup.

structlog was a declared dependency with zero actual usage — 109 call sites
across 36 files used plain stdlib `logging` with %s-interpolated messages, no
JSON, no correlation ids. Rewriting every call site to `structlog.get_logger()`
would be a huge, high-risk mechanical change for no functional difference in
what gets logged. Instead this configures structlog as the *formatter* for the
stdlib `logging` root handler (structlog.stdlib.ProcessorFormatter), so every
existing `logging.getLogger(__name__).info(...)` call — unmodified — starts
emitting structured (JSON in production, colored key=value in dev) output with
timestamp/level/logger/request context automatically attached. New code can
still opt into `structlog.get_logger()` directly for richer structured fields;
old code gets structure for free.

Call configure_logging() once, as early as possible in each app's module
(before any logger.info() calls happen at import time).
"""

from __future__ import annotations

import logging
import os
import sys

try:
    import structlog
except ImportError:
    structlog = None  # type: ignore[assignment]


def configure_logging() -> None:
    if structlog is None:
        # Not every image has structlog installed yet (e.g. Dockerfile.api's
        # minimal pip list, pre-rollout) — fall back to plain stdlib logging
        # rather than crash the whole app on import.
        logging.basicConfig(level=os.environ.get("STRATUM_LOG_LEVEL", "INFO").upper())
        return

    is_prod = os.environ.get("STRATUM_ENV") == "production"
    log_level = os.environ.get("STRATUM_LOG_LEVEL", "INFO").upper()

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=shared_processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    renderer = structlog.processors.JSONRenderer() if is_prod else structlog.dev.ConsoleRenderer()
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(log_level)
