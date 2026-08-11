#!/usr/bin/env python3
"""Stratum 侧 3O 消费方合规审计（SPEC v3.0）。

stratum 是 Layer-4 项目服务层，本身不包含 3O 层代码；层包部署于 /opt/platform
（dev: /platform/3O）。本脚本审计 stratum 对 3O 包的消费是否合规：

  A. async 契约交叉核对（§0.2 / 附录 A #5 精神）：
     取 /platform 中 stratum 实际 import 的每个元素的 sync/async 状态，
     检查 stratum 调用点是否 await（async 不 await / sync 被 await 均记错）。
  B. 导入卫生：私有（_ 前缀）平台模块耦合、深路径依赖。
  C. 各层消费面统计。

用法:
    python audit_stratum_usage.py [--root stratum] [--platform /data/soffy/projects/platform/3O]
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

LAYERS = ("oprim", "oskill", "omodul", "obase", "oservi")


# ─────────────────────────── 平台侧解析 ───────────────────────────

def _platform_pkg_dir(platform_root: Path, layer: str) -> Path:
    base = platform_root / layer
    nested = base / layer
    return nested if nested.is_dir() else base


def _resolve_module_file(pkg_dir: Path, module: str) -> Path | None:
    """把 'oprim.llm.llm_call' 解析为平台包内文件路径。"""
    rel = module.split(".", 1)[1] if "." in module else ""
    if not rel:
        return None
    cand = pkg_dir / f"{rel.replace('.', '/')}.py"
    if cand.is_file():
        return cand
    cand_pkg = pkg_dir / rel.replace(".", "/")
    for init in ("__init__.py", "__init__.pyi"):
        if (cand_pkg / init).is_file():
            return cand_pkg / init
    return None


def _find_func_def(tree: ast.AST, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def _is_async_in_file(py_file: Path, name: str) -> bool | None:
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    except (OSError, SyntaxError):
        return None
    node = _find_func_def(tree, name)
    if node is not None:
        return isinstance(node, ast.AsyncFunctionDef)
    # 可能经 __init__ 再导出：跟随 import
    if py_file.name == "__init__.py":
        for sub in ast.walk(tree):
            if isinstance(sub, ast.ImportFrom) and sub.module:
                for alias in sub.names:
                    if alias.name == name:
                        base_mod = py_file.parent.name
                        target = _resolve_module_file(py_file.parent.parent, f"{base_mod}.{sub.module}")
                        if target:
                            r = _is_async_in_file(target, alias.asname or alias.name)
                            if r is not None:
                                return r
    return None


def resolve_platform_func_async(platform_root: Path, module: str, name: str) -> bool | None:
    """module 如 'oprim.llm.llm_call'（或顶层 'oprim'），name 如 'llm_call'。"""
    layer = module.split(".")[0]
    if layer not in LAYERS:
        return None
    pkg_dir = _platform_pkg_dir(platform_root, layer)
    if "." in module:
        py_file = _resolve_module_file(pkg_dir, module)
        if py_file:
            r = _is_async_in_file(py_file, name)
            if r is not None:
                return r
    # 顶层导出（from oprim import X）：跟 __init__.py
    init = pkg_dir / "__init__.py"
    if init.is_file():
        r = _is_async_in_file(init, name)
        if r is not None:
            return r
    return None


# ─────────────────────────── stratum 侧解析 ───────────────────────────

def collect_stratum_imports(root: Path) -> list[dict]:
    """返回 [{file, module, name, alias, lineno}]，module 为 oprim/oskill/... 根。"""
    found = []
    for py in root.rglob("*.py"):
        if any(part.startswith((".", "_", "__")) for part in py.relative_to(root).parts):
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                root_mod = node.module.split(".")[0]
                if root_mod in LAYERS:
                    for alias in node.names:
                        found.append({
                            "file": py, "module": node.module, "name": alias.name,
                            "alias": alias.asname or alias.name, "lineno": node.lineno,
                        })
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    root_mod = alias.name.split(".")[0]
                    if root_mod in LAYERS:
                        found.append({
                            "file": py, "module": alias.name, "name": None,
                            "alias": alias.asname or alias.name, "lineno": node.lineno,
                        })
    return found


def check_call_sites(root: Path, imports: list[dict], platform_root: Path) -> list[str]:
    """对每个 stratum 文件：找 import 的 async 平台函数是否被正确 await。"""
    errors: list[str] = []

    # 文件级解析缓存
    from collections import defaultdict
    files: dict[Path, ast.AST] = {}
    for imp in imports:
        f = imp["file"]
        if f not in files:
            try:
                files[f] = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
            except (OSError, SyntaxError):
                files[f] = None

    # 每个文件：alias -> (platform_async|None)
    alias_map: dict[Path, dict[str, bool | None]] = defaultdict(dict)
    for imp in imports:
        if imp["name"] is None:
            continue  # import oprim 整体：不逐符号核对
        alias_map[imp["file"]][imp["alias"]] = resolve_platform_func_async(
            platform_root, imp["module"], imp["name"]
        )

    for f, tree in files.items():
        if tree is None:
            continue
        alias_async = alias_map.get(f, {})
        for node in ast.walk(tree):
            # 只在函数体/模块体内的调用点检查
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Name):
                continue
            if func.id not in alias_async:
                continue
            plat_async = alias_async[func.id]
            if plat_async is None:
                continue  # 平台未解析到，跳过
            parents = _parents(tree, node)
            rel = f.relative_to(root)

            # asyncio 驱动调用（coroutine 被调度/驱动，不算违规）
            ASYNCIO_DRIVERS = {"run", "gather", "create_task", "wait",
                               "ensure_future", "run_coroutine_threadsafe", "to_thread"}
            driven = any(
                isinstance(p, ast.Call)
                and (isinstance(p.func, ast.Attribute) and p.func.attr in ASYNCIO_DRIVERS
                     or isinstance(p.func, ast.Name) and p.func.id in {"gather", "wait"})
                for p in parents
            )
            direct_await = bool(parents) and isinstance(parents[0], ast.Await)

            if plat_async:
                # async fn：必须被 await，或被 asyncio.run/gather/create_task 等驱动
                if not direct_await and not driven:
                    errors.append(
                        f"[SPEC §0.2 Async Contract] {rel}:{node.lineno} -> calls async platform "
                        f"function '{func.id}' WITHOUT await. "
                        f"(platform: async def — MUST await; sync call will produce unawaited coroutine.)"
                    )
            else:
                # sync fn：仅当被【直接】await（await fn(...)）才违规；
                # await run_in_executor(lambda: fn(...)) 是合法非阻塞用法。
                if direct_await:
                    errors.append(
                        f"[SPEC §0.2 Async Contract] {rel}:{node.lineno} -> awaits sync platform "
                        f"function '{func.id}' (platform: sync def — await raises TypeError; "
                        f"use run_in_executor/to_thread if it must not block the loop)."
                    )
    return errors


def _parents(tree: ast.AST, node: ast.AST) -> list[ast.AST]:
    parents: dict[int, ast.AST] = {id(node): node}
    out = []
    stack = [tree]
    while stack:
        cur = stack.pop()
        for child in ast.iter_child_nodes(cur):
            parents[id(child)] = cur
            if child is node:
                out = [cur]
                cur2 = cur
                while cur2 is not tree:
                    cur2 = parents[id(cur2)]
                    out.append(cur2)
                return out
            stack.append(child)
    return out


def scan_import_hygiene(imports: list[dict], root: Path) -> list[str]:
    errors = []
    seen = set()  # (file, lineno) 去重，同行动名展开只报一次
    for imp in imports:
        rel = imp["file"].relative_to(root)
        key = (str(rel), imp["lineno"])
        if key in seen:
            continue
        if imp["name"] is None:
            continue
        # 私有模块（_ 前缀）耦合
        parts = imp["module"].split(".")
        if any(p.startswith("_") for p in parts[1:]):
            seen.add(key)
            errors.append(
                f"[Import Hygiene] {rel}:{imp['lineno']} -> imports PRIVATE platform module "
                f"'{imp['module']}' (internal '_' namespace). Breaks on refactor; "
                f"SPEC §7.3 元素私有 _providers/ 不对外暴露."
            )
        # 深路径（≥2 级子模块）
        elif len(parts) >= 3:
            seen.add(key)
            errors.append(
                f"[Import Hygiene] {rel}:{imp['lineno']} -> deep-path import "
                f"'{imp['module']}'; 依赖平台非扁平命名空间，升版脆弱."
            )
    return errors


# ─────────────────────────── main ───────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Stratum 3O 消费方合规审计")
    ap.add_argument("--root", default=".", help="stratum 仓库根")
    ap.add_argument("--platform", default="/data/soffy/projects/platform/3O",
                    help="3O 平台 dev 副本（/platform/3O）")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    platform = Path(args.platform).resolve()
    if not root.is_dir() or not platform.is_dir():
        print(f"❌ root 或 platform 目录无效: {root} / {platform}")
        return 2

    print(f"🔍 Stratum 3O 消费方审计")
    print(f"   root: {root}")
    print(f"   platform: {platform}\n")

    imports = collect_stratum_imports(root)
    by_layer: dict[str, int] = {}
    files_with_3o = {str(imp["file"]) for imp in imports}
    for imp in imports:
        by_layer[imp["module"].split(".")[0]] = by_layer.get(imp["module"].split(".")[0], 0) + 1

    print("A. 3O 消费面统计")
    print(f"   涉 3O 的 stratum 文件数: {len(files_with_3o)}")
    for layer in LAYERS:
        print(f"   {layer}: {by_layer.get(layer, 0)} 处导入")

    print("\nB. async 契约交叉核对（stratum 调用点 vs /platform 真实签名）")
    errors = check_call_sites(root, imports, platform)
    if errors:
        for e in errors:
            print(f"   ❌ {e}")
    else:
        print("   ✅ 未发现 async 契约破坏")

    print("\nC. 导入卫生")
    hygiene = scan_import_hygiene(imports, root)
    if hygiene:
        for e in hygiene:
            print(f"   ⚠️ {e}")
    else:
        print("   ✅ 干净")

    print(f"\n合计: B={len(errors)} 契约问题, C={len(hygiene)} 卫生提醒")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
