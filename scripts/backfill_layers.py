#!/usr/bin/env python3
"""backfill_layers.py — 批量为已有 substrate 生成 L0/L1 摘要.

用法:
    python scripts/backfill_layers.py [--limit N] [--dry-run]

功能:
    1. 查找没有 L0 层的 substrate
    2. 读取 substrate 的 MD 导出文件 (exported_at 标记)
    3. 调用 layer_generator 生成 L0/L1
    4. 构建目录树
"""

import argparse
import logging
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("backfill_layers")


def main():
    parser = argparse.ArgumentParser(description="Backfill L0/L1 layers for substrates")
    parser.add_argument("--limit", type=int, default=50, help="Max substrates to process")
    parser.add_argument("--dry-run", action="store_true", help="Only show what would be processed")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between LLM calls (seconds)")
    args = parser.parse_args()

    from stratum.db import get_conn
    from stratum.services.layer_generator import (
        generate_substrate_layers,
        get_substrates_without_layers,
    )
    from stratum.services.directory_builder import build_initial_tree

    # Get substrates without layers
    pending_ids = get_substrates_without_layers()
    log.info("Found %d substrates without L0 layer", len(pending_ids))

    if not pending_ids:
        log.info("Nothing to do!")
        return

    if args.dry_run:
        for sid in pending_ids[:args.limit]:
            with get_conn() as conn:
                row = conn.execute(
                    "SELECT title, source_path FROM substrates WHERE id = ?", (sid,)
                ).fetchone()
            if row:
                log.info("  [dry-run] %s: %s (%s)", sid[:12], row[0], row[1] or "no path")
        return

    processed = 0
    failed = 0

    for sid in pending_ids[:args.limit]:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT title, source_path FROM substrates WHERE id = ?", (sid,)
            ).fetchone()

        if not row:
            log.warning("Substrate %s not found, skipping", sid)
            continue

        title, source_path = row[0], row[1]

        # Try to read content
        content = None
        if source_path:
            p = Path(source_path)
            if p.exists():
                try:
                    content = p.read_text(encoding="utf-8", errors="replace")[:10000]
                except Exception:
                    pass

        if not content and not title:
            log.warning("No content or title for %s, skipping", sid)
            failed += 1
            continue

        try:
            layers = generate_substrate_layers(sid, title=title, content=content)
            l0_len = len(layers.get("L0", ""))
            l1_len = len(layers.get("L1", ""))
            log.info("[%d/%d] %s: L0=%d chars, L1=%d chars",
                     processed + 1, min(args.limit, len(pending_ids)),
                     title[:50], l0_len, l1_len)
            processed += 1
        except Exception as exc:
            log.error("Failed to generate layers for %s: %s", sid, exc)
            failed += 1

        time.sleep(args.delay)

    log.info("Done: %d processed, %d failed", processed, failed)

    # Build directory tree
    log.info("Building directory tree...")
    counts = build_initial_tree()
    log.info("Directory tree: %s", counts)


if __name__ == "__main__":
    main()
