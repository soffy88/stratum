#!/usr/bin/env python3
"""炼狱书诊断 — 只读, 把"KU 1-100 卡在中间地带"的书量化 surface 出来。

背景(实证): discover 排除只认 ku_count>100(econ/misc/advmath)/ >30(math)。低于阈值
的书若 state.json 里又没终态标记, 就每轮被重新发现、重新处理——既浪费又可能产生重复 KU。
recon 实测: ingested_substrate 里 ku 1-100 有 86 本, 其中 74 本是 ULID 方案(不在
econ/misc/advmath 的 re-discover 命名空间内, 不会被它们重捡), 真正的"md5方案炼狱"是少数
misc_/econ_ 且 state 无终态的。

本工具只读: 列出这些书 + 判定它们是"真炼狱(会被重捡)"还是"已被终态排除(无害)"。不自动
改 state.json——因为重跑一本 26 KU 的书是"补齐到阈值"还是"产生重复"取决于管道幂等性, 这
个语义未验证前, 冻结哪本书该由人/看门狗按此报告决定, 不由脚本擅自决断。

用法: python scripts/purgatory_triage.py [--json out.json]
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from book_identity import TERMINAL_KU_THRESHOLD, TERMINAL_STATUSES  # noqa: E402

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / "aii" / ".env", override=True)

# 各飞轮 state.json + 它们负责的 substrate 前缀(判定某本书归哪个 discover 命名空间)。
STATES = [
    (ROOT / "econ_pipeline/flywheel_zh_state.json", ("econ_zh_", "econ_en_")),
    (ROOT / "misc_pipeline/flywheel_misc_state.json", ("misc_zh_", "misc_en_")),
    (ROOT / "advmath_pipeline/flywheel_state.json", ("advmath_zh_", "advmath_en_")),
    (ROOT / "math_pipeline/flywheel_state.json", ("math_prog_",)),
]


def _load_state(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("processed", {})
    except Exception:
        return {}


async def _low_ku_books() -> list[dict]:
    import asyncpg

    conn = await asyncpg.connect(os.getenv("DATABASE_URL"), timeout=15)
    try:
        rows = await conn.fetch(
            "SELECT substrate_id, title, ku_count FROM aii.ingested_substrate "
            "WHERE ku_count BETWEEN 1 AND $1 ORDER BY ku_count",
            TERMINAL_KU_THRESHOLD - 1,
        )
    finally:
        await conn.close()
    return [{"sid": r["substrate_id"], "title": r["title"], "ku": r["ku_count"]} for r in rows]


def _namespace(sid: str) -> tuple[Path, dict] | None:
    for state_path, prefixes in STATES:
        if any(sid.startswith(p) for p in prefixes):
            return state_path, _load_state(state_path)
    return None


async def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    books = await _low_ku_books()
    genuine_purgatory, terminal_ok, out_of_namespace = [], [], []
    for b in books:
        ns = _namespace(b["sid"])
        if ns is None:
            out_of_namespace.append(b)  # ULID/legacy 方案, 不被 md5 discover 重捡
            continue
        _, processed = ns
        st = processed.get(b["sid"], {})
        status = st.get("status") if isinstance(st, dict) else None
        if status in TERMINAL_STATUSES:
            terminal_ok.append({**b, "status": status})
        else:
            genuine_purgatory.append({**b, "status": status or "(无state记录)"})

    print(f"=== 炼狱诊断 (ku 1-{TERMINAL_KU_THRESHOLD - 1}, 共 {len(books)} 本) ===")
    print(f"🔴 真炼狱(md5命名空间 + 无终态 → 每轮被重捡重处理): {len(genuine_purgatory)}")
    for b in genuine_purgatory:
        print(f"   ku={b['ku']:<3} {b['sid']:<22} {str(b['title'])[:40]}  [state={b['status']}]")
    print(f"🟢 已终态排除(无害): {len(terminal_ok)}")
    print(f"⚪ 命名空间外(ULID/legacy, md5 discover 不会重捡): {len(out_of_namespace)}")
    print()
    print(
        "建议: 🔴 这批需人/看门狗决断 —— 若管道非幂等(重跑会加重复KU), 应在对应 state.json 里"
        "给它们标终态(quarantine + 原因)止损; 若幂等且只是没到阈值, 可留着让它继续补。"
    )

    summary = {
        "threshold": TERMINAL_KU_THRESHOLD,
        "total_low_ku": len(books),
        "genuine_purgatory": genuine_purgatory,
        "terminal_ok_count": len(terminal_ok),
        "out_of_namespace_count": len(out_of_namespace),
    }
    if args.json:
        Path(args.json).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n摘要 → {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
