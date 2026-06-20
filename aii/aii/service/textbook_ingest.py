"""textbook_ingest — Pipeline 2: 中小学教材摄取.

每文件流程:
  1. 读 MD + JSON sidecar → textbook_meta
  2. parse_textbook() → clusters + raw_ku_chunks
  3. 每 chunk: KuIngestionEngine.ingest() (含查重/Mathlib确证,grade_cap=None)
  4. 教学元数据 LLM 注释 → patch provenance JSONB
  5. 顺序 prerequisite_of 边 (同 cluster 内相邻 section 的最后/首个 KU)
  6. RelationEngine.extract_relations_async() 结网 (全量 KU id)
  7. 跨层连接: 为每个教材 KU 找最近高置信 KU → basis_of 边
  8. mark_substrate_ingested (medium="textbook")

红线: grade_cap=None 确保数学定理走 Mathlib 确证链路,一视同仁.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

from aii.service.textbook_parser import parse_textbook
from aii.storage.pg_backend import PgBackend

logger = logging.getLogger(__name__)

_OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
_CROSS_TIER_DISTANCE = float(os.getenv("TEXTBOOK_CROSS_TIER_DISTANCE", "0.30"))
_HIGH_GRADES = {"verified", "proven", "high"}


# ── 教学元数据 LLM 注释 ────────────────────────────────────────────────────────

async def _annotate_edu_meta(text: str, chapter: str, section: str) -> dict:
    """Local Ollama call → educational metadata dict.  Falls back to defaults."""
    import requests as _r
    import re as _re

    prompt = (
        f"为以下教材知识点生成教学元数据，严格以JSON格式回答，不要其他内容:\n"
        f"章节: {chapter} > {section}\n"
        f"内容摘要: {text[:400]}\n\n"
        '返回JSON: {"difficulty":"easy|medium|hard","exam_frequency":"low|medium|high",'
        '"question_types":["calculation","proof","multiple_choice","fill_in"],'
        '"ku_type":"concept|theorem|procedure|formula|example",'
        '"mastery_levels":["recall","understand","apply","analyze"],'
        '"curriculum_standard":"","standard_code":""}'
    )
    defaults = {
        "difficulty": "medium", "exam_frequency": "medium",
        "question_types": [], "ku_type": "concept",
        "mastery_levels": ["recall", "understand"],
        "curriculum_standard": "", "standard_code": "",
    }
    try:
        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(
            None,
            lambda: _r.post(
                f"{_OLLAMA_URL}/api/generate",
                json={"model": "qwen2.5:7b", "prompt": prompt, "stream": False},
                timeout=30,
            ),
        )
        raw = resp.json().get("response", "")
        m = _re.search(r'\{.*\}', raw, _re.DOTALL)
        if m:
            parsed = json.loads(m.group())
            return {**defaults, **parsed}
    except Exception as e:
        logger.warning("textbook_ingest: edu_meta annotation failed: %s", e)
    return defaults


# ── 单 chunk 摄取 ──────────────────────────────────────────────────────────────

async def _ingest_chunk(
    chunk: dict,
    textbook: dict,
    backend: PgBackend,
    provider: str = "default",
) -> list[str]:
    """Ingest one section chunk.  Returns list of registered ku_ids."""
    from aii.service.ku_ingestion_engine import KuIngestionEngine

    textbook_id = textbook["id"]
    text = chunk["text"]
    if not text.strip():
        return []

    # 1. 教学元数据注释 (local Ollama, 非阻塞到主事件循环)
    edu_meta = await _annotate_edu_meta(text, chunk["chapter"], chunk["section"])

    # 2. KU抽取 + 注册 (含查重/Mathlib, grade_cap=None: 数学定理该确证就确证)
    # skip_reflux=True: reflux 是 O(N_graph) 逐 KU 查询, 每 chunk 跑一次代价太高.
    # 调用方 (ingest_one_textbook) 在全量 chunk 完成后统一跑一次 reflux.
    engine = KuIngestionEngine(backend)
    result = await engine.ingest(
        text=text,
        project_id=textbook_id,
        substrate_id=textbook_id,
        grade_cap=None,
        provider=provider,
        skip_reflux=True,
    )
    registered_ids = [str(kid) for kid in result.get("registered", []) if kid]

    if not registered_ids:
        return []

    # 3. Patch provenance JSONB 写入教学元数据
    provenance_patch = json.dumps({
        "textbook_id": textbook_id,
        "cluster_id": chunk["cluster_id"],
        "chapter": chunk["chapter"],
        "section": chunk["section"],
        "school_grade": textbook.get("grade", ""),
        "subject": textbook.get("subject", ""),
        "edition": textbook.get("edition", ""),
        **edu_meta,
    })
    try:
        pool = await backend._ensure_pool()
        async with pool.acquire() as conn:
            for ku_id in registered_ids:
                await conn.execute(
                    """
                    UPDATE aii.ku
                    SET provenance = COALESCE(provenance, '{}'::jsonb) || $1::jsonb,
                        updated_at = NOW()
                    WHERE ku_id = $2::uuid
                    """,
                    provenance_patch, ku_id,
                )
    except Exception as e:
        logger.warning("textbook_ingest: provenance patch failed: %s", e)

    return registered_ids


# ── 顺序 prerequisite_of 边 ────────────────────────────────────────────────────

async def _add_sequential_prerequisites(
    ordered_chunk_ids: list[list[str]],
    backend: PgBackend,
) -> int:
    """Add prerequisite_of edges between consecutive sections.

    ordered_chunk_ids: [[ku_ids for section 0], [ku_ids for section 1], ...]
    Connects last KU of section[i] → prerequisite_of → first KU of section[i+1].
    """
    count = 0
    for i in range(len(ordered_chunk_ids) - 1):
        frm = ordered_chunk_ids[i]
        to = ordered_chunk_ids[i + 1]
        if not frm or not to:
            continue
        src_id, dst_id = frm[-1], to[0]
        try:
            await backend.add_relation_edge(
                src_id=src_id,
                relation_type="prerequisite_of",
                dst_id=dst_id,
                grade="medium",
                evidence={"source": "textbook_section_order", "section_index": i},
                extraction_method="textbook_order",
            )
            count += 1
        except Exception as e:
            logger.warning("textbook_ingest: prereq edge %s→%s failed: %s",
                           src_id[:8], dst_id[:8], e)
    return count


# ── 跨层连接 (高阶KU → basis_of → 教材KU) ─────────────────────────────────────

async def _add_cross_tier_connections(
    ku_ids: list[str],
    textbook_id: str,
    backend: PgBackend,
) -> int:
    """For each textbook KU, find nearest high-grade non-textbook KU → basis_of edge."""
    if not ku_ids:
        return 0

    # 批量取 embedding
    embeddings = await backend.get_ku_embeddings(ku_ids)
    count = 0
    pool = await backend._ensure_pool()

    async with pool.acquire() as conn:
        for ku_id, emb in embeddings.items():
            try:
                row = await conn.fetchrow(
                    """
                    SELECT ku_id::text, grade,
                           (embedding <=> $1) AS distance
                    FROM aii.ku
                    WHERE ku_id != $2::uuid
                      AND is_synthesis = FALSE
                      AND grade = ANY($3)
                      AND embedding IS NOT NULL
                      AND (provenance->>'textbook_id' IS DISTINCT FROM $4)
                    ORDER BY embedding <=> $1
                    LIMIT 1
                    """,
                    emb, ku_id, list(_HIGH_GRADES), textbook_id,
                )
                if row and row["distance"] < _CROSS_TIER_DISTANCE:
                    existing_id = str(row["ku_id"])
                    await backend.add_relation_edge(
                        src_id=existing_id,
                        relation_type="basis_of",
                        dst_id=ku_id,
                        grade="unverified",
                        evidence={
                            "source": "cross_tier_similarity",
                            "distance": round(row["distance"], 4),
                        },
                        extraction_method="cross_tier",
                    )
                    count += 1
            except Exception as e:
                logger.debug("textbook_ingest: cross-tier for %s failed: %s", ku_id[:8], e)

    return count


# ── 主入口 ─────────────────────────────────────────────────────────────────────

async def ingest_one_textbook(
    md_path: str | Path,
    backend: PgBackend | None = None,
    provider: str = "default",
) -> dict[str, Any]:
    """Ingest one textbook MD file (requires paired .json sidecar).

    Returns summary dict with counts.  Creates backend from env if not passed.
    """
    md_path = Path(md_path)
    json_path = md_path.with_suffix(".json")

    if not json_path.exists():
        raise FileNotFoundError(f"textbook_ingest: no sidecar JSON for {md_path.name}")

    textbook_meta: dict = json.loads(
        await asyncio.to_thread(json_path.read_text, encoding="utf-8")
    )
    textbook_id = textbook_meta.get("id", "")
    if not textbook_id:
        raise ValueError(f"textbook_ingest: no 'id' field in {json_path.name}")

    # 如果调用方没传 backend，从 env 创建
    _owns_backend = False
    if backend is None:
        from dotenv import load_dotenv
        load_dotenv(override=True)
        from aii.api._provider import register_providers
        register_providers()
        dsn = os.getenv("DATABASE_URL", "postgresql://aii:aii@localhost:5432/aii_kg")
        backend = PgBackend(dsn=dsn)
        await backend._ensure_pool()
        _owns_backend = True

    # 已摄取则跳过
    if await backend.is_substrate_ingested(textbook_id):
        logger.info("textbook_ingest: already ingested %s, skip", textbook_id)
        return {"status": "skipped", "textbook_id": textbook_id}

    md_text = await asyncio.to_thread(md_path.read_text, encoding="utf-8", errors="replace")
    parsed = parse_textbook(md_text, textbook_meta)
    textbook = parsed["textbook"]
    clusters = parsed["clusters"]
    chunks = parsed["raw_ku_chunks"]

    logger.info(
        "textbook_ingest: %s — %d clusters, %d chunks",
        textbook_id, len(clusters), len(chunks),
    )

    # ── Milestone 2: KU抽取 ────────────────────────────────────────────────
    # 按 cluster 分组, 保留 section 顺序
    cluster_order: dict[str, list[list[str]]] = {}  # cluster_id → [section_ku_ids]
    all_ku_ids: list[str] = []
    total_registered = 0

    for chunk in chunks:
        cid = chunk["cluster_id"]
        chunk_ku_ids = await _ingest_chunk(chunk, textbook, backend, provider=provider)
        all_ku_ids.extend(chunk_ku_ids)
        total_registered += len(chunk_ku_ids)
        cluster_order.setdefault(cid, []).append(chunk_ku_ids)
        logger.info(
            "textbook_ingest: chunk '%s' → %d KUs",
            chunk["section"][:40], len(chunk_ku_ids),
        )

    logger.info("textbook_ingest: total registered %d KUs", total_registered)

    if total_registered == 0:
        await backend.mark_substrate_ingested(
            textbook_id, textbook.get("book_name", md_path.stem),
            "textbook", 0, subject=textbook.get("subject"),
        )
        return {"status": "done", "textbook_id": textbook_id, "ku_count": 0}

    # ── Milestone 3: 依赖关系 ──────────────────────────────────────────────

    # 3a. 顺序 prerequisite_of (同 cluster 内 section 间)
    prereq_count = 0
    for section_chunks_list in cluster_order.values():
        prereq_count += await _add_sequential_prerequisites(section_chunks_list, backend)
    logger.info("textbook_ingest: added %d sequential prerequisite_of edges", prereq_count)

    # 3b. RelationEngine 结网 (规则+LLM 边)
    try:
        from aii.service.relation_engine import RelationEngine
        rel_engine = RelationEngine(backend)
        rel_result = await rel_engine.extract_relations_async(all_ku_ids, provider=provider)
        logger.info(
            "textbook_ingest: RelationEngine → rule=%d llm=%d edges",
            rel_result.get("rule_edges", 0), rel_result.get("llm_edges", 0),
        )
    except Exception:
        logger.exception("textbook_ingest: RelationEngine failed (non-fatal)")

    # 3c. 跨层连接 (高阶 KU → basis_of → 教材 KU)
    cross_count = await _add_cross_tier_connections(all_ku_ids, textbook_id, backend)
    logger.info("textbook_ingest: added %d cross-tier basis_of edges", cross_count)

    # ── 入库标记 ───────────────────────────────────────────────────────────
    await backend.mark_substrate_ingested(
        textbook_id, textbook.get("book_name", md_path.stem),
        "textbook", total_registered, subject=textbook.get("subject"),
    )

    return {
        "status": "done",
        "textbook_id": textbook_id,
        "book_name": textbook.get("book_name"),
        "clusters": len(clusters),
        "chunks_processed": len(chunks),
        "ku_count": total_registered,
        "prereq_edges": prereq_count,
        "cross_tier_edges": cross_count,
    }
