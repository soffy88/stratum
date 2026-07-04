"""Structured logging setup for the AII backend — mirrors stratum's
stratum/logging_config.py (structlog declared as a dependency, zero usage
before this). Configures structlog as the stdlib logging formatter so
existing `logging.getLogger(__name__)` call sites get structured output
without a call-site rewrite; see stratum's module docstring for the full
rationale.
"""

from __future__ import annotations

import logging
import os
import sys

import structlog


def configure_logging() -> None:
    is_prod = os.environ.get("AII_ENV", os.environ.get("STRATUM_ENV")) == "production"
    log_level = os.environ.get("AII_LOG_LEVEL", "INFO").upper()

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
