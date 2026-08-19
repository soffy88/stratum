"""9. 采集与比对所有元素的执行模型 (sync/async) 契约，防止隐蔽变更破坏调用方——SPEC v3.0 §0.2 / 附录 A #5

无 baseline 时仅采集契约（collect_async_contracts）。
提供 baseline JSON 时进行比对，sync<->async 翻转记为 MAJOR Breaking Change。
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from paths import find_layer_dir

TARGET_LAYERS = ["oprim", "oskill", "omodul"]


def collect_async_contracts(root_dir: Path) -> dict[str, bool]:
    """采集每个导出的顶层函数的 async 状态"""
    contracts = {}
    for layer in TARGET_LAYERS:
        layer_dir = find_layer_dir(root_dir, layer)
        if layer_dir is None:
            continue

        for py_file in layer_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not node.name.startswith("_"):
                        key = f"{layer}.{py_file.stem}.{node.name}"
                        contracts[key] = isinstance(node, ast.AsyncFunctionDef)
    return contracts


def check_async_contract(root_dir: Path, baseline_file: Path | None = None) -> list[str]:
    errors = []
    current_contracts = collect_async_contracts(root_dir)

    if baseline_file and baseline_file.exists():
        baseline_contracts = json.loads(baseline_file.read_text(encoding="utf-8"))
        for func_key, is_async in current_contracts.items():
            if func_key in baseline_contracts:
                old_async = baseline_contracts[func_key]
                if old_async != is_async:
                    errors.append(
                        f"[SPEC §0.2 Async Contract BREAKING] '{func_key}' execution model changed "
                        f"from {'async' if old_async else 'sync'} to {'async' if is_async else 'sync'}. "
                        f"This is a MAJOR Breaking Change!"
                    )
    return errors


if __name__ == "__main__":
    import sys

    contracts = collect_async_contracts(Path(sys.argv[1] if len(sys.argv) > 1 else "."))
    print(json.dumps(contracts, indent=2, ensure_ascii=False))
