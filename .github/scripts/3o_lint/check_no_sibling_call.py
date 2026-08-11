"""3. 检查同层裸调禁令——SPEC v3.0 §1.2
- oprim: 禁裸调 sibling
- omodul: 禁裸调 sibling (走 oservi 编排)
- oskill: 允许受限互调（深度 ≤ 2，且必须在 docstring 中显式声明）
"""
from __future__ import annotations

import ast
from pathlib import Path

from paths import find_layer_dir


def _get_imports(tree: ast.AST) -> dict[str, str]:
    """提取文件中的 import 映射关系，如 'other_oprim' -> 'oprim'"""
    imports = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            root_mod = node.module.split(".")[0]
            for alias in node.names:
                imports[alias.name] = root_mod
    return imports


def check_no_sibling_call(root_dir: Path) -> list[str]:
    errors = []

    # A. 检查 oprim & omodul 同层裸调
    for layer in ["oprim", "omodul"]:
        layer_dir = find_layer_dir(root_dir, layer)
        if layer_dir is None:
            continue

        for py_file in layer_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            imports = _get_imports(tree)

            for func_name, mod in imports.items():
                if mod == layer:
                    errors.append(
                        f"[SPEC §1.2 Sibling Call] {py_file.name} illegally imports sibling '{func_name}' "
                        f"from the same layer '{layer}'."
                    )

    # B. 检查 oskill 互调约束 (深度 ≤ 2 & Docstring 声明)
    oskill_dir = find_layer_dir(root_dir, "oskill")
    if oskill_dir is not None:
        oskill_deps: dict[str, list[str]] = {}

        for py_file in oskill_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            imports = _get_imports(tree)

            sibling_calls = [name for name, mod in imports.items() if mod == "oskill"]
            oskill_deps[py_file.stem] = sibling_calls

            # 如果调用了 sibling oskill，必须在 docstring 中写明
            if sibling_calls:
                doc = ast.get_docstring(tree) or ""
                if "oskill" not in doc.lower():
                    errors.append(
                        f"[SPEC §1.2 oskill Constraint] {py_file.name} calls sibling oskills {sibling_calls} "
                        f"but lacks docstring disclosure."
                    )

        # 检查调用链深度 (A -> B -> C 深度为 3，违规)
        for caller, callee_list in oskill_deps.items():
            for callee in callee_list:
                nested_callees = oskill_deps.get(callee, [])
                if nested_callees:
                    errors.append(
                        f"[SPEC §1.2 Call Depth] Call chain '{caller} -> {callee} -> {nested_callees}' "
                        f"exceeds max allowed depth of 2."
                    )

    return errors
