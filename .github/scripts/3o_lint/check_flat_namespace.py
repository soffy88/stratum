"""1. 检查 oprim / oskill / omodul 是否保持扁平命名空间（严禁按业务领域建子目录）——SPEC v3.0 §2.2"""
from __future__ import annotations

from pathlib import Path

from paths import LAYERS, find_layer_dir

MODULE_LAYERS = ["oprim", "oskill", "omodul"]


def check_flat_namespace(root_dir: Path) -> list[str]:
    errors = []
    for layer in MODULE_LAYERS:
        layer_dir = find_layer_dir(root_dir, layer)
        if layer_dir is None:
            continue

        for item in layer_dir.iterdir():
            # 忽略私有目录和 pycache
            if item.is_dir() and not item.name.startswith(("_", ".")):
                errors.append(
                    f"[SPEC §2.2 Flat Namespace] Layer '{layer}' contains illegal subdirectory '{item.name}'. "
                    f"3O layers MUST be flat without domain submodules."
                )
    return errors
