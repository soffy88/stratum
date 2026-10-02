"""把整本被质量门隔离的书的 KU 在库里封存(is_quarantined=true).

★为什么需要(2026-09-29 发现): 质量门报警后, 飞轮只把书写进 quarantine.json
并更新 flywheel state —— 数据库侧只做了【逐章独立提交】(见 onto_persist.py:245
每章一个 `async with conn.transaction()`), 所以隔离发生时, 这本书已经写进去的
KU 全部留在 aii.ku_onto 里, is_quarantined 仍是 false。

实测: 89 本隔离书, 89 本在库内留有 KU, 合计 5618 条。这些 KU 对读者/检索/
下游(S13 统计)是可见的 —— "已隔离" 只停留在一个 JSON 文件里, 没有落到数据层。

本脚本把该状态对齐到数据库: 隔离 = 不可见 + 可逆, 不做物理删除
(与 quarantine_corrupted_ku.py 的取舍一致: is_quarantined 可逆, DELETE 不可逆)。

隔离是【幂等】的: 重复执行不会重复写 state_history, 也不影响非隔离书。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_STAGE = 1


def _collect_ids(quarantine_files: list[Path], only: set[str] | None) -> list[str]:
    ids: list[str] = []
    for path in quarantine_files:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print(f"  ! 跳过 {path}: {e}")
            continue
        items = data.get("quarantined", []) if isinstance(data, dict) else data
        for it in items or []:
            sid = (it or {}).get("substrate_id", "").strip()
            if sid and (not only or sid in only):
                ids.append(sid)
    return sorted(set(ids))


SQL_STATS = """
SELECT
    count(*)                                             AS total,
    count(*) FILTER (WHERE NOT is_quarantined)           AS visible
FROM aii.ku_onto
WHERE substrate_id = $1
"""

SQL_HIDE = """
UPDATE aii.ku_onto
   SET is_quarantined = TRUE,
       updated_at     = CURRENT_TIMESTAMP
 WHERE substrate_id = $1
   AND NOT is_quarantined
RETURNING ku_id
"""


async def _run(conn, sids: list[str], reason_of: dict[str, str], dry_run: bool) -> None:
    grand_hide = 0
    grand_skip = 0
    for sid in sids:
        row = await conn.fetchrow(SQL_STATS, sid)
        if not row or row["total"] == 0:
            continue
        if row["visible"] == 0:
            grand_skip += 1
            continue
        if dry_run:
            print(f"  [dry] {sid}: {row['visible']} 条将封存(总 {row['total']})")
            grand_hide += row["visible"]
            continue
        hidden = [r["ku_id"] for r in await conn.fetch(SQL_HIDE, sid)]
        reason = reason_of.get(sid, "quality_gate")
        # 逐条记 state_history, 让封存可追溯(与 pg_backend.quarantine_ku 同口径)
        for ku_id in hidden:
            await conn.execute(
                """
                INSERT INTO aii.ku_state_history
                    (ku_id, from_grade, to_grade, trigger, decision_trail)
                SELECT ku_id, grade, grade, 'book_quality_gate', $2::jsonb
                  FROM aii.ku_onto WHERE ku_id = $1
                """,
                ku_id,
                json.dumps({"substrate_id": sid, "reason": reason}, ensure_ascii=False),
            )
        grand_hide += len(hidden)
        print(f"  封存 {sid}: {len(hidden)}/{row['total']} 条")

    verb = "将封存" if dry_run else "已封存"
    print(f"  合计{verb} {grand_hide} 条, {grand_skip} 本本就已封存(幂等跳过)")


def main() -> int:
    ap = argparse.ArgumentParser(description="把整本隔离书的 KU 在库内封存")
    ap.add_argument(
        "-q",
        "--quarantine",
        action="append",
        type=Path,
        help="quarantine.json 路径, 可重复; 默认扫各飞轮目录下同名文件",
    )
    ap.add_argument("--substrate-id", action="append", help="只处理指定书, 可重复")
    ap.add_argument("--dry-run", action="store_true", help="只报告不写库")
    args = ap.parse_args()

    files = args.quarantine or sorted(Path(".").glob("*_pipeline/quarantine.json"))
    if not files:
        print("  未找到 quarantine.json")
        return 1
    print(f"  扫描 {len(files)} 个 quarantine 文件")

    reason_of: dict[str, str] = {}
    for path in files:
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data.get("quarantined", []) if isinstance(data, dict) else data
        for it in items or []:
            if (sid := (it or {}).get("substrate_id", "").strip()):
                reason_of.setdefault(sid, (it or {}).get("reason_detail", "quality_gate")[:200])

    sids = _collect_ids(files, set(args.substrate_id) if args.substrate_id else None)
    print(f"  隔离书 {len(sids)} 本, 生效于 {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC")

    async def _main() -> None:
        import asyncpg

        # 宿主映射端口是 5437(容器内才是 5432), 与 .env POSTGRES_* 同一份凭据
        conn = await asyncpg.connect(
            host="localhost",
            port=int(os.getenv("AII_PG_PORT", "5437")),
            user=os.getenv("POSTGRES_USER", "aii"),
            password=os.environ.get("POSTGRES_PASSWORD", ""),
            database=os.getenv("POSTGRES_DB", "aii_kg"),
        )
        try:
            await _run(conn, sids, reason_of, args.dry_run)
        finally:
            await conn.close()

    asyncio.run(_main())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
