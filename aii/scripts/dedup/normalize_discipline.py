"""B仓 refined_concept.discipline 清洗(只改标签, 不改概念同一性)。

问题: M0 早期把 substrate_id / 中文书名 / 哈希后缀写进 discipline,
导致 microecon_v2 / econ_zh_* / 经济学 与 economics 并存, 无法按域统计。

规则(保守, 可重放):
  1. 只 remap 已知脏标签 → 规范域(economics|math|physics|misc|unknown)
  2. 不合并概念、不删行、不改 name
  3. 默认 dry-run; --apply 才 UPDATE
  4. 每条 UPDATE 记 decision_ledger(decision_type=discipline_normalize)

用法:
  uv run python scripts/dedup/normalize_discipline.py
  uv run python scripts/dedup/normalize_discipline.py --apply
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / "aii" / ".env", override=True)

import asyncpg  # noqa: E402

REFINED_URL = os.getenv("REFINED_URL", "postgresql://aii:aii_safe_pass@localhost:5436/aii_refined")
APPLY = "--apply" in sys.argv

# 脏 → 规范(按匹配优先级)
_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(econ|mankiw|micro|经济|principles_econ)", re.I), "economics"),
    (re.compile(r"(math|advmath|algebra|calculus|topology|analysis|数分|高数|微积分)", re.I), "math"),
    (re.compile(r"(phys|物理)", re.I), "physics"),
    (re.compile(r"(misc|paper|哲学|心理|科普)", re.I), "misc"),
]
_CANON = {"economics", "math", "physics", "misc", "unknown", "law", "economics/law"}


def normalize(raw: str | None) -> str:
    if not raw or not str(raw).strip():
        return "unknown"
    s = str(raw).strip()
    if s in _CANON:
        return s
    if s == "economics/law":
        return "economics/law"
    for pat, canon in _RULES:
        if pat.search(s):
            return canon
    return "unknown"


async def main():
    conn = await asyncpg.connect(REFINED_URL)
    rows = await conn.fetch("SELECT concept_id, name, discipline FROM rf.refined_concept")
    changes = []
    dist_before = Counter((r["discipline"] or "") for r in rows)
    for r in rows:
        new = normalize(r["discipline"])
        old = r["discipline"] or ""
        if new != old:
            changes.append((r["concept_id"], r["name"], old, new))
    dist_after = Counter(dist_before)
    for _, _, old, new in changes:
        dist_after[old] -= 1
        if dist_after[old] <= 0:
            del dist_after[old]
        dist_after[new] += 1

    print(f"[{'APPLY' if APPLY else 'DRY-RUN'}] concepts={len(rows)} dirty→remap={len(changes)}")
    print("before:", dict(dist_before.most_common(20)))
    print("after :", dict(dist_after.most_common(20)))
    for cid, name, old, new in changes[:15]:
        print(f"  · #{cid} {(name or '')[:40]!r}: {old!r} → {new!r}")
    if len(changes) > 15:
        print(f"  ... +{len(changes) - 15} more")

    if APPLY and changes:
        async with conn.transaction():
            for cid, name, old, new in changes:
                await conn.execute(
                    "UPDATE rf.refined_concept SET discipline=$2, updated_at=now() WHERE concept_id=$1",
                    cid,
                    new,
                )
            # append-only 台账(schema: inputs/verdict 非 payload)
            await conn.execute(
                """
                INSERT INTO rf.decision_ledger(decision_type, inputs, verdict, actor, created_at)
                VALUES (
                  'discipline_normalize',
                  $1::jsonb,
                  $2::jsonb,
                  'script',
                  now()
                )
                """,
                json.dumps({"n_before": len(rows)}, ensure_ascii=False),
                json.dumps(
                    {
                        "n": len(changes),
                        "sample": [
                            {"concept_id": c, "old": o, "new": n} for c, _, o, n in changes[:50]
                        ],
                    },
                    ensure_ascii=False,
                ),
            )
        print(f"✓ updated {len(changes)} concepts + ledger")
    elif not APPLY:
        print("DRY-RUN: 加 --apply 才写库")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
