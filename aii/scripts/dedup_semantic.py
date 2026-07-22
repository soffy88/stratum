"""跨章/跨书语义去重(P2⑨): 向量近邻配对 → LLM 判 SAME → 报告/安全合并.

补 dedup_kus.py(只查同章标题)的盲区: 跨章(同书)、跨书的语义重复.
判定: LLM SAME/DIFFERENT(只关心是否同一断言).
动作分级(命门: 跨书"重复"常是不同书各自覆盖, 不可乱删):
  - 同书跨章 SAME → 可安全合并(--apply): 保留内容更长者, 另一条的边重指向, 删除.
  - 跨书 SAME → 仅报告(人工决定是否归并/建 same_as 边), 不自动删.

用法: python3 scripts/dedup_semantic.py [--sim 0.86] [--max 80] [--apply]

核心逻辑已搬进 aii.service.dedup_semantic (供 app.py 后台周期任务复用) — 本
脚本现在只是那个模块的 CLI 入口，逻辑不再重复维护两份。
"""

import asyncio, sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)

from aii.service.dedup_semantic import run_dedup_semantic


async def main():
    sim = float(sys.argv[sys.argv.index("--sim") + 1]) if "--sim" in sys.argv else 0.86
    mx = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 80
    apply = "--apply" in sys.argv

    summary = await run_dedup_semantic(sim=sim, max_pairs=mx, apply=apply)
    print(f"{summary['candidates']} candidate pairs (sim>={sim}, judged)")
    print(
        f"SAME={summary['same_verdicts']} "
        f"(同书跨章={summary['same_book_merged'] if apply else '?'} 可合并, "
        f"跨书={summary['cross_book_reported']} 仅报告)"
    )
    print(
        f"\nDONE: {summary['same_verdicts']} dups; merged {summary['same_book_merged']} same-book"
        + ("" if apply else " (dry-run)")
    )


if __name__ == "__main__":
    asyncio.run(main())
