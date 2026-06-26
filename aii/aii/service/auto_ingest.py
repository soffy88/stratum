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

段落级完整覆盖 (里程硃1):
  分块降到段落级 (~1500字/块, 逐块逼 LLM 完整抽取不能跳过)
  覆盖率质量门 (里程硃4):
    ku_density = ku_count / (original_chars / 500)
    < 0.3 → 报警 LOW_COVERAGE + 写 low_coverage.json (供飞轮重摄)
    = 0 → 强制报错 ZERO_KU
  标准: 一本书的KU合起来能复现这本书的完整知识

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
import os
import re
from pathlib import Path

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

# 段落级分块参数 (里程硃1: 降到段落级逼 LLM 不能跳过)
# 目标 ~500-800 汉字 ≈ 1500 字符; 确保每块 ≤ 2-3 段落，LLM 必须全部抽取
_CHUNK_TARGET_CHARS: int = 1500
_CHUNK_MAX_CHARS: int = 2500   # 硬上限: 超过强制切分

# 覆盖率质量门参数 (里程硃4)
# ku_density = ku_count / (original_chars / 500) 表示"每500字平均KU条数"
# 0.3 = 30%预期: 期望每500字抽出1条KU, 0.3表示实际达到30%即报警
_QUALITY_DENSITY_ALERT: float = 0.3
_QUALITY_OUTPUT_DIR = Path(os.getenv("FLYWHEEL_OUTPUT_DIR", "/home/soffy/shared/aii-to-stratum"))


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
    """将全书文本按段落级切分，每块单独送 LLM，逼迫完整抽取不能跳过。

    策略 (段落级, 里程硃1):
    1. 优先按 ## / ### 标题切分为 section
    2. 小 section (<80字内容) 向后合并避免空标题chunk
    3. 大 section (>硬上限) 按段落切分到目标大小
    4. 无段落分隔符的连续文本按字数硬切
    5. 目标: 1500字/块 ≈ 500-750汉字 (约2-3个段落), LLM必须全部抽取

    ★ 段落级切分是实现“完整覆盖能复现整本书”的核心手段。
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
    # 先合并过小的 section（解决OCR/PDF转换书大量空 ## 行的问题）
    # section 内容（去掉首行标题后）< _CHUNK_MIN_CONTENT_CHARS 则并入下一个
    _CHUNK_MIN_CONTENT_CHARS = 80
    if len(sections) > 1:
        merged: list[str] = []
        carry = ""
        for sec in sections:
            combined = (carry + "\n\n" + sec).strip() if carry else sec
            # 计算"实质内容"字符数：去掉首行标题行
            body_lines = combined.splitlines()[1:]
            body_chars = sum(len(l) for l in body_lines)
            if body_chars < _CHUNK_MIN_CONTENT_CHARS:
                carry = combined  # 太小，继续往后合并
            else:
                merged.append(combined)
                carry = ""
        if carry:  # 最后一个小块追加到最后一个大块，或单独保留
            if merged:
                merged[-1] = merged[-1] + "\n\n" + carry
            else:
                merged.append(carry)
        sections = merged

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

    return [c for c in chunks if c.strip()]


def _write_quality_alert(
    substrate_id: str,
    title: str,
    ku_count: int,
    original_chars: int,
    alert_type: str,
    density: float = 0.0,
) -> None:
    """将覆盖率过低的书写入 low_coverage.json 供飞轮重摄。非致命。"""
    import json as _json
    from datetime import datetime, timezone
    try:
        _QUALITY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = _QUALITY_OUTPUT_DIR / "low_coverage.json"
        existing: list[dict] = []
        if out_path.exists():
            try:
                existing = _json.loads(out_path.read_text(encoding="utf-8"))
            except Exception:
                existing = []
        existing_ids = {e.get("substrate_id") for e in existing}
        if substrate_id not in existing_ids:
            existing.append({
                "substrate_id": substrate_id,
                "title": title[:100],
                "ku_count": ku_count,
                "original_chars": original_chars,
                "ku_density": round(density, 4),
                "alert_type": alert_type,
                "detected_at": datetime.now(timezone.utc).isoformat(),
            })
            out_path.write_text(
                _json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
            )
    except Exception as _e:
        logger.warning("quality_alert: write failed (non-fatal): %s", _e)

async def _run_ontology_path(
    backend: PgBackend, substrate_id: str, text: str, title: str,
    medium: str, doc_type: str, provider: str, subject: str,
) -> int:
    """onto 正式路径 (USE_ONTOLOGY): 抽取→持久化→语义归一→跨块连接→KC(Louvain).

    复用已验证模块, 不重新发明. 旧路径在 ingest_one 下方保留可回退.
    """
    from obase import ProviderRegistry
    from oskill import ontology_extract
    from aii.service import onto_prompts as P
    from aii.service.onto_persist import persist_ontology_result
    from aii.service.concept_onto_ops import vectorize_and_normalize
    from aii.service.cross_chunk_link import gen_candidates, judge_and_link
    from aii.service.kc_cluster import cluster_and_persist
    import asyncpg

    llm = ProviderRegistry.get().llm(provider)  # 默认 flash; Step4/5 固定用它(量大/容错/省钱)
    # ★按步分模型预留: 默认全 flash(实测够用). Step1 抽取可单独切 pro:
    #   设 STEP1_MODEL=deepseek-pro → Step1 走 pro; 不设 → 随 provider(flash). 不强制切.
    _step1_model = os.getenv("STEP1_MODEL")
    step1_llm = ProviderRegistry.get().llm(_step1_model) if _step1_model else llm
    source_credibility = "high" if doc_type == "textbook" else "medium"
    trail_dir = Path("/tmp") / "onto_trails"
    trail_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: ontology_extract (主库两遍法/六分类) + AII Layer-4 判据 prompt 注入
    from aii.service import onto_vocab as V
    result = await ontology_extract(
        source_text=text, llm=step1_llm, doc_type=doc_type, source_credibility=source_credibility,
        pass1_chunk_tmpl=P.PASS1_CHUNK_TMPL, pass1_chunk_system=P.PASS1_CHUNK_SYSTEM,
        pass1_outline_tmpl=P.PASS1_OUTLINE_TMPL, pass1_outline_system=P.PASS1_OUTLINE_SYSTEM,
        pass2_chunk_tmpl=P.PASS2_CHUNK_TMPL, pass2_system=P.PASS2_SYSTEM,
        valid_knowledge_types=V.VALID_KNOWLEDGE_TYPES,  # ★注入 AII 词表(含 rationale)
        valid_sub_types=V.VALID_SUB_TYPES,
        valid_relation_types=V.VALID_RELATION_TYPES,
    )
    # Step 2: 持久化 (过 register_ku_ontology 校验) → ku_onto/edge_onto/concept_onto
    pstats = await persist_ontology_result(
        dsn=backend.dsn, substrate_id=substrate_id, result=result,
        trail_dir=trail_dir, backend=backend)
    ku_count = pstats.get("registered", 0)

    conn = await asyncpg.connect(backend.dsn)
    try:
        from pgvector.asyncpg import register_vector
        await register_vector(conn)
        # Step 3: 概念语义归一 (向量筛候选 + LLM 判同一才合, 治反义误并)
        nstats = await vectorize_and_normalize(
            conn, llm, substrate_id=substrate_id, discipline=(subject or "general"))
        # Step 4: 跨块连接 (概念/语义筛候选 → LLM 判真关系 → 连真边)
        cands = await gen_candidates(conn, substrate_id=substrate_id, sem_threshold=0.80)
        cstats = await judge_and_link(conn, llm, cands, substrate_id=substrate_id)
        # Step 5: KC 聚类 (★Louvain res>=1.0, 不用 community_cluster/连通分量) → kc_onto
        kstats = await cluster_and_persist(conn, llm, substrate_id=substrate_id, resolution=1.0)
    finally:
        await conn.close()

    await backend.mark_substrate_ingested(substrate_id, title, medium, ku_count, subject=subject)
    logger.info(
        "auto_ingest[onto]: %s → KU=%d 归一=%d→%d 跨块边=%d/%d候选 KC=%d社区%s",
        title[:40], ku_count, nstats.get("before", 0), nstats.get("after", 0),
        cstats.get("linked", 0), cstats.get("candidates", 0),
        kstats.get("communities", 0), kstats.get("sizes", []),
    )
    return ku_count


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

    # ★md 交付合格性自检 (飞轮入口质量门, AII-STRATUM-MD-SPEC-001):
    #   book 章节结构不合格 → 不抽 + 写 rework 请求 → 不标已摄(Stratum 返工后可重入).
    from aii.service.md_quality_check import check_md_quality, write_md_rework
    _q = check_md_quality(text, medium=medium, title=title)
    if not _q["ok"]:
        write_md_rework(substrate_id=substrate_id, file_name=md_path.name, title=title, result=_q)
        logger.warning("auto_ingest: md quality gate FAILED %s (%s) → rework, skip抽取. fails=%s",
                       substrate_id[:8], title[:40], [f["check"] for f in _q["hard_failures"]])
        return -1

    # onto-only: 旧 Step1-4 链路(KuIngestionEngine/RelationEngine/DeepSynthesis)已退役删除, 统一走 onto 路径.
    return await _run_ontology_path(
        backend, substrate_id, text, title, medium, doc_type, provider, subject)

