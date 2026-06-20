"""
Layer 4: 调 omodul.export_substrate_markdown 把 substrate 导出为带 frontmatter
的 .md 到 AII 共享目录。

调用链（全主库元素，不改主库）:
  substrate (DB) → omodul.export_substrate_markdown
    (内部: text_clean_publish_noise + markdown_frontmatter_build)
  → 写 .md 到 /data/shared/stratum-to-aii/
"""
import asyncio
import logging
import shutil
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


def export_one(substrate_id: str) -> dict:
    """导出单个 substrate 为 .md（带 frontmatter）到 AII 共享目录。"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT s.id, s.title, s.mime, s.language, s.meta_json, d.content "
            "FROM substrates s "
            "JOIN derivative d ON s.id = d.substrate_id "
            "WHERE s.id = ? AND d.kind = 'markdown' "
            "AND d.content IS NOT NULL AND LENGTH(d.content) > 0",
            (substrate_id,)
        ).fetchone()

    if not row:
        return {"status": "skipped", "reason": "no markdown content", "substrate_id": substrate_id}

    sid, title, mime, language, meta_json, content = row
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
            "AND (s.parse_quality IS NULL OR s.parse_quality = 'ok')"
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
