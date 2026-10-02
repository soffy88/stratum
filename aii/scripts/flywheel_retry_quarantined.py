"""飞轮重试: 将因双语率/KU密度/rationale隔离的书从 quarantine 状态释放,
重新加入飞轮队列.

背景(2026-07-30): 四个飞轮累计 414 本书全部被隔离(0 本通过), 主因:
  1. 双语率 0% — 已修: 英文书不再检查双语率(A仓命门是抽全不漏, 翻译是下游的事)
  2. KU 密度不足 — 阈值过高(已修: 60%→35%, 15/章→10/章)
  3. rationale=0 — prompt 不够强(已修: PLAN_SYS 强化)
本脚本识别"可重试"的隔离书(隔离原因已被修复), 清除其在飞轮状态中的
终态标记, 并清理 DB 中对应的残留 KU/概念/KC/BU(重跑时需要干净起点).

不可重试的隔离原因(上游问题, 重试仍会失败):
  - precheck_fail: MD 文件结构损坏(需上游 PDF→MD 转换修复)
  - 双语率0% + KU密度0 + 无章节: MD 内容本身有问题
  - 管道步骤失败: 程序 bug(需先修代码)

Usage:
  python3 scripts/flywheel_retry_quarantined.py --pipeline econ   # 经济学中文
  python3 scripts/flywheel_retry_quarantined.py --pipeline advmath # 高级数学经济
  python3 scripts/flywheel_retry_quarantined.py --pipeline misc   # 其它学科
  python3 scripts/flywheel_retry_quarantined.py --pipeline all    # 全部
  python3 scripts/flywheel_retry_quarantined.py --pipeline econ --dry-run  # 只看不动
"""

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import hashlib
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── 管道配置 ──
PIPELINE_CONFIGS = {
    "econ": {
        "state_file": "econ_pipeline/flywheel_zh_state.json",
        "quarantine_file": "econ_pipeline/quarantine.json",
    },
    "advmath": {
        "state_file": "advmath_pipeline/flywheel_state.json",
        "quarantine_file": "advmath_pipeline/quarantine.json",
    },
    "misc": {
        "state_file": "misc_pipeline/flywheel_misc_state.json",
        "quarantine_file": "misc_pipeline/quarantine.json",
    },
    "cs": {
        "state_file": "cs_pipeline/flywheel_cs_state.json",
        "quarantine_file": "cs_pipeline/quarantine.json",
    },
    "edu": {
        "state_file": "edu_pipeline/flywheel_edu_state.json",
        "quarantine_file": "edu_pipeline/quarantine.json",
    },
}

SOURCE_DIRS = {
    "econ": Path("/home/soffy/books/MD/经济学"),
    "cs": Path("/home/soffy/books/MD/计算机"),
    "misc": Path("/home/soffy/books/MD/其它"),
    "edu": Path("/home/soffy/books/MD/教辅"),
}


def resolve_source_path(pipeline_name: str, substrate_id: str, recorded: str) -> Path:
    """Resolve stale quarantine paths against the current classified MD pool."""
    path = Path(recorded) if recorded else Path()
    if path.is_file():
        return path
    suffix = substrate_id.rsplit("_", 1)[-1]
    source_dir = SOURCE_DIRS.get(pipeline_name)
    if source_dir and source_dir.is_dir():
        for candidate in source_dir.glob("*.md"):
            if hashlib.md5(candidate.stem.encode("utf-8")).hexdigest()[:10] == suffix:
                return candidate
    return path

# ── 可重试的隔离原因关键词 ──
RETRYABLE_PATTERNS = [
    r"双语率\d+%<",  # bilingual rate too low → now fixed by translation step
    r"KU密度不足: 实抽\d+",  # KU密度太低(但抽到了一些KU, 可重试) → relaxed thresholds
    r"rationale\(why\)=0",  # no rationale extracted → now fixed by stronger prompt
    r"低密度章过多",  # too many low-density chapters → now fixed by lower floor
    r"完整率",  # 完整率不足(含0%: 章节regex可能未命中, 但书有KU就值得重试; 0KU+0%会被下面非重试"实抽0仅0%"捕获)
    r"管道超过 \d+ 分钟未完成",  # 旧LLM/网关超时；切换网关或修复后可恢复
]

# ── 不可重试的隔离原因 ──
NON_RETRYABLE_PATTERNS = [
    r"precheck_fail",  # MD structure broken
    r"FAIL:chapter",  # chapter structure issues
    r"FAIL:running_header",  # OCR noise
    r"管道步骤失败",  # pipeline error (code bug)
    r"源MD文件严重重复",  # source file corrupted
    r"章号重复",  # chapter duplication
    r"章号非连续",  # chapter gap
    # 完整率0% 不再列入非重试: 可能只是章节regex未命中, 但书有KU(有内容) → 可重试
    r"实抽0仅0%",  # 0 KU extracted = synthesis failed entirely
]


def is_retryable(reason: str) -> bool:
    """Check if a quarantine reason matches a retryable pattern."""
    # If any non-retryable pattern matches, skip
    for pat in NON_RETRYABLE_PATTERNS:
        if re.search(pat, reason):
            return False
    # If any retryable pattern matches, it's retryable
    for pat in RETRYABLE_PATTERNS:
        if re.search(pat, reason):
            return True
    return False


def source_precheck_passes(item: dict, pipeline_name: str = "") -> bool:
    """隔离后源 MD 被重新转换过时，允许基于当前结构重新入队。

    旧状态里的“实抽 0 KU/0 章”可能发生在上游转换器修复之前；只看旧 reason
    会把已经修好的书永久锁死。这里必须同时满足 MD 存在且当前 R1-R9 预检通过，
    避免把真正损坏或只有扫描页的源文件盲目重跑。
    """
    md_path = str(item.get("md_path", "")).strip()
    if not md_path:
        return False
    path = resolve_source_path(pipeline_name, str(item.get("substrate_id", "")), md_path)
    if not path.exists() or path.suffix.lower() != ".md":
        return False
    title = str(item.get("title", path.stem))
    checker = Path(__file__).resolve().parent / "misc_precheck.py"
    try:
        result = subprocess.run(
            [sys.executable, str(checker), str(path), title],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and result.stdout.strip().startswith("PASS")


def process_pipeline(pipeline_name: str, dry_run: bool, only_substrate: str | None = None):
    """Process a single pipeline's quarantine list."""
    config = PIPELINE_CONFIGS[pipeline_name]
    state_path = Path(config["state_file"])
    quarantine_path = Path(config["quarantine_file"])

    if not state_path.exists():
        print(f"  [{pipeline_name}] 状态文件不存在: {state_path}")
        return []

    state = json.loads(state_path.read_text(encoding="utf-8"))
    processed = state.get("processed", {})

    qmap = {}
    if quarantine_path.exists():
        try:
            qmap = {
                item.get("substrate_id", ""): item
                for item in json.loads(quarantine_path.read_text(encoding="utf-8")).get(
                    "quarantined", []
                )
            }
        except (OSError, json.JSONDecodeError):
            qmap = {}

    # Find retryable entries
    retryable = {}
    skipped_non_retryable = 0
    for sid, info in processed.items():
        if only_substrate and sid != only_substrate:
            continue
        status = info.get("status", "")
        reason = info.get("reason", "")
        qitem = qmap.get(sid, {})
        retryable_reason = is_retryable(reason)
        # 定向 substrate 重试是人工/运维明确指定的单本修复入口。旧版本在
        # worker 合并 quarantine.json 时可能丢掉条目，但状态文件仍保留隔离
        # 记录；此时不能因为 qitem 缺失而让这本 0-KU 书永久锁死。清理后仍
        # 由 discover + R1-R9 预检决定是否真正进入管道。
        directed_retry = bool(only_substrate and sid == only_substrate and not qitem)
        # 允许“旧质量门失败 + 当前源 MD 已修复且预检通过”的定向重试。
        # 只针对结构/密度型失败开放，不放行任意管道错误。
        repaired_source = (
            status in ("quarantine", "retry", "precheck_fail")
            and bool(re.search(r"实抽0仅0%|KU密度不足|完整率|管道步骤失败", reason))
            and not retryable_reason
            and source_precheck_passes(qitem, pipeline_name)
        )
        if status in ("quarantine", "retry") and (retryable_reason or repaired_source or directed_retry):
            retryable[sid] = info
        elif status == "precheck_fail" and repaired_source:
            retryable[sid] = info
        elif status in ("quarantine", "retry", "precheck_fail"):
            skipped_non_retryable += 1

    # 外层批处理先写 quarantine.json、稍后才合并回 state.json；在这个窗口内，
    # 定向 substrate 只存在于 quarantine 一侧。允许精确目标直接进入同一清理
    # 流程，避免质量门失败书因并发落盘顺序永久漏扫。
    if only_substrate and only_substrate not in retryable and only_substrate in qmap:
        qitem = qmap[only_substrate]
        qreason = str(qitem.get("reason_detail", ""))
        if is_retryable(qreason) or (
            re.search(r"实抽0仅0%|KU密度不足|完整率|管道步骤失败", qreason)
            and source_precheck_passes(qitem, pipeline_name)
        ):
            retryable[only_substrate] = {
                "status": "quarantine",
                "reason": qreason,
                "md_path": qitem.get("md_path", ""),
            }

    print(f"  [{pipeline_name}] 总计 {len(processed)} 条记录:")
    print(f"    可重试(双语/密度/rationale): {len(retryable)}")
    print(f"    不可重试(预检/管道/源文件): {skipped_non_retryable}")

    if not retryable:
        print("    无可重试项, 跳过")
        return []

    if dry_run:
        print(f"    [DRY RUN] 将重试以下 {len(retryable)} 本书:")
        for sid, info in list(retryable.items())[:10]:
            reason_short = info.get("reason", "")[:80]
            print(f"      {sid}: {reason_short}")
        if len(retryable) > 10:
            print(f"      ... 还有 {len(retryable) - 10} 本")
        return list(retryable)

    # Remove retryable entries from state
    for sid in retryable:
        processed.pop(sid, None)

    state["processed"] = processed
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"    ✅ 已从状态文件移除 {len(retryable)} 条(下次 discover 会重新发现)")

    # Also clean from quarantine.json
    if quarantine_path.exists():
        q = json.loads(quarantine_path.read_text(encoding="utf-8"))
        q_items = q.get("quarantined", [])
        retryable_sids = set(retryable.keys())
        q["quarantined"] = [
            item for item in q_items if item.get("substrate_id", "") not in retryable_sids
        ]
        quarantine_path.write_text(json.dumps(q, ensure_ascii=False, indent=2), encoding="utf-8")
        removed = len(q_items) - len(q["quarantined"])
        print(f"    ✅ 已从 quarantine.json 移除 {removed} 条")

    return list(retryable)


async def clean_db(
    retryable_sids: list[str], dry_run: bool, checkpoint_dir: Path | None = None
):
    """Clean residual KU/concept/KC/BU data from DB for retryable substrates."""
    if not retryable_sids:
        return

    import asyncpg

    db_url = os.getenv("DATABASE_URL", "postgresql://aii:***REMOVED***@localhost:5437/aii_kg")

    try:
        conn = await asyncpg.connect(db_url)
    except Exception as e:
        print(f"    ⚠ 无法连接数据库: {e}")
        return

    total_cleaned = 0
    for sid in retryable_sids:
        # Check if substrate has any KU data
        ku_count = await conn.fetchval(
            "SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1", sid
        )
        if dry_run:
            total_cleaned += ku_count
            continue

        # Delete in order: BU → KC → KU.  concept_onto is a global canonical
        # concept table and has no substrate_id column, so it must never be
        # included in this per-book cleanup.  Also remove the ingest
        # marker: all discover scripts use ingested_substrate as a hard stop,
        # so merely removing flywheel_state would otherwise never requeue it.
        for table in ["bu_onto", "kc_onto", "ku_onto"]:
            try:
                await conn.execute(f"DELETE FROM aii.{table} WHERE substrate_id=$1", sid)
            except Exception:
                pass  # table might not exist or have FK constraints

        try:
            await conn.execute("DELETE FROM aii.ingested_substrate WHERE substrate_id=$1", sid)
        except Exception:
            pass

        # 重试必须从干净章节集开始。旧 checkpoint 可能记录了上一轮“已处理”
        # 的章节，若只清 DB，重跑会出现 17/13 chapters done 但 0 KU 的假完成。
        if checkpoint_dir:
            ckpt = checkpoint_dir / f"ckpt_{sid}.json"
            try:
                ckpt.unlink(missing_ok=True)
                print(f"    ✅ 已清理 checkpoint: {ckpt}")
            except OSError as e:
                print(f"    ⚠ checkpoint 清理失败 {ckpt}: {e}")

        total_cleaned += ku_count

    action = "[DRY RUN] 将清理" if dry_run else "✅ 已清理"
    print(f"    {action} DB 中 {total_cleaned} 条残留 KU(跨 {len(retryable_sids)} 本书)")
    await conn.close()


async def main():
    parser = argparse.ArgumentParser(description="飞轮重试: 释放可重试的隔离书")
    parser.add_argument(
        "--pipeline", choices=["econ", "advmath", "misc", "cs", "edu", "all"], default="all"
    )
    parser.add_argument("--dry-run", action="store_true", help="只看不改")
    parser.add_argument("--substrate", default="", help="只处理指定 substrate，避免扫描整批隔离项")
    args = parser.parse_args()

    pipelines = list(PIPELINE_CONFIGS.keys()) if args.pipeline == "all" else [args.pipeline]

    print(f"{'[DRY RUN] ' if args.dry_run else ''}★ 飞轮重试扫描")
    print()

    for pipeline in pipelines:
        retryable_sids = process_pipeline(pipeline, args.dry_run, args.substrate or None)
        # 原脚本虽然定义了 clean_db，但此前没有调用，导致重试书的旧 KU/BU
        # 残留继续参与统计/查重；这里按飞轮分别清理 DB 和 checkpoint，防止
        # 清理一个飞轮时误碰另一飞轮同名/并行中的状态。
        checkpoint_dir = Path(PIPELINE_CONFIGS[pipeline]["state_file"]).parent / "ckpts"
        await clean_db(retryable_sids, args.dry_run, checkpoint_dir)

    if not args.dry_run:
        print()
        print("提示: 下次飞轮运行时, discover 脚本会重新发现这些书并加入队列.")
        print("      econ_flywheel_zh.sh / misc_flywheel.sh / advmath_flywheel.sh")
        print("      的 Step 0 (pull_ingest.sh) 会同步新书源.")


if __name__ == "__main__":
    asyncio.run(main())
