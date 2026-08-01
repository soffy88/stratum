#!/usr/bin/env python3
"""backfill_layers_fast.py — 极速批量: 只用标题作 L0, 不调 LLM, 只算 embedding.

对所有缺少 L0 的 substrate:
  L0 = title[:200]
  L1 = title
  L2 = title
  embedding = computed from L0

预期速度: ~8/sec (仅 embedding 计算瓶颈)
"""

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("backfill_fast")


def main():
    from stratum.db import get_conn
    from stratum.services.layer_generator import (
        _persist_substrate_layers,
        _get_embedding,
    )

    with get_conn() as conn:
        rows = conn.execute(
            """SELECT s.id, s.title
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
    t0 = time.time()

    for sid, title in rows:
        title = title or "Untitled"
        try:
            l0 = title[:200]
            l1 = f"# {title}"
            layers = {"L0": l0, "L1": l1, "L2": title}
            _persist_substrate_layers(sid, layers)
            processed += 1

            if processed % 100 == 0:
                elapsed = time.time() - t0
                rate = processed / elapsed if elapsed > 0 else 0
                log.info("[%d/%d] %.1f/sec | %s", processed, len(rows), rate, title[:40])
        except Exception as exc:
            log.error("Failed: %s — %s", sid[:12], exc)
            failed += 1

    elapsed = time.time() - t0
    log.info("Layers done: %d processed, %d failed in %.0fs (%.1f/sec)",
             processed, failed, elapsed, processed / elapsed if elapsed > 0 else 0)

    # Backfill any missing embeddings
    log.info("Checking missing embeddings...")
    emb_count = 0
    while True:
        from stratum.services.layer_generator import backfill_embeddings
        n = backfill_embeddings(batch_size=200)
        if n == 0:
            break
        emb_count += n
        log.info("Embeddings: %d done", emb_count)

    log.info("COMPLETE: %d layers + %d embeddings, %d failed", processed, emb_count, failed)


if __name__ == "__main__":
    main()
