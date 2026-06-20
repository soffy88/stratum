"""auto_ingest — 单文件自动摄取，按 medium 分级 + provider 分流.

grade_cap 守命门:
  video/audio/podcast → grade_cap="unverified"  (讲课内容不自动升级)
  paper/book/article  → grade_cap=None          (可proven)
  其他                → grade_cap=None

provider 分流:
  video/audio/podcast → "ollama-local" (qwen2.5:7b 本地, 免费快, grade低无需精确)
  paper/book/其他     → "default"      (DeepSeek, 精确, 用于数学/科学内容)

深度理解管道 (每文件摄取后自动跑，单步失败不崩):
  1. RelationEngine.extract_relations_async  → 结网 (规则+LLM边unverified)
  2. DeepSynthesisEngine.build_overview_async → 社区聚类+大局摘要
  3. DeepSynthesisEngine.build_book_understanding_async → 书级理解(stance/论据grade独立)
"""
from __future__ import annotations

import asyncio
import functools
import json
import logging
import re
from pathlib import Path

from aii.service.ku_ingestion_engine import KuIngestionEngine
from aii.service.relation_engine import RelationEngine
from aii.service.synthesis_engine_deep import DeepSynthesisEngine
from aii.storage.pg_backend import PgBackend

logger = logging.getLogger(__name__)

_SUBJECTS = ["数学", "经济学", "物理", "化学", "生物", "计算机", "文学", "哲学", "历史", "心理学", "其他"]


async def _infer_subject_async(title: str) -> str:
    """从书名/标题用本地 LLM (qwen2.5:7b) 推断学科，失败返回'其他'。"""
    import requests as _req
    subjects_str = "/".join(_SUBJECTS)
    prompt = (
        f"这本书或文章属于哪个学科？只从[{subjects_str}]中选一个，只回答学科名，不要其他内容：\n{title}"
    )
    loop = asyncio.get_event_loop()
    try:
        resp = await loop.run_in_executor(
            None,
            functools.partial(
                _req.post,
                "http://localhost:11434/api/generate",
                json={"model": "qwen2.5:7b", "prompt": prompt, "stream": False},
                timeout=30,
            ),
        )
        raw = resp.json().get("response", "").strip()
        for subj in _SUBJECTS:
            if subj in raw:
                return subj
        return "其他"
    except Exception as e:
        logger.warning("auto_ingest: subject inference failed for '%s': %s", title[:30], e)
        return "其他"

_MEDIUM_GRADE_CAP: dict[str, str] = {
    "video": "unverified",
    "audio": "unverified",
    "podcast": "unverified",
}

# 低信任来源用本地模型(快/免费/grade_cap=unverified下质量够用)
# 高信任来源保留DeepSeek(数学/科学需要精确symbolic_form识别)
_MEDIUM_PROVIDER: dict[str, str] = {
    "video": "ollama-local",
    "audio": "ollama-local",
    "podcast": "ollama-local",
}

# medium → doc_type (书级理解的文档类型标签)
_MEDIUM_DOC_TYPE: dict[str, str] = {
    "video": "lecture",
    "audio": "lecture",
    "podcast": "lecture",
    "paper": "science",
    # book/article/其他 → "science" (默认; 无法仅凭medium区分数学书和文史书)
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
    subject = await _infer_subject_async(title)
    if not text:
        logger.warning("auto_ingest: empty content %s, marking done (0 KUs)", md_path.name)
        await backend.mark_substrate_ingested(substrate_id, title, medium, 0, subject=subject)
        return 0

    grade_cap = _MEDIUM_GRADE_CAP.get(medium)
    provider = _MEDIUM_PROVIDER.get(medium, "default")
    doc_type = _MEDIUM_DOC_TYPE.get(medium, "science")

    # ── Step 1: KU 抽取 ────────────────────────────────────────────────────
    engine = KuIngestionEngine(backend)
    try:
        result = await engine.ingest(
            text=text,
            project_id=substrate_id,
            substrate_id=substrate_id,
            grade_cap=grade_cap,
            provider=provider,
        )
    except Exception:
        logger.exception("auto_ingest: ingest failed for %s", md_path.name)
        return -1

    ku_count = len(result.get("registered", []))
    await backend.mark_substrate_ingested(substrate_id, title, medium, ku_count, subject=subject)
    logger.info(
        "auto_ingest: %s medium=%s provider=%s grade_cap=%s → %d KUs",
        title[:50], medium, provider, grade_cap, ku_count,
    )

    if ku_count == 0:
        return 0

    registered_ids = [str(kid) for kid in result.get("registered", []) if kid]

    # ── Step 2: 结网 (RelationEngine) ──────────────────────────────────────
    try:
        rel_engine = RelationEngine(backend)
        rel_result = await rel_engine.extract_relations_async(registered_ids, provider=provider)
        logger.info(
            "auto_ingest: relation %s → rule=%d llm=%d edges",
            title[:30], rel_result.get("rule_edges", 0), rel_result.get("llm_edges", 0),
        )
    except Exception:
        logger.exception("auto_ingest: RelationEngine failed for %s (non-fatal)", substrate_id[:8])

    # ── Step 3: 社区聚类 + 大局摘要 (DeepSynthesisEngine.build_overview) ────
    try:
        deep_engine = DeepSynthesisEngine(backend)
        ov_result = await deep_engine.build_overview_async(registered_ids, provider=provider)
        logger.info(
            "auto_ingest: overview %s → communities=%d synthesis=%d",
            title[:30], ov_result.get("communities", 0), ov_result.get("synthesis_count", 0),
        )
    except Exception:
        logger.exception("auto_ingest: build_overview failed for %s (non-fatal)", substrate_id[:8])

    # ── Step 4: 书级理解 (DeepSynthesisEngine.build_book_understanding) ────
    try:
        deep_engine2 = DeepSynthesisEngine(backend)
        bk_result = await deep_engine2.build_book_understanding_async(
            substrate_id, registered_ids, doc_type=doc_type, provider=provider,
        )
        logger.info(
            "auto_ingest: book_understanding %s → status=%s claims=%d",
            title[:30], bk_result.get("status"), bk_result.get("main_claims_count", 0),
        )
    except Exception:
        logger.exception("auto_ingest: book_understanding failed for %s (non-fatal)", substrate_id[:8])

    # 标记深度理解完成 (供飞轮回填检查)
    try:
        await backend.mark_deep_understood(substrate_id)
    except Exception:
        logger.warning("auto_ingest: mark_deep_understood failed for %s (non-fatal)", substrate_id[:8])

    return ku_count
