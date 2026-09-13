#!/usr/bin/env python3
"""CI guard: forbid new product-semantic `Stratum` naming.

Allowed:
- src/stratum/ path (internal code shell, kept for risk)
- stratum-sl container name / legacy allowlist entries
- docs/history/ content
- this script itself

Forbidden (product/architecture naming):
- "Stratum Knowledge ...", "Stratum Agent ...", "Stratum Layer ..."
- Any new file introducing Stratum as product title/branding

Usage:
  python scripts/check_aii_naming.py            # check staged + working tree diff
  python scripts/check_aii_naming.py --all      # scan entire repo source
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Legacy allowlist: exact substrings that are allowed to contain "stratum"
ALLOWLIST_SUBSTRINGS = [
    "src/stratum",
    "stratum-sl",
    "stratum-api",
    "stratum-web",
    "stratum_",
    "STRATUM_",
    ".stratum",
    "docs/history",
    "check_aii_naming.py",
    "AII_ARCHITECTURE_CONTRACT",
    "KNOWLEDGE_MODEL.md",  # contains migration notes, allowed
    "CURRENT_STATE.md",
    "CHANGELOG.md",
]

# Product-semantic pattern: Stratum + Knowledge/Agent/Layer/Runtime as product name
FORBIDDEN_RE = re.compile(r"Stratum\s+(Knowledge|Agent|Layer|Runtime|Retrieval|Learning)", re.IGNORECASE)


def _is_allowed(path: str, line: str) -> bool:
    for allow in ALLOWLIST_SUBSTRINGS:
        if allow in path or allow in line:
            return True
    return False


def _get_files_to_check(all_files: bool) -> list[str]:
    if all_files:
        # Scan source files only (avoid .git, node_modules, .venv)
        exts = {".py", ".ts", ".tsx", ".md", ".json", ".yml", ".yaml"}
        files: list[str] = []
        for p in ROOT.rglob("*"):
            if p.is_file() and p.suffix in exts:
                rel = str(p.relative_to(ROOT))
                if any(x in rel for x in (".git/", "node_modules/", ".venv/", ".next/", ".stratum/")):
                    continue
                files.append(rel)
        return files
    # Default: check git diff (staged + unstaged) vs HEAD
    try:
        out = subprocess.check_output(
            ["git", "-C", str(ROOT), "diff", "--name-only", "HEAD"],
            text=True,
        )
        return [x.strip() for x in out.splitlines() if x.strip()]
    except subprocess.CalledProcessError:
        return []


def main() -> int:
    all_files = "--all" in sys.argv
    files = _get_files_to_check(all_files)
    violations: list[str] = []

    for rel in files:
        path = ROOT / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if FORBIDDEN_RE.search(line):
                if _is_allowed(rel, line):
                    continue
                violations.append(f"{rel}:{i}: {line.strip()[:200]}")

    if violations:
        print("AII naming guard FAILED — new Stratum product naming detected:\n")
        for v in violations:
            print(f"  {v}")
        print("\nAllowed: src/stratum/ path, stratum-sl container, docs/history/")
        print("Forbidden: Stratum Knowledge/Agent/Layer/Runtime as product title.")
        print("Fix: use AII / AII Knowledge Runtime / AII Knowledge Store / AII Retrieval / AII Learning.")
        return 1

    print("AII naming guard PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
