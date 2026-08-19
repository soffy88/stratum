"""5. 检查 omodul：SPEC v3.0 §5.2 / §5.4
1. 位置参数必须满足三件套 (config, input_data, output_dir)
2. 内部严禁抛出 Exception (失败必须返回 status='failed' 字典)
"""
from __future__ import annotations

import ast
from pathlib import Path

EXPECTED_ARGS = ["config", "input_data", "output_dir"]

# SPEC §5.5：compute_fingerprint_for 的强制签名是 (config, input_data) —— 豁免三件套检查
EXEMPT_FUNCS = {"compute_fingerprint_for"}


def check_omodul_signature(omodul_dir: Path) -> list[str]:
    errors = []
    if not omodul_dir.exists():
        return errors

    for py_file in omodul_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            continue

        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_"):
                    continue

                # 1. 签名检查
                pos_args = [a.arg for a in node.args.args]
                if node.name not in EXEMPT_FUNCS and pos_args[:3] != EXPECTED_ARGS:
                    errors.append(
                        f"[SPEC §5.2 omodul Signature] {py_file.name}:{node.lineno} -> Function '{node.name}' "
                        f"positional args are {pos_args[:3]}. Expected standard triplet: {EXPECTED_ARGS}."
                    )

                # 2. 失败不 raise 检查 (扫描未捕获的 raise 语句)
                for sub_node in ast.walk(node):
                    if isinstance(sub_node, ast.Raise) and sub_node.exc:
                        # 允许重新抛出 asyncio.CancelledError
                        exc_name = ""
                        if isinstance(sub_node.exc, ast.Name):
                            exc_name = sub_node.exc.id
                        if exc_name != "CancelledError":
                            errors.append(
                                f"[SPEC §5.4 omodul No-Raise] {py_file.name}:{sub_node.lineno} -> "
                                f"omodul function '{node.name}' contains 'raise {exc_name}'. "
                                f"omodul MUST NOT raise exceptions on failure (return status='failed' dict instead)."
                            )
    return errors
