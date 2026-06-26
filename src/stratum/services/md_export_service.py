"""
Layer 4: 调 omodul.export_substrate_markdown 把 substrate 导出为带 frontmatter
的 .md 到 AII 共享目录。

调用链（全主库元素，不改主库）:
  substrate (DB) → omodul.export_substrate_markdown
    (内部: text_clean_publish_noise + markdown_frontmatter_build)
  → 写 .md 到 /data/shared/stratum-to-aii/
  → [book 类] book_structure_inject: 章节 H1 注入 + TOC 围栏 + 页眉剔除
"""
import asyncio
import logging
import shutil
import sys
import tempfile
from pathlib import Path

from omodul.export_substrate_markdown import (
    ExportSubstrateMarkdownConfig,
    ExportSubstrateMarkdownInput,
    export_substrate_markdown,
)

from stratum.db import get_conn

log = logging.getLogger(__name__)

EXPORT_DIR = Path("/data/shared/stratum-to-aii")

_MEDIUM_TO_DOC_TYPE = {
    "paper": "paper",
    "book": "book",
    "epub": "book",
    "webpage": "article",
    "pdf": "paper",
    "text": "article",
    "video": "article",
}


def _doc_type(mime: str, meta_json: dict) -> str:
    medium = (meta_json or {}).get("medium", "")
    if medium in _MEDIUM_TO_DOC_TYPE:
        return _MEDIUM_TO_DOC_TYPE[medium]
    for key, val in _MEDIUM_TO_DOC_TYPE.items():
        if key in (mime or "").lower():
            return val
    return "article"


def _inject_book_structure(substrate_id: str, md_path: Path, file_path: str | None) -> bool:
    """Book md 导出后，若 PDF 有章节书签则注入章节结构（R1/R2/R3/R9/R5）。

    原地覆盖 md_path。Returns True if injection was performed.
    skip_tables=True（表格重提耗时，留给批处理 book_structure_inject --batch-all）。
    """
    if not file_path:
        return False
    pdf_path = Path(file_path)
    if not pdf_path.exists() or pdf_path.suffix.lower() != '.pdf':
        return False

    try:
        # scripts/ 目录在容器内挂为 /app/scripts
        if '/app/scripts' not in sys.path:
            sys.path.insert(0, '/app/scripts')
        from book_structure_inject import inject_structure_inplace  # type: ignore[import]

        result = inject_structure_inplace(
            md_path=md_path,
            pdf_path=pdf_path,
            substrate_id=substrate_id,
            skip_tables=True,  # 快速模式：章节注入+页眉剔除，不重提表格
        )
        if result is not None:
            acc = result.acceptance
            log.info(
                "md_export: structure injected for %s — chapters=%d/%d R9_pass=%s",
                substrate_id[:8], result.chapters_found, result.chapters_total,
                acc.get('R9_pass'),
            )
            return True
    except Exception as e:
        log.warning("md_export: structure inject failed for %s: %s", substrate_id[:8], e)
    return False


def export_one(substrate_id: str) -> dict:
    """导出单个 substrate 为 .md（带 frontmatter）到 AII 共享目录。"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT s.id, s.title, s.mime, s.language, s.meta_json, d.content, s.source_path "
            "FROM substrates s "
            "JOIN derivative d ON s.id = d.substrate_id "
            "WHERE s.id = ? AND d.kind = 'markdown' "
            "AND d.content IS NOT NULL AND LENGTH(d.content) > 0",
            (substrate_id,)
        ).fetchone()

    if not row:
        return {"status": "skipped", "reason": "no markdown content", "substrate_id": substrate_id}

    sid, title, mime, language, meta_json, content, file_path = row
    if isinstance(meta_json, str):
        import json as _json
        try:
            meta_json = _json.loads(meta_json)
        except Exception:
            meta_json = {}
    meta_json = meta_json or {}

    doc_type = _doc_type(mime, meta_json)

    config = ExportSubstrateMarkdownConfig(
        substrate_id=sid,
        doc_type=doc_type,
        clean_noise=True,
    )
    input_data = ExportSubstrateMarkdownInput(
        content=content,
        metadata={
            "title": title or sid,
            "language": language or "zh",
            "source": "stratum",
        },
    )

    # export to temp dir so omodul audit files (report .md, decision_trail.json)
    # don't pollute the AII shared dir — only the content .md is moved over
    with tempfile.TemporaryDirectory(prefix="md_export_") as tmp:
        tmp_path = Path(tmp)
        result = asyncio.run(
            export_substrate_markdown(config=config, input_data=input_data, output_dir=tmp_path)
        )

        status = result.get("status")
        if status == "completed":
            findings = result.get("findings")
            src = Path(findings.file_path)
            EXPORT_DIR.mkdir(parents=True, exist_ok=True)
            dst = EXPORT_DIR / src.name
            shutil.move(str(src), dst)
            # patch findings.file_path to reflect final location
            findings.file_path = str(dst)
            log.info("md_export: exported %s → %s", title, dst.name)

            # Book 类: 自动注入章节结构 (R1/R2/R3/R9/R5)
            if doc_type == "book":
                _inject_book_structure(sid, dst, file_path)
        else:
            log.warning("md_export: failed %s: %s", title, result.get("error"))

    return result


def export_all(doc_type_filter: str | None = None) -> dict:
    """批量导出所有有 markdown 的 substrate。"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT s.id, s.mime, s.meta_json "
            "FROM substrates s "
            "JOIN derivative d ON s.id = d.substrate_id "
            "WHERE d.kind = 'markdown' AND d.content IS NOT NULL AND LENGTH(d.content) > 0 "
            "AND s.parse_quality = 'ok'"
        ).fetchall()

    targets = []
    for sid, mime, meta_json in rows:
        if isinstance(meta_json, str):
            import json as _json
            try:
                meta_json = _json.loads(meta_json)
            except Exception:
                meta_json = {}
        if doc_type_filter and _doc_type(mime, meta_json or {}) != doc_type_filter:
            continue
        if (meta_json or {}).get("is_collection"):
            continue
        targets.append(sid)

    exported = skipped = 0
    for sid in targets:
        r = export_one(sid)
        if r.get("status") == "completed":
            exported += 1
        else:
            skipped += 1

    log.info("md_export: batch done — %d exported, %d skipped", exported, skipped)
    return {"total": len(targets), "exported": exported, "skipped": skipped}
