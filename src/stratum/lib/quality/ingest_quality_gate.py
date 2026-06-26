"""ingest_quality_gate — 入库质保门禁（Stratum Layer 4, §20）.

在 _fill_derivative_content 之后调用，写最终 parse_quality + quality_reason。

优先级:
  quarantine (file_corrupt)   ← 文件打不开，最高优先
  fragment                    ← 双条件: 标题词 + content < 2000
  omodul 设的 scanned/empty/garbled/ocr_ok  ← 已有正确标记，保留不覆盖
  quarantine (md_empty / md_too_short)
  ok                          ← 全部通过
"""
from __future__ import annotations

import logging

from stratum.db import get_conn
from stratum.lib.quality.source_openable_check import check_source_openable
from stratum.lib.quality.md_validity_check import check_md_validity
from stratum.lib.quality.fragment_detect import is_fragment

log = logging.getLogger(__name__)

_PQ_RESPECT = frozenset(["scanned", "empty", "garbled", "ocr_ok", "duplicate", "bundle"])


def run_quality_gate(substrate_id: str) -> dict:
    """Run quality checks and write pq + quality_reason to DB.

    Returns {"pq": str, "reason": str | None}.
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT source_path, mime, title, parse_quality"
            " FROM substrates WHERE id = ?",
            (substrate_id,),
        ).fetchone()

    if not row:
        log.warning("quality_gate: substrate not found %s", substrate_id)
        return {"pq": None, "reason": "substrate_not_found"}

    source_path, mime, title, current_pq = row

    with get_conn() as conn:
        md_row = conn.execute(
            "SELECT content FROM derivative WHERE substrate_id = ? AND kind = 'markdown'",
            (substrate_id,),
        ).fetchone()
    md_content: str | None = md_row[0] if md_row else None

    # ── 1. Source openable (最高优先，即使 omodul 已设 pq 也检查) ─────────────
    ok, open_reason = check_source_openable(source_path, mime)
    if not ok:
        _write_pq(substrate_id, "quarantine", f"file_corrupt:{open_reason}")
        return {"pq": "quarantine", "reason": f"file_corrupt:{open_reason}"}

    # ── 2. 尊重 omodul 已设的精确状态 ───────────────────────────────────────
    if current_pq in _PQ_RESPECT:
        return {"pq": current_pq, "reason": "omodul_classified"}

    # ── 3. Fragment (双条件) ─────────────────────────────────────────────────
    if is_fragment(title, md_content):
        _write_pq(substrate_id, "fragment", "fragment_detected")
        return {"pq": "fragment", "reason": "fragment_detected"}

    # ── 4. MD 有效性 ─────────────────────────────────────────────────────────
    md_ok, md_reason = check_md_validity(md_content, current_pq)
    if not md_ok:
        _write_pq(substrate_id, "quarantine", md_reason)
        return {"pq": "quarantine", "reason": md_reason}

    # ── 5. 全通过 ────────────────────────────────────────────────────────────
    _write_pq(substrate_id, "ok", None)
    return {"pq": "ok", "reason": None}


def _write_pq(substrate_id: str, pq: str, reason: str | None) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE substrates"
            " SET parse_quality = ?, quality_reason = ?, updated_at = NOW()"
            " WHERE id = ?",
            (pq, reason, substrate_id),
        )
    log.info("quality_gate: %s → pq=%s reason=%s", substrate_id[:12], pq, reason)
