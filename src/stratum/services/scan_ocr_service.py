"""scan_ocr_service — 扫描版 PDF OCR 后处理（Stratum Layer 4, §20 零主库改动）。

触发条件:
  substrates.parse_quality IN ('scanned', 'empty', 'garbled')

流程（双轨）:
  is_math=True  → Unlimited-OCR（宿主机 GPU 服务，端到端 LaTeX）
  is_math=False → PPStructureV3（容器内 CPU ONNX）

  公共尾部:
  4. UPDATE substrates: parse_quality='ocr_ok', parser=..., updated_at
  5. UPSERT derivative kind='markdown' with OCR content
  6. md_export_service.export_one() → 写 AII 共享目录

约束:
  - Unlimited-OCR server: http://172.19.0.1:8765 (宿主机，Wan2GP venv)
  - PPStructureV3: use_formula_recognition=False (ONNX 无公式版)
  - PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True (docker-compose env)
"""
from __future__ import annotations

import glob
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any

import fitz  # pymupdf

from stratum.db import get_conn

log = logging.getLogger(__name__)

_OCR_TARGET_PQ = ("scanned", "empty", "garbled")
_MATH_KEYWORDS = (
    "数学", "分析", "微积分", "泛函", "拓扑", "代数", "概率", "统计",
    "calculus", "analysis", "mathematics", "stochastic", "topology",
    "algebra", "econometrics",
)

# 每次批量的最大页数（避免OOM，超大书分批）
_PAGE_BATCH = 50

# ── Unlimited-OCR 宿主机服务 ─────────────────────────────────────────────────
_UNLIMITED_OCR_URL = "http://172.19.0.1:8766/ocr"
_UNLIMITED_OCR_HEALTH = "http://172.19.0.1:8766/health"
_MATH_PHYSICS_KEYWORDS = (
    "数学", "物理", "分析", "微积分", "泛函", "拓扑", "代数", "概率",
    "统计", "线性", "力学", "量子", "电磁", "光学",
    "calculus", "analysis", "mathematics", "physics", "stochastic",
    "topology", "algebra", "mechanics", "optics", "quantum",
)


def _is_math_physics_book(title: str | None, meta_json: dict | None) -> bool:
    title_lower = (title or "").lower()
    meta = meta_json or {}
    subjects = " ".join(str(v) for v in meta.values()).lower()
    return any(kw in title_lower or kw in subjects for kw in _MATH_PHYSICS_KEYWORDS)


def _unlimited_ocr_available() -> bool:
    """Check if the Unlimited-OCR server on the host is reachable."""
    try:
        import urllib.request
        with urllib.request.urlopen(_UNLIMITED_OCR_HEALTH, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def _unlimited_ocr_det_to_md(raw: str) -> str:
    """Convert Unlimited-OCR tagged output to clean Markdown.

    Input format: <|det|>TYPE [x1,y1,x2,y2]<|/det|>CONTENT
    """
    import re
    lines = []
    # Match: <|det|>type [coords]<|/det|>content
    pattern = re.compile(
        r'<\|det\|>\s*(\w+)\s*\[[^\]]*\]\s*<\|/det\|>(.*?)(?=<\|det\|>|$)',
        re.DOTALL,
    )
    for m in pattern.finditer(raw):
        det_type = m.group(1).strip()
        content = m.group(2).strip()
        if not content:
            continue
        if det_type in ("page_number", "footer", "image"):
            continue
        if det_type in ("header", "title"):
            lines.append(f"## {content}")
        elif det_type == "image_caption":
            lines.append(f"*{content}*")
        else:
            # text, equation, table — output as-is
            lines.append(content)
    return "\n\n".join(lines) if lines else raw


def _unlimited_ocr_page(img_path: str) -> str:
    """OCR a single page image via the Unlimited-OCR host service.

    Falls back to empty string on connection/server errors.
    """
    import urllib.request, urllib.error, json
    try:
        with open(img_path, "rb") as f:
            data = f.read()
        boundary = b"----OCRBoundary"
        body = (
            b"--" + boundary + b"\r\n"
            b'Content-Disposition: form-data; name="file"; filename="page.png"\r\n'
            b"Content-Type: image/png\r\n\r\n"
            + data + b"\r\n"
            b"--" + boundary + b"--\r\n"
        )
        req = urllib.request.Request(
            _UNLIMITED_OCR_URL,
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary.decode()}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=600) as resp:
            result = json.loads(resp.read())
        raw = result.get("markdown", "")
        return _unlimited_ocr_det_to_md(raw)
    except Exception as exc:
        log.warning("unlimited_ocr: request failed: %s", exc)
        return ""


def _is_math_book(title: str | None, meta_json: dict | None) -> bool:
    title_lower = (title or "").lower()
    meta = meta_json or {}
    subjects = " ".join(str(v) for v in meta.values()).lower()
    return any(kw in title_lower or kw in subjects for kw in _MATH_KEYWORDS)


def _get_ocr_engine():
    """懒加载 PPStructureV3，只在第一次调用时初始化（含模型加载）。"""
    import paddleocr
    return paddleocr.PPStructureV3(
        engine="onnxruntime",
        lang="ch",
        use_formula_recognition=False,
        use_chart_recognition=False,
    )


_ocr_engine_cache = None


def _ocr_engine():
    global _ocr_engine_cache
    if _ocr_engine_cache is None:
        log.info("scan_ocr: loading PPStructureV3 (first call)...")
        t = time.time()
        _ocr_engine_cache = _get_ocr_engine()
        log.info("scan_ocr: PPStructureV3 ready in %.1fs", time.time() - t)
    return _ocr_engine_cache


def _pdf_page_to_png(pdf_path: str, page_idx: int, dpi: int = 150) -> bytes:
    doc = fitz.open(pdf_path)
    pix = doc[page_idx].get_pixmap(dpi=dpi)
    doc.close()
    return pix.tobytes("png")


def _ocr_pdf_pages(
    pdf_path: str,
    page_indices: list[int],
    tmp_dir: str,
    *,
    use_unlimited_ocr: bool = False,
) -> list[str]:
    """OCR 一批页面，返回每页 markdown 字符串列表（顺序与 page_indices 一致）。

    use_unlimited_ocr=True → Unlimited-OCR host service (数理书，LaTeX公式)
    use_unlimited_ocr=False → PPStructureV3 (普通扫描, CPU ONNX)
    """
    if not use_unlimited_ocr:
        engine = _ocr_engine()
    results: list[str] = []
    doc = fitz.open(pdf_path)
    # 两路都用 150 DPI：model 内部 resize 到 image_size=1024，更高 DPI 不提质量只增耗时
    dpi = 150
    for i, pg_idx in enumerate(page_indices):
        img_path = os.path.join(tmp_dir, f"page_{pg_idx:04d}.png")
        pix = doc[pg_idx].get_pixmap(dpi=dpi)
        pix.save(img_path)

        if use_unlimited_ocr:
            # ── Unlimited-OCR 路径 ──────────────────────────────────────────
            log.info("scan_ocr: unlimited_ocr page %d/%d", pg_idx + 1, max(page_indices) + 1)
            md = _unlimited_ocr_page(img_path)
            results.append(md)
            continue

        # ── PP-StructureV3 路径 ─────────────────────────────────────────────
        try:
            result = list(engine.predict(img_path))
        except Exception as exc:
            log.warning("scan_ocr: page %d ocr failed: %s", pg_idx + 1, exc)
            results.append("")
            continue

        if not result:
            results.append("")
            continue

        r = result[0]

        # 主路径: save_to_markdown → 读文件（最可靠）
        page_out = os.path.join(tmp_dir, f"md_page_{pg_idx:04d}")
        os.makedirs(page_out, exist_ok=True)
        md = ""
        try:
            r.save_to_markdown(page_out)
            mds = glob.glob(page_out + "/**/*.md", recursive=True) + glob.glob(page_out + "/*.md")
            if mds:
                md = open(mds[0]).read()
        except Exception as exc:
            log.warning("scan_ocr: save_to_markdown failed page %d: %s", pg_idx + 1, exc)

        # 备路径: 直接从 .markdown 属性读（跳过文件IO）
        if not md.strip():
            try:
                md_obj = r.get("markdown", {}) if isinstance(r, dict) else getattr(r, "markdown", {})
                if isinstance(md_obj, dict):
                    md = (md_obj.get("markdown_texts") or md_obj.get("content") or "")
                    if not md:
                        md = "\n".join(str(v) for v in md_obj.values() if isinstance(v, str) and len(str(v)) > 20)
                elif isinstance(md_obj, str):
                    md = md_obj
            except Exception:
                pass

        results.append(md)
    doc.close()
    return results


def _normalize_math_formulas(text: str, substrate_id: str) -> str:
    """LLM 公式归一化：把 OCR 输出的 x^{2} / f(x^{2) → 规范 LaTeX/unicode。

    轻量 prompt，只处理明确的 OCR 歧义，不做 LLM 解题。
    失败时返回原始文本（不中断入库）。
    """
    try:
        from oprim.llm.llm_call import llm_call

        prompt = (
            "以下是扫描版数学书某页的 OCR 输出，包含未规范化的上下标符号。\n"
            "请仅对数学公式做最小化修正：\n"
            "  - x^{2} → x²（可选，保留LaTeX也行）\n"
            "  - a^{n} → aⁿ 或 $a^n$（统一即可）\n"
            "  - 修正明显识别错误（如 O→0 在公式中，l→1 在分母中）\n"
            "  - 不改正文，不补内容，不解释\n"
            "直接输出修正后的全文：\n\n" + text[:8000]
        )
        normalized = llm_call(
            prompt=prompt,
            provider="qwen3_dashscope",
            model="qwen-plus",
        )
        if normalized:
            log.info("scan_ocr: math normalization done for %s", substrate_id[:12])
            return normalized
        return text
    except Exception as exc:
        log.warning("scan_ocr: math normalization skipped: %s", exc)
        return text


def _upsert_derivative_markdown(conn, substrate_id: str, content: str) -> None:
    """UPSERT derivative kind='markdown'。"""
    from ulid import ULID

    existing = conn.execute(
        "SELECT id FROM derivative WHERE substrate_id=? AND kind='markdown' LIMIT 1",
        (substrate_id,)
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE derivative SET content=? WHERE substrate_id=? AND kind='markdown'",
            (content, substrate_id),
        )
    else:
        conn.execute(
            "INSERT INTO derivative (id, substrate_id, kind, seq, content, created_at)"
            " VALUES (?, ?, 'markdown', 0, ?, NOW())",
            (str(ULID()), substrate_id, content),
        )


def ocr_one(substrate_id: str, *, force: bool = False) -> dict:
    """OCR 单个 substrate。

    Returns:
        dict with keys: status, substrate_id, page_count, elapsed_s, parse_quality
    """
    t_start = time.time()

    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, title, source_path, parse_quality, mime, meta_json"
            " FROM substrates WHERE id=?",
            (substrate_id,)
        ).fetchone()

    if not row:
        return {"status": "not_found", "substrate_id": substrate_id}

    sid, title, source_path, parse_quality, mime, meta_json = row

    if not force and parse_quality == "ocr_ok":
        return {"status": "skipped", "reason": "already ocr_ok", "substrate_id": sid}

    if parse_quality not in _OCR_TARGET_PQ and not force:
        return {"status": "skipped", "reason": f"parse_quality={parse_quality!r} not target", "substrate_id": sid}

    if not source_path or not Path(source_path).exists():
        log.error("scan_ocr: source_path missing or not found: %s", source_path)
        return {"status": "error", "reason": "source_path not found", "substrate_id": sid}

    # Only PDFs handled via OCR
    if mime and "pdf" not in mime.lower():
        return {"status": "skipped", "reason": f"mime={mime} not pdf", "substrate_id": sid}

    import json
    meta = json.loads(meta_json or "{}")
    is_math = _is_math_physics_book(title, meta)

    # 决定 OCR 引擎：数理书 → Unlimited-OCR（如服务可用），否则 PPStructureV3
    use_unlimited = is_math and _unlimited_ocr_available()
    parser_tag = "unlimited-ocr" if use_unlimited else "paddleocr-v6"

    log.info(
        "scan_ocr: starting OCR %s (title=%r, is_math=%s, engine=%s)",
        sid[:12], (title or "")[:40], is_math, parser_tag,
    )

    doc = fitz.open(source_path)
    page_count = len(doc)
    doc.close()

    all_pages_md: list[str] = []
    with tempfile.TemporaryDirectory(prefix="scan_ocr_") as tmp_dir:
        for batch_start in range(0, page_count, _PAGE_BATCH):
            batch_end = min(batch_start + _PAGE_BATCH, page_count)
            page_indices = list(range(batch_start, batch_end))
            log.info("scan_ocr: OCR pages %d-%d / %d", batch_start + 1, batch_end, page_count)
            batch_mds = _ocr_pdf_pages(
                source_path, page_indices, tmp_dir,
                use_unlimited_ocr=use_unlimited,
            )
            all_pages_md.extend(batch_mds)

    full_md = "\n\n---\n\n".join(p for p in all_pages_md if p.strip())

    if not full_md.strip():
        log.warning("scan_ocr: empty OCR result for %s", sid[:12])
        return {"status": "error", "reason": "ocr_empty_output", "substrate_id": sid, "elapsed_s": round(time.time() - t_start, 1)}

    if is_math:
        full_md = _normalize_math_formulas(full_md, sid)

    with get_conn() as conn:
        conn.execute(
            "UPDATE substrates SET parse_quality='ocr_ok', parser=?,"
            " updated_at=NOW() WHERE id=?",
            (parser_tag, sid)
        )
        _upsert_derivative_markdown(conn, sid, full_md)

    # Re-export to AII shared dir
    try:
        from stratum.services.md_export_service import export_one
        export_one(sid)
        log.info("scan_ocr: md_export done for %s", sid[:12])
    except Exception as exc:
        log.warning("scan_ocr: md_export failed (non-fatal) %s: %s", sid[:12], exc)

    elapsed = round(time.time() - t_start, 1)
    log.info("scan_ocr: done %s pages=%d elapsed=%.1fs", sid[:12], page_count, elapsed)
    return {
        "status": "ok",
        "substrate_id": sid,
        "title": title,
        "page_count": page_count,
        "is_math": is_math,
        "engine": parser_tag,
        "elapsed_s": elapsed,
        "parse_quality": "ocr_ok",
        "md_chars": len(full_md),
    }


def ocr_batch(
    *,
    user_id: str | None = None,
    dry_run: bool = False,
    force: bool = False,
    max_books: int = 50,
) -> dict:
    """批量 OCR 所有 scanned/empty/garbled substrates。

    Args:
        user_id: 限定用户，None = 全库
        dry_run: 不实际执行 OCR，只返回候选列表
        force: 强制重跑已是 ocr_ok 的书
        max_books: 单次批量上限

    Returns:
        dict with results list and summary
    """
    pq_filter = list(_OCR_TARGET_PQ)
    if force:
        pq_filter.append("ocr_ok")

    placeholders = ", ".join("?" * len(pq_filter))
    params: list = list(pq_filter)

    query = (
        f"SELECT id, title, source_path, parse_quality, mime"
        f" FROM substrates WHERE parse_quality IN ({placeholders})"
        f" AND mime LIKE '%pdf%'"
    )
    if user_id:
        query += " AND user_id=?"
        params.append(user_id)
    query += f" ORDER BY created_at LIMIT {max_books}"

    with get_conn() as conn:
        candidates = conn.execute(query, params).fetchall()

    log.info("scan_ocr: batch found %d candidates (dry_run=%s)", len(candidates), dry_run)

    if dry_run:
        return {
            "status": "dry_run",
            "count": len(candidates),
            "candidates": [
                {"id": r[0], "title": r[1], "parse_quality": r[3]} for r in candidates
            ],
        }

    results = []
    ok_count = err_count = skip_count = 0

    for r in candidates:
        sid, title = r[0], r[1]
        try:
            result = ocr_one(sid, force=force)
            results.append(result)
            if result["status"] == "ok":
                ok_count += 1
            elif result["status"] == "skipped":
                skip_count += 1
            else:
                err_count += 1
        except Exception as exc:
            log.error("scan_ocr: batch item failed %s: %s", sid[:12], exc, exc_info=True)
            results.append({"status": "error", "substrate_id": sid, "reason": str(exc)})
            err_count += 1

    return {
        "status": "done",
        "total": len(candidates),
        "ok": ok_count,
        "skipped": skip_count,
        "error": err_count,
        "results": results,
    }
