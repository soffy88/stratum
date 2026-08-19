"""3O 层目录定位助手。

支持两种仓库布局：
  root/oprim/          # 扁平：层仓库 == 层包父目录（oprim/*.py 直接在层目录下）
  root/oprim/oprim/    # 嵌套：层仓库内再套一层真实包目录（oprim/oprim/*.py）

SPEC v3.0 §2.1：5 个独立 package，各自独立 repo。
实际部署中（/platform/3O/<layer>/<layer>）是嵌套布局，故需要此解析。
"""
from __future__ import annotations

from pathlib import Path

LAYERS = ("oprim", "oskill", "omodul", "oservi", "obase")


def find_layer_dir(root: Path, layer: str) -> Path | None:
    """返回层包的真实代码目录；不存在则返回 None。"""
    base = root / layer
    if not base.is_dir():
        return None
    nested = base / layer
    if nested.is_dir():
        return nested
    return base
