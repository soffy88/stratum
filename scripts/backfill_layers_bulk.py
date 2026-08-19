#!/usr/bin/env python3
"""backfill_layers_bulk.py — 高效批量为所有 substrate 生成 L0/L1 + embeddings.

策略:
  - 有 MD/TXT 源文件: 读取内容 → LLM 生成 L0/L1
  - 仅 PDF (无文本): 标题作为 L0, 跳过 LLM (快速路径)
  - 每批处理后计算 embedding
"""

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("backfill_bulk")

_BATCH_SIZE = 200


def main():
    from stratum.db import get_conn
    from stratum.services.layer_generator import (
        generate_substrate_layers,
        _persist_substrate_layers,
        _get_embedding,
    )

    # Get ALL substrates without L0 layers
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT s.id, s.title, s.source_path, s.mime
               FROM substrates s
               LEFT JOIN substrate_layers sl ON s.id = sl.substrate_id AND sl.layer = 'L0'
               WHERE sl.id IS NULL
               ORDER BY s.created_at DESC"""
        ).fetchall()

    log.info("Substrates without L0: %d", len(rows))
    if not rows:
        log.info("Nothing to do!")
        return

    processed = 0
    failed = 0
    llm_calls = 0
    t0 = time.time()

    for sid, title, source_path, mime in rows:
        title = title or "Untitled"
        content = None

        # Try to read text content for non-PDF files
        if source_path and mime and "pdf" not in mime.lower():
            p = Path(source_path)
            if p.exists():
                try:
                    content = p.read_text(encoding="utf-8", errors="replace")[:8000]
                except Exception:
                    pass

        try:
            if content and len(content) > 500:
                # Full LLM path: generate L0/L1 from content
                layers = generate_substrate_layers(sid, title=title, content=content)
                llm_calls += 1
            else:
                # Fast path: use title as L0, title+ as L1 (no LLM call)
                l0 = title[:200]
                l1 = f"# {title}\n\n{title}"  # Minimal L1
                layers = {"L0": l0, "L1": l1, "L2": content or title}
                _persist_substrate_layers(sid, layers)

            processed += 1
            if processed % 50 == 0:
                elapsed = time.time() - t0
                rate = processed / elapsed if elapsed > 0 else 0
                log.info("[%d/%d] %.1f/sec | LLM calls: %d | %s",
                         processed, len(rows), rate, llm_calls, title[:50])

        except Exception as exc:
            log.error("Failed: %s — %s", sid[:12], exc)
            failed += 1

    elapsed = time.time() - t0
    log.info("Layers done: %d processed, %d failed, %d LLM calls in %.0fs",
             processed, failed, llm_calls, elapsed)

    # Now backfill embeddings for all L0 without them
    log.info("Backfilling embeddings...")
    emb_count = 0
    while True:
        from stratum.services.layer_generator import backfill_embeddings
        n = backfill_embeddings(batch_size=100)
        if n == 0:
            break
        emb_count += n
        log.info("Embeddings batch: %d done so far", emb_count)

    log.info("Total: %d layers, %d embeddings, %d failed", processed, emb_count, failed)


if __name__ == "__main__":
    main()
