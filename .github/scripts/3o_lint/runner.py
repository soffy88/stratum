#!/usr/bin/env python3
"""3O Paradigm SPEC v3.0 - Unified CI Lint Runner.

用法:
    python runner.py [ROOT_DIR] [--baseline PATH]
    ROOT_DIR 默认取本仓库根（脚本位于 .github/scripts/3o_lint/ 时自动上溯 3 级）。
    对 stratum 而言：层目录（oprim/oskill/omodul/oservi/obase）不在本仓库内，
    这些检查将全部 N/A；层代码实际位于 /platform（部署到镜像 /opt/platform）。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from check_async_contract import check_async_contract
from check_enabled_pillars import check_enabled_pillars
from check_flat_namespace import check_flat_namespace
from check_obase_no_reverse_dep import check_obase_no_reverse_dep
from check_omodul_signature import check_omodul_signature
from check_oprim_keyword_only import check_oprim_keyword_only
from check_oservi_injection import check_oservi_injection
from check_no_project_prefix import check_no_project_prefix
from check_no_sibling_call import check_no_sibling_call


def main() -> int:
    parser = argparse.ArgumentParser(description="3O Paradigm SPEC v3.0 CI Lint Runner")
    parser.add_argument("root", nargs="?", default=None,
                        help="仓库根目录（含层目录）；默认自动定位")
    parser.add_argument("--baseline", default=None,
                        help="async 契约 baseline JSON（用于 MAJOR 变更比对）")
    args = parser.parse_args()

    if args.root:
        root_dir = Path(args.root).resolve()
    else:
        # 脚本位于 <root>/.github/scripts/3o_lint/runner.py → 上溯 3 级
        root_dir = Path(__file__).resolve().parents[3]
    baseline_file = Path(args.baseline).resolve() if args.baseline else None

    print(f"🔍 Executing 3O Paradigm SPEC v3.0 Comprehensive CI Lint...")
    print(f"   root: {root_dir}\n")

    # 执行 9 大检查
    errors: list[str] = []
    errors.extend(check_flat_namespace(root_dir))
    errors.extend(check_no_project_prefix(root_dir))
    errors.extend(check_no_sibling_call(root_dir))
    errors.extend(check_oprim_keyword_only(root_dir / "oprim"))
    errors.extend(check_omodul_signature(root_dir / "omodul"))
    errors.extend(check_enabled_pillars(root_dir / "omodul"))
    errors.extend(check_obase_no_reverse_dep(root_dir / "obase"))
    errors.extend(check_oservi_injection(root_dir / "oservi"))
    errors.extend(check_async_contract(root_dir, baseline_file))

    if errors:
        print(f"\n❌ Found {len(errors)} 3O Paradigm Violations:\n")
        for idx, err in enumerate(errors, 1):
            print(f"  {idx}. {err}")
        print("\n💥 CI Check Failed! Align your code with SPEC v3.0 before merging.")
        return 1

    print("✅ All 9 3O Paradigm Compliance Checks Passed Successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
