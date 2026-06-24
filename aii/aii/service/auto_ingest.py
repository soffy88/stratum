"""auto_ingest — 单文件自动摄取，按 medium 分级 + provider 分流.

grade_cap 守命门:
  video/audio/podcast → grade_cap="unverified"  (讲课内容不自动升级)
  paper/book/article  → grade_cap=None          (可proven)
  其他                → grade_cap=None

provider 分流:
  video/audio/podcast → "ollama-local" (qwen2.5:7b 本地, 免费快, grade低无需精确)
  paper/book/其他     → "default"      (DeepSeek, 精确, 用于数学/科学内容)

分块摄取 (修复整书全文一次塞LLM只抽7-12条KU的病根):
  整书 text → _split_text_into_chunks() 按 H2/H3 结构或字数切块
  每块独立调 engine.ingest() → 各自拥有完整 2048 token 输出空间
  汇总所有块的 KU → 正常规模 (几十-几百条/书)
  参考 textbook_ingest 的正确分块范例，不重新发明。

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

_PICTURE_KEYWORDS = frozenset(("picture", "figure", "image"))

# 分块参数: 每块目标字符数 (约 3000 汉字 ≈ 4500 ASCII 字符)
# 超过此阈值的结构块会被进一步按字数切分，避免单块仍太大
_CHUNK_TARGET_CHARS: int = 4000
_CHUNK_MAX_CHARS: int = 8000  # 硬上限: 超过此大小强制切分


def _strip_omitted_lines(text: str) -> str:
    """Remove lines that mention a visual placeholder being omitted.

    The original regex `[^\n]*(?:picture|figure|image)[^\n]*omitted[^\n]*` caused
    catastrophic backtracking (O(n²)) on files where many lines contain "figure"
    but not "omitted" — measured at 51 s on a 241 KB economics textbook.
    This O(n) line-by-line replacement takes < 1 ms on the same file.
    """
    result: list[str] = []
    for line in text.splitlines(keepends=True):
        ll = line.lower()
        if any(kw in ll for kw in _PICTURE_KEYWORDS) and "omitted" in ll:
            continue
        result.append(line)
    return "".join(result)


def _split_text_into_chunks(text: str) -> list[str]:
    """将全书文本按 H2/H3 标题结构切分成独立块，每块单独送 LLM。

    策略 (参考 textbook_parser 的正确范例):
    1. 优先按 ## / ### 标题切分 → 每个 section 一块
    2. 若某块超过 _CHUNK_MAX_CHARS，进一步按段落切分到 _CHUNK_TARGET_CHARS
    3. 若全文无 ## / ### 标题，退化为按 _CHUNK_TARGET_CHARS 字数切分
    4. 每块至少保留标题上下文 (heading 前缀) 供 LLM 理解
    5. 过滤掉空块和纯空白块

    ★ 这是修复整书全文一次塞LLM只抽7-12条KU病根的核心函数。
    """
    lines = text.splitlines(keepends=True)

    # ── 尝试按 H2 / H3 结构切分 ──────────────────────────────────────────────
    # 收集每个标题起始行的索引
    heading_indices: list[int] = []
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("## ") or stripped.startswith("### "):
            heading_indices.append(i)

    sections: list[str] = []
    if heading_indices:
        # 有标题结构 → 按标题分块
        boundaries = heading_indices + [len(lines)]
        for idx in range(len(heading_indices)):
            start = boundaries[idx]
            end = boundaries[idx + 1]
            block = "".join(lines[start:end]).strip()
            if block:
                sections.append(block)
        # 第一个标题之前的前言内容也纳入
        if heading_indices[0] > 0:
            preamble = "".join(lines[:heading_indices[0]]).strip()
            if preamble:
                sections.insert(0, preamble)
    else:
        # 无标题结构 → 整体视为一个大块，后续按字数切
        sections = [text.strip()] if text.strip() else []

    # ── 过大的块按字数进一步切分 ─────────────────────────────────────────────
    chunks: list[str] = []
    for section in sections:
        if len(section) <= _CHUNK_MAX_CHARS:
            chunks.append(section)
            continue
        # 先尝试按段落（双换行）切分
        paras = re.split(r"\n{2,}", section)
        if len(paras) > 1:
            # 有段落分隔 → 积攒到 _CHUNK_TARGET_CHARS
            buf: list[str] = []
            buf_len = 0
            for para in paras:
                para_len = len(para)
                if buf_len + para_len > _CHUNK_TARGET_CHARS and buf:
                    chunks.append("\n\n".join(buf).strip())
                    buf = [para]
                    buf_len = para_len
                else:
                    buf.append(para)
                    buf_len += para_len
            if buf:
                chunks.append("\n\n".join(buf).strip())
        else:
            # 无段落分隔（连续文本）→ 直接按 _CHUNK_TARGET_CHARS 字数硬切
            pos = 0
            while pos < len(section):
                chunks.append(section[pos: pos + _CHUNK_TARGET_CHARS])
                pos += _CHUNK_TARGET_CHARS

    # 过滤空块
    return [c for c in chunks if c.strip()]


async def ingest_one(md_path: Path, backend: PgBackend) -> int:
    """Ingest one MD file. Returns KU count registered, -1 on skip, 0 on empty."""
    json_path = md_path.with_suffix(".json")
    if not json_path.exists():
        logger.warning("auto_ingest: no sidecar JSON for %s, skip", md_path.name)
        return -1

    try:
        meta = json.loads(await asyncio.to_thread(json_path.read_text, encoding="utf-8"))
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

    # 书级去重: 同 title 已成功摄取 → 跳过(防止同书不同 chunk-ID 重复摄取)
    existing = await backend.get_substrate_id_by_title(title)
    if existing:
        logger.info(
            "auto_ingest: title already ingested as %s — skip duplicate %s (%s)",
            existing[:8], substrate_id[:8], title[:40],
        )
        return -1

    def _load_text() -> str:
        raw = md_path.read_text(encoding="utf-8", errors="replace")
        return _strip_omitted_lines(raw).strip()

    text = await asyncio.to_thread(_load_text)
    subject = await _infer_subject_async(title)
    if not text:
        logger.warning("auto_ingest: empty content %s, marking done (0 KUs)", md_path.name)
        await backend.mark_substrate_ingested(substrate_id, title, medium, 0, subject=subject)
        return 0

    grade_cap = _MEDIUM_GRADE_CAP.get(medium)
    provider = _MEDIUM_PROVIDER.get(medium, "default")
    doc_type = _MEDIUM_DOC_TYPE.get(medium, "science")

    # ── Step 1: KU 抽取 (分块版，修复整书全文一次塞LLM只抽7-12条病根) ────
    chunks = _split_text_into_chunks(text)
    logger.info(
        "auto_ingest: %s → %d chunk(s) (total %d chars)",
        title[:50], len(chunks), len(text),
    )

    engine = KuIngestionEngine(backend)
    registered_ids_all: list[str] = []
    chunk_errors = 0

    for chunk_idx, chunk_text in enumerate(chunks):
        try:
            chunk_result = await engine.ingest(
                text=chunk_text,
                project_id=substrate_id,
                substrate_id=substrate_id,
                grade_cap=grade_cap,
                provider=provider,
                skip_reflux=True,  # 全部 chunk 完成后统一跑一次 reflux
            )
            chunk_ku_ids = [str(kid) for kid in chunk_result.get("registered", []) if kid]
            registered_ids_all.extend(chunk_ku_ids)
            logger.info(
                "auto_ingest: chunk %d/%d → %d KUs (title=%s)",
                chunk_idx + 1, len(chunks), len(chunk_ku_ids), title[:30],
            )
        except Exception:
            logger.exception(
                "auto_ingest: chunk %d/%d failed for %s (non-fatal, continue)",
                chunk_idx + 1, len(chunks), md_path.name,
            )
            chunk_errors += 1

    # 统一跑一次 reflux (全量 KU)
    if registered_ids_all:
        from omodul.knowledge_reflux import run_reflux, KnowledgeRefluxConfig
        import asyncio as _asyncio
        loop = _asyncio.get_event_loop()
        try:
            _rc = KnowledgeRefluxConfig(backend=backend)
            await loop.run_in_executor(None, lambda: run_reflux(_rc, {}))
        except Exception as _re:
            logger.warning("auto_ingest: reflux failed for %s (non-fatal): %s", title[:40], _re)

    ku_count = len(registered_ids_all)
    await backend.mark_substrate_ingested(substrate_id, title, medium, ku_count, subject=subject)
    logger.info(
        "auto_ingest: %s medium=%s provider=%s grade_cap=%s chunks=%d chunk_errors=%d → %d KUs total",
        title[:50], medium, provider, grade_cap, len(chunks), chunk_errors, ku_count,
    )

    if ku_count == 0:
        return 0

    registered_ids = registered_ids_all

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
