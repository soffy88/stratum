#!/usr/bin/env python3
"""upgrade_pdf_l0.py — 将 PDF substrate 的 L0 从文件名升级为实际首段文本.

策略:
  - 用 PyMuPDF 提取 PDF 第一页前 300 字符
  - 如果首段太短 (<30 chars), 尝试第二页
  - 直接替换 L0 content (不调 LLM, 纯提取)
  - 重新计算 embedding

预期速度: ~20/sec (受 embedding API 限制)
"""

import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("upgrade_pdf_l0")


def _extract_first_text(pdf_path: str, max_chars: int = 300) -> str | None:
    """Extract first page text from PDF, truncated to max_chars."""
    import fitz
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page_idx in range(min(2, len(doc))):
            text += doc[page_idx].get_text()
            if len(text) >= 50:
                break
        doc.close()
        # Clean up
        text = " ".join(text.split())  # normalize whitespace
        return text[:max_chars] if text else None
    except Exception as exc:
        log.warning("PDF extract failed for %s: %s", pdf_path[:60], exc)
        return None


def main():
    from stratum.db import get_conn
    from stratum.services.layer_generator import _persist_substrate_layers

    with get_conn() as conn:
        rows = conn.execute(
            """SELECT s.id, s.title, s.source_path,
                      sl.content as current_l0
               FROM substrates s
               JOIN substrate_layers sl ON s.id = sl.substrate_id AND sl.layer = 'L0'
               WHERE s.mime LIKE '%%pdf%%'
                 AND s.source_path IS NOT NULL
               ORDER BY s.created_at DESC"""
        ).fetchall()

    log.info("PDF substrates with L0: %d", len(rows))

    # Filter to those where L0 is just the title (needs upgrade)
    needs_upgrade = []
    for sid, title, path, current_l0 in rows:
        if not path or not os.path.exists(path):
            continue
        # If L0 is identical to title (or very similar), it needs upgrading
        title_clean = (title or "").strip()
        l0_clean = (current_l0 or "").strip()
        if l0_clean == title_clean or len(l0_clean) < 50:
            needs_upgrade.append((sid, title, path))

    log.info("PDFs needing L0 upgrade: %d", len(needs_upgrade))
    if not needs_upgrade:
        log.info("Nothing to do!")
        return

    processed = 0
    upgraded = 0
    failed = 0
    t0 = time.time()

    for sid, title, path in needs_upgrade:
        processed += 1
        extracted = _extract_first_text(path, max_chars=300)

        if extracted and len(extracted) > 30 and extracted != (title or ""):
            # Use extracted text as L0
            l0 = extracted[:200]
            layers = {"L0": l0, "L1": f"# {title or 'Untitled'}", "L2": title or ""}
            try:
                _persist_substrate_layers(sid, layers)
                upgraded += 1
            except Exception as exc:
                log.error("Persist failed for %s: %s", sid[:16], exc)
                failed += 1
        else:
            # Keep existing (title-only) L0
            pass

        if processed % 200 == 0:
            elapsed = time.time() - t0
            rate = processed / elapsed if elapsed > 0 else 0
            log.info("[%d/%d] %.1f/sec | upgraded=%d failed=%d",
                     processed, len(needs_upgrade), rate, upgraded, failed)

    elapsed = time.time() - t0
    log.info("COMPLETE: %d processed, %d upgraded, %d failed in %.0fs (%.1f/sec)",
             processed, upgraded, failed, elapsed, processed / elapsed if elapsed > 0 else 0)


if __name__ == "__main__":
    main()
