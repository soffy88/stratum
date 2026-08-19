"""8. 检查 oservi 引擎骨架：严禁硬编码 import 具体的业务元素（只能通过 Manifest 注入）——SPEC v3.0 §8.2 红线 5 / §8.8"""
from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN_CONCRETE_IMPORTS = {"oprim", "oskill", "omodul"}


def check_oservi_injection(oservi_dir: Path) -> list[str]:
    errors = []
    if not oservi_dir.exists():
        return errors

    for py_file in oservi_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            continue

        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                root_mod = node.module.split(".")[0]
                if root_mod in FORBIDDEN_CONCRETE_IMPORTS:
                    errors.append(
                        f"[SPEC §8.2 Dependency Inversion] {py_file.name}:{node.lineno} -> "
                        f"oservi skeleton hardcodes import from '{node.module}'. "
                        f"Implementations MUST be injected via ServiceManifest."
                    )
    return errors
