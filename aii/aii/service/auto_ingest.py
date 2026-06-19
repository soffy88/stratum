"""auto_ingest — 单文件自动摄取，按 medium 分级.

grade_cap 守命门:
  video/audio/podcast → grade_cap="unverified"  (讲课内容不自动升级)
  paper/book/article  → grade_cap=None          (可proven)
  其他                → grade_cap=None
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from aii.service.ku_ingestion_engine import KuIngestionEngine
from aii.storage.pg_backend import PgBackend

logger = logging.getLogger(__name__)

_MEDIUM_GRADE_CAP: dict[str, str] = {
    "video": "unverified",
    "audio": "unverified",
    "podcast": "unverified",
}

_PICTURE_RE = re.compile(
    r'[^\n]*(?:picture|figure|image)[^\n]*(?:intentionally\s+)?omitted[^\n]*\n?',
    re.IGNORECASE,
)


async def ingest_one(md_path: Path, backend: PgBackend) -> int:
    """Ingest one MD file. Returns KU count registered, -1 on skip, 0 on empty."""
    json_path = md_path.with_suffix(".json")
    if not json_path.exists():
        logger.warning("auto_ingest: no sidecar JSON for %s, skip", md_path.name)
        return -1

    try:
        meta = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("auto_ingest: bad JSON %s, skip", json_path.name)
        return -1

    substrate_id: str = meta.get("id", "")
    title: str = meta.get("title", md_path.stem)
    medium: str = (meta.get("medium") or "").lower()

    if not substrate_id:
        logger.warning("auto_ingest: no id field in %s, skip", json_path.name)
        return -1

    if await backend.is_substrate_ingested(substrate_id):
        logger.debug("auto_ingest: already ingested %s (%s)", substrate_id[:8], title[:40])
        return -1

    text = _PICTURE_RE.sub("", md_path.read_text(encoding="utf-8", errors="replace")).strip()
    if not text:
        logger.warning("auto_ingest: empty content %s, marking done (0 KUs)", md_path.name)
        await backend.mark_substrate_ingested(substrate_id, title, medium, 0)
        return 0

    grade_cap = _MEDIUM_GRADE_CAP.get(medium)
    engine = KuIngestionEngine(backend)
    try:
        result = await engine.ingest(
            text=text,
            project_id=substrate_id,
            substrate_id=substrate_id,
            grade_cap=grade_cap,
        )
    except Exception:
        logger.exception("auto_ingest: ingest failed for %s", md_path.name)
        return -1

    ku_count = len(result.get("registered", []))
    await backend.mark_substrate_ingested(substrate_id, title, medium, ku_count)
    logger.info(
        "auto_ingest: %s medium=%s grade_cap=%s → %d KUs",
        title[:50], medium, grade_cap, ku_count,
    )
    return ku_count
