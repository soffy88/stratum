"""6. 检查 omodul 配置类中必须显式声明 _enabled_pillars 且数量 ≥ 1——SPEC v3.0 §5.3"""
from __future__ import annotations

import ast
from pathlib import Path

VALID_PILLARS = {"fingerprint", "decision_trail", "report", "cost"}


def check_enabled_pillars(omodul_dir: Path) -> list[str]:
    errors = []
    if not omodul_dir.exists():
        return errors

    for py_file in omodul_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            continue

        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        found_pillar_decl = False

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for body_node in node.body:
                    # 查找 _enabled_pillars = {...} 声明
                    if isinstance(body_node, ast.Assign):
                        for target in body_node.targets:
                            if isinstance(target, ast.Name) and target.id == "_enabled_pillars":
                                found_pillar_decl = True
                                # 校验赋值是否为非空 Set
                                if isinstance(body_node.value, ast.Set):
                                    elements = {
                                        elt.value for elt in body_node.value.elts
                                        if isinstance(elt, ast.Constant)
                                    }
                                    if not elements:
                                        errors.append(
                                            f"[SPEC §5.3 Pillars] {py_file.name}:{body_node.lineno} -> "
                                            f"'_enabled_pillars' set is empty. Must enable at least 1 pillar."
                                        )
                                    elif not elements.issubset(VALID_PILLARS):
                                        errors.append(
                                            f"[SPEC §5.3 Pillars] {py_file.name}:{body_node.lineno} -> "
                                            f"Contains invalid pillars {elements - VALID_PILLARS}."
                                        )

        if not found_pillar_decl:
            errors.append(
                f"[SPEC §5.3 Pillars] {py_file.name} -> Config class lacks ClassVar '_enabled_pillars' declaration."
            )

    return errors
