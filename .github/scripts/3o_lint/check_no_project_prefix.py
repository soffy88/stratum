"""2. 检查元素与文件名是否包含项目或 Vendor 绑定前缀——SPEC v3.0 §2.4"""
from __future__ import annotations

import ast
from pathlib import Path

from paths import find_layer_dir

# 禁止的项目/Vendor 前缀（可在配置文件中扩充）
# 基础集（附录 B）+ 本生态实际出现过的项目前缀（helios_/btc_/tide_ 等）
BANNED_PREFIXES = (
    "aegis_", "finance_", "veya_", "vendor_", "proj_",
    "helios_", "btc_", "tide_", "mneme_", "stratum_", "aii_",
)
TARGET_LAYERS = ["oprim", "oskill", "omodul", "oservi"]


def check_no_project_prefix(root_dir: Path) -> list[str]:
    errors = []
    for layer in TARGET_LAYERS:
        layer_dir = find_layer_dir(root_dir, layer)
        if layer_dir is None:
            continue

        for py_file in layer_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            # 1. 检查文件名
            if py_file.name.startswith(BANNED_PREFIXES):
                errors.append(
                    f"[SPEC §2.4 Naming] File '{py_file.name}' in '{layer}' uses illegal project/vendor prefix."
                )

            # 2. 检查导出的顶层函数/类名
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            except SyntaxError:
                continue

            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if not node.name.startswith("_") and node.name.startswith(BANNED_PREFIXES):
                        errors.append(
                            f"[SPEC §2.4 Naming] {py_file.name}:{node.lineno} -> Entity '{node.name}' "
                            f"uses illegal project/vendor prefix."
                        )
    return errors
