#!/usr/bin/env python3
"""★OpenKB 内化 — 批量文档 → wiki 编译 + Skill Factory。

把 books/MD 文档池喂给内化 OpenKB(仓库 services/openkb_svc) → 编译 wiki →
对有价值主题产出 SKILL.md 进 ~/.agents/skills/(3O/pi 技能体系)。

用法: .venv/bin/python scripts/wiki_batch.py [--limit N] [--kb /data/.../wiki_kb]
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KB = Path("/data/soffy/projects/stratum/wiki_kb")
OPENKB = "/tmp/openkb-env/bin/openkb"
SKILLS = Path.home() / ".agents" / "skills"

# 文档源池(优先教材/论文/教辅)
POOLS = [
    ("英文数学", "/home/soffy/books/MD/英文数学"),
    ("经济学", "/home/soffy/books/MD/经济学"),
    ("教辅", "/home/soffy/books/MD/教辅"),
    ("其它", "/home/soffy/books/MD/其它"),
]


def _pick(limit: int) -> list[tuple[str, Path]]:
    out = []
    for label, d in POOLS:
        mds = sorted(Path(d).glob("*.md"))
        for md in mds[: max(2, limit // 4 + 1)]:
            out.append((label, md))
        if len(out) >= limit:
            break
    return out[:limit]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=6)
    ap.add_argument("--skill", action="store_true", help="编译后产 skill")
    args = ap.parse_args()

    picks = _pick(args.limit)
    print(f"选 {len(picks)} 本文档: {[p[0] for p in picks]}")

    for i, (label, md) in enumerate(picks):
        dest = KB / "raw" / f"{i:02d}_{label}_{md.stem[:40]}.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(md, dest)
        r = subprocess.run([OPENKB, "add", str(dest)], cwd=KB,
                           capture_output=True, text=True, timeout=1500)
        tail = [l for l in (r.stdout or "").splitlines() if "OK" in l or "ERROR" in l][-2:]
        print(f"  [{label}] {md.stem[:35]} → {' | '.join(tail)[:90] or 'done'}")

    if args.skill:
        print("\n[skill] 从 wiki 产 skill...")
        topics = ["mathematics", "economics", "education", "science"]
        for t in topics:
            r = subprocess.run([OPENKB, "skill", "new", f"wiki-{t}", f"Reason like an expert on {t}"],
                               cwd=KB, capture_output=True, text=True, timeout=900)
            out = (r.stdout or "") + (r.stderr or "")
            if "output/skills" in out:
                # 拷贝进 ~/.agents/skills/
                src = KB / "output" / "skills" / f"wiki-{t}"
                if src.exists():
                    shutil.copytree(src, SKILLS / f"wiki-{t}", dirs_exist_ok=True)
                    print(f"  📦 {t} → ~/.agents/skills/wiki-{t}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
