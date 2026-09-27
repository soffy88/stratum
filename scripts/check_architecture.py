#!/usr/bin/env python3
"""Static import-boundary gate for the Stratum modular monolith.

This is intentionally AST-based: the check must work in CI without importing
the application (and therefore without Postgres, provider keys, or optional
AI packages).  It enforces the first bounded-context rule now and becomes
stricter automatically when a ``domain`` package is introduced.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "stratum"

# Services and adapters may depend on domain code, but never on HTTP/MCP
# delivery layers.  This prevents the common “service imports router” cycle.
SERVICE_ROOTS = (SRC / "services", SRC / "service", SRC / "dao")
SERVICE_FORBIDDEN = ("stratum.api", "stratum.http_api", "stratum.mcp_server")

# Pure domain modules have no I/O or framework dependencies.  The explicit
# list is small by design: it gives us a safe seam for deterministic tests
# while the rest of the legacy service layer is migrated incrementally.
PURE_MODULES = (SRC / "services" / "spaced_repetition.py",)
PURE_FORBIDDEN_ROOTS = (
    "fastapi",
    "psycopg2",
    "asyncpg",
    "stratum.db",
    "mcp",
    "openai",
    "anthropic",
    "dashscope",
    "oprim",
    "oskill",
)


def _imports(path: Path) -> list[tuple[str, int]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        return [(f"<parse error: {exc}>", 1)]
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append((node.module, node.lineno))
    return found


def check() -> list[str]:
    errors: list[str] = []
    for root in SERVICE_ROOTS:
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            for module, lineno in _imports(path):
                if any(
                    module == prefix or module.startswith(prefix + ".")
                    for prefix in SERVICE_FORBIDDEN
                ):
                    errors.append(
                        f"{path.relative_to(ROOT)}:{lineno}: service layer imports delivery module {module}"
                    )

    for path in PURE_MODULES:
        if not path.is_file():
            continue
        for module, lineno in _imports(path):
            if any(
                module == prefix or module.startswith(prefix + ".")
                for prefix in PURE_FORBIDDEN_ROOTS
            ):
                errors.append(
                    f"{path.relative_to(ROOT)}:{lineno}: pure module imports forbidden dependency {module}"
                )
    return errors


if __name__ == "__main__":
    violations = check()
    if violations:
        print("Architecture boundary violations:", file=sys.stderr)
        print("\n".join(f"- {item}" for item in violations), file=sys.stderr)
        raise SystemExit(1)
    print("Architecture boundaries: OK")
