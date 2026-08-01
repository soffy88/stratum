#!/usr/bin/env python3
"""backfill_ku_layers.py — 批量为 KU 生成 L0/L1 摘要 + embeddings.

策略:
  - L0 = title[:200] (或 natural_text 前200 chars)
  - L1 = natural_text[:3000]
  - L2 = natural_text (full)
  - embedding = computed from L0

预期速度: ~8/sec (embedding-only, no LLM)
"""

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("backfill_ku")

_BATCH_SIZE = 500


def main():
    from stratum.db import get_conn
    from stratum.services.layer_generator import _get_embedding, _gen_id, _estimate_tokens, _MODEL

    with get_conn() as conn:
        rows = conn.execute(
            """SELECT k.ku_id, k.title, k.natural_text
               FROM aii.ku_onto k
               LEFT JOIN stratum.ku_layers kl ON k.ku_id = kl.ku_id AND kl.layer = 'L0'
               WHERE kl.id IS NULL
                 AND k.natural_text IS NOT NULL
                 AND length(k.natural_text) > 30
               ORDER BY k.created_at DESC"""
        ).fetchall()

    log.info("KUs without L0: %d", len(rows))
    if not rows:
        log.info("Nothing to do!")
        return

    processed = 0
    failed = 0
    t0 = time.time()

    for ku_id, title, text in rows:
        title = title or "Untitled"
        text = text.replace("\x00", "") if text else ""

        l0 = (title[:200] if title else text[:200])
        l1 = text[:3000]
        l2 = text

        try:
            embedding = _get_embedding(l0)

            with get_conn() as conn:
                for layer_name, content in [("L0", l0), ("L1", l1), ("L2", l2)]:
                    if not content:
                        continue
                    layer_id = _gen_id(f"kl-{ku_id}-{layer_name}")

                    if layer_name == "L0" and embedding:
                        emb_str = "[" + ",".join(str(x) for x in embedding) + "]"
                        conn.execute(
                            """INSERT INTO ku_layers (id, ku_id, layer, content, token_count, model_used, embedding)
                               VALUES (?, ?, ?, ?, ?, ?, ?::vector)
                               ON CONFLICT (ku_id, layer) DO UPDATE
                               SET content = EXCLUDED.content,
                                   token_count = EXCLUDED.token_count,
                                   generated_at = NOW()""",
                            (layer_id, ku_id, layer_name, content.replace("\x00", ""),
                             _estimate_tokens(content), _MODEL, emb_str),
                        )
                    else:
                        conn.execute(
                            """INSERT INTO ku_layers (id, ku_id, layer, content, token_count, model_used)
                               VALUES (?, ?, ?, ?, ?, ?)
                               ON CONFLICT (ku_id, layer) DO UPDATE
                               SET content = EXCLUDED.content,
                                   token_count = EXCLUDED.token_count,
                                   generated_at = NOW()""",
                            (layer_id, ku_id, layer_name, content.replace("\x00", ""),
                             _estimate_tokens(content), _MODEL),
                        )

            processed += 1
            if processed % 100 == 0:
                elapsed = time.time() - t0
                rate = processed / elapsed if elapsed > 0 else 0
                log.info("[%d/%d] %.1f/sec | %s", processed, len(rows), rate, title[:40])

        except Exception as exc:
            log.error("Failed: %s — %s", ku_id[:16], exc)
            failed += 1

    elapsed = time.time() - t0
    log.info("COMPLETE: %d processed, %d failed in %.0fs (%.1f/sec)",
             processed, failed, elapsed, processed / elapsed if elapsed > 0 else 0)


if __name__ == "__main__":
    main()
