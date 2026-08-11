"""4. 检查 oprim 签名：最多允许 ≤1 个位置参数，其余强制为 keyword-only (*)——SPEC v3.0 §3.4"""
from __future__ import annotations

import ast
from pathlib import Path

from paths import find_layer_dir


def check_oprim_keyword_only(oprim_dir: Path) -> list[str]:
    errors = []
    if not oprim_dir.exists():
        return errors

    for py_file in oprim_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            continue

        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_"):
                    continue

                pos_args = node.args.args
                if len(pos_args) > 1:
                    arg_names = [a.arg for a in pos_args]
                    errors.append(
                        f"[SPEC §3.4 oprim Signature] {py_file.name}:{node.lineno} -> Function '{node.name}' "
                        f"has {len(pos_args)} positional args {arg_names}. Max allowed is 1. "
                        f"Add '*' to convert remaining args to keyword-only."
                    )
    return errors
