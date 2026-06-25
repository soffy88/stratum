"""DRAFT — ontology persist mapping (extractor dict → _onto tables).

★ 草稿,给 Claude/Owner 过目,尚未接入 auto_ingest。
匹配 pg_backend._put_ku_async 约定: 直连 asyncpg + register_vector + 事务 + 动态 upsert。

数据流 (每条 ku_candidate):
  ontology_extract → ku_candidate dict
    → 组 register_ku_ontology 校验输入 (ku + 它的 edges)
    → run_in_executor 跑校验 (register 是同步函数!)
    → status=='failed' → record_failure_lesson, 跳过不入库
    → status=='completed' → 写 ku_onto + edge_onto + concept_onto/ku_concept_onto

命门:
  - 持久化前必过 register_ku_ontology (四套词表 + grade铁律 + positional 校验)
  - grade 恒 'unverified'; grounded_by 恒 {"method":"default"}
  - same_as 边不写 edge_onto (operad 语义: same_as=合并信号, 非边)
  - intuition/insight/opposing_stance 本次恒 NULL (二期 enrichment)
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

import asyncpg
from oprim import vector_encode

from aii.service import onto_vocab as V

from omodul.register_ku_ontology import (
    register_ku_ontology,
    RegisterKuOntologyConfig,
    RegisterKuOntologyInput,
)


# extractor ku_candidate 键 → ku_onto 列 (1:1 部分)
#   id            → ku_id          (TEXT, operad string id)
#   title         → title          (★ 不是 name; name 在 concept_onto)
#   content       → natural_text
#   knowledge_type→ knowledge_type
#   grade         → grade          (恒 unverified)
#   sub_type      → sub_type       (可 NULL)
#   stance_holder → stance_holder
#   example       → example        (★ TEXT, extractor 产单串, 非 jsonb)
#   concepts      → concept_onto + ku_concept_onto (按名 upsert)
# AII 补的列: substrate_id / provenance / embedding / natural_text_zh
# 本次恒 NULL: intuition / insight / opposing_stance
# 校验需要但 extractor 不产: grounded_by → 注入 {"method":"default"}


def _as_text(v):
    """LLM 偶尔把单串字段(example/title/...)产成 list 或 dict → 入 TEXT 列前归一为字符串.
    list → '; ' 连接(元素递归); dict → 值 '; ' 连接; 标量 → str; None/空 → None."""
    if v is None:
        return None
    if isinstance(v, list):
        v = "; ".join(_as_text(x) or "" for x in v)
    elif isinstance(v, dict):
        v = "; ".join(_as_text(x) or "" for x in v.values())
    elif not isinstance(v, str):
        v = str(v)
    return v or None


async def persist_ontology_result(
    *,
    dsn: str,
    substrate_id: str,
    result: Any,              # OntologyExtractResult
    trail_dir: Path,          # register_ku_ontology 写决策轨迹的目录
    backend: Any,             # PgBackend, 复用 record_failure_lesson_async / vector_encode
) -> dict:
    """持久化一本书的抽取结果到 _onto 表。返回统计 dict。"""
    ku_candidates = list(result.ku_candidates or [])
    edge_candidates = list(result.edge_candidates or [])
    concept_candidates = list(result.concept_candidates or [])

    # 按 source(temp id) 把边分组到各 KU
    edges_by_src: dict[str, list[dict]] = {}
    for e in edge_candidates:
        edges_by_src.setdefault(e.get("source", ""), []).append(e)

    loop = asyncio.get_event_loop()
    stats = {"registered": 0, "rejected": 0, "edges": 0, "concepts": 0,
             "same_as_signals": 0}

    # ★ku_id 按 substrate 命名空间化 (根治跨书碰撞: ku_c0_0 每本从0重启, ku_id 是全局PK)
    ku_temp_ids = {(k.get("id") or k.get("ku_id")) for k in ku_candidates}

    def _ns(tid: str) -> str:
        return f"{substrate_id}::{tid}"

    # ★路A: conceptual KU 定义概念 → 收集其 level/discipline/invariant (概念信息骑定义它的KU)
    # concept_meta[name] = {level, discipline, invariant, disc_conflict:[...]}; 首个非空胜出
    concept_meta: dict[str, dict] = {}

    conn = await asyncpg.connect(dsn)
    try:
        from pgvector.asyncpg import register_vector
        await register_vector(conn)

        # ── 先把全书概念 upsert, 拿 name→concept_id 映射 ───────────────
        concept_id_by_name: dict[str, int] = {}
        all_names = set(concept_candidates)
        for ku in ku_candidates:
            all_names.update(ku.get("concepts", []) or [])
        for name in (n for n in all_names if n):
            cid = await conn.fetchval(
                """
                INSERT INTO aii.concept_onto(name) VALUES($1)
                ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                RETURNING concept_id
                """,
                name,
            )
            concept_id_by_name[name] = cid
            stats["concepts"] += 1

        # ── 逐条 KU: 先过 register 校验, 再入库 ────────────────────────
        for ku in ku_candidates:
            ku_id = ku.get("id") or ku.get("ku_id")
            ku_edges = edges_by_src.get(ku_id, [])

            # 组校验输入 (operad 要 grounded_by 才能过 grade 铁律)
            ku_for_validation = {
                **ku,
                "grade": "unverified",
                "grounded_by": {"method": "default"},
            }
            cfg = RegisterKuOntologyConfig(
                substrate_id=substrate_id,
                knowledge_type=ku.get("knowledge_type", ""),
                db_url=dsn,
            )
            inp = RegisterKuOntologyInput(ku=ku_for_validation, edges=ku_edges)

            # register_ku_ontology 是同步 → executor 包, 不阻塞事件循环
            # ★注入 AII 词表(含 rationale), 校验绑 AII 单一权威, 不用主库默认
            reg = await loop.run_in_executor(
                None, lambda: register_ku_ontology(
                    cfg, inp, trail_dir,
                    valid_knowledge_types=V.VALID_KNOWLEDGE_TYPES,
                    valid_sub_types=V.VALID_SUB_TYPES,
                    valid_grades=V.VALID_GRADES,
                    valid_relation_types=V.VALID_RELATION_TYPES,
                )
            )

            if reg.get("status") != "completed":
                # 校验失败 → 记 failure_lesson, 不入库
                await backend.record_failure_lesson_async(
                    trigger_type="ontology_validation_failed",
                    subject_ref=str(ku_id),
                    evidence={"ku": ku, "errors": reg.get("validation_errors", [])},
                    lesson="; ".join(reg.get("validation_errors", []) or ["unknown"]),
                )
                stats["rejected"] += 1
                continue

            # ── embedding 入库时填 (写 ku_onto 前算, 和旧链路一致) ──────
            content = _as_text(ku.get("content")) or ""
            _emb = (await loop.run_in_executor(
                None, lambda c=content: vector_encode(texts=[c], provider="default")
            ))[0]  # (1,1024) → 取第 0 行; register_vector 后 pgvector 收 np 向量

            # ── 写 ku_onto ───────────────────────────────────────────
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO aii.ku_onto
                        (ku_id, substrate_id, title, natural_text, knowledge_type,
                         sub_type, stance_holder, example, grade, grounded_by,
                         provenance, embedding, natural_text_zh)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,'unverified',$9,$10,$11,$12)
                    ON CONFLICT (ku_id) DO UPDATE SET
                        natural_text=EXCLUDED.natural_text,
                        natural_text_zh=EXCLUDED.natural_text_zh,
                        knowledge_type=EXCLUDED.knowledge_type,
                        sub_type=EXCLUDED.sub_type,
                        stance_holder=EXCLUDED.stance_holder,
                        example=EXCLUDED.example,
                        embedding=EXCLUDED.embedding
                    """,
                    _ns(ku_id), substrate_id,
                    _as_text(ku.get("title")), content,
                    ku.get("knowledge_type"),
                    ku.get("sub_type") or None,
                    _as_text(ku.get("stance_holder")),
                    _as_text(ku.get("example")),
                    json.dumps({"method": "default"}),
                    json.dumps({"chunk": ku.get("_chunk"), "extractor": "ontology_extract"}),
                    _emb,
                    _as_text(ku.get("content_zh")),
                )
                stats["registered"] += 1

                # ★路A: 仅 conceptual KU 且定义了概念 → 收集概念层信息(首个非空)
                if ku.get("knowledge_type") == "conceptual" and ku.get("defines_concept"):
                    nm = ku["defines_concept"]
                    m = concept_meta.setdefault(
                        nm, {"level": None, "discipline": None, "invariant": None, "disc_conflict": []})
                    if m["level"] is None and ku.get("concept_level"):
                        m["level"] = ku["concept_level"]
                    if m["invariant"] is None and ku.get("concept_invariant"):
                        m["invariant"] = ku["concept_invariant"]
                    d = ku.get("concept_discipline")
                    if d:
                        if m["discipline"] is None:
                            m["discipline"] = d
                        elif m["discipline"] != d:
                            m["disc_conflict"].append(d)  # 学科判定冲突 = 信号, 记日志

                # ── 写 ku_concept_onto ──────────────────────────────
                for cname in (ku.get("concepts") or []):
                    cid = concept_id_by_name.get(cname)
                    if cid is None:
                        continue
                    await conn.execute(
                        """
                        INSERT INTO aii.ku_concept_onto(ku_id, concept_id)
                        VALUES ($1,$2) ON CONFLICT DO NOTHING
                        """,
                        _ns(ku_id), cid,
                    )

                # ── 写 edge_onto (same_as 跳过 = 合并信号, 非边) ─────
                for e in ku_edges:
                    rel = e.get("relation_type")
                    if rel == "same_as":
                        # 本次: 仅计数, 不合并不写边 (合并逻辑二期做)
                        stats["same_as_signals"] += 1
                        continue
                    # dst 是 ku 临时 id → 命名空间化; 是概念名 → 保持原样
                    _tgt = e.get("target", "")
                    _dst = _ns(_tgt) if _tgt in ku_temp_ids else _tgt
                    await conn.execute(
                        """
                        INSERT INTO aii.edge_onto
                            (substrate_id, src_id, dst_id, relation_type, extraction_method)
                        VALUES ($1,$2,$3,$4,'llm')
                        """,
                        substrate_id, _ns(ku_id), _dst, rel,
                    )
                    stats["edges"] += 1

        # ── ★路A 写概念层: level/discipline(concept_onto列) + invariant(独立统一表) ──
        # 本性是独立节点: 写 aii.invariant 行(is_concept=false, member=[该概念]), concept.invariant_id 回链.
        # 本性同一(挂载/升 is_concept)由 converge_invariants 负责, 此处只产单本性节点.
        for nm, m in concept_meta.items():
            cid = concept_id_by_name.get(nm)
            if cid is None:
                cid = await conn.fetchval(
                    "INSERT INTO aii.concept_onto(name) VALUES($1) "
                    "ON CONFLICT (name) DO UPDATE SET name=EXCLUDED.name RETURNING concept_id", nm)
                concept_id_by_name[nm] = cid
            if m["disc_conflict"]:
                logger.info("onto_persist[invariant]: discipline 冲突 concept=%r keep=%r others=%r",
                            nm, m["discipline"], m["disc_conflict"])
            # level/discipline 仍是 concept_onto 列, 首个非空胜出
            await conn.execute(
                "UPDATE aii.concept_onto SET level=COALESCE(level,$1), "
                "discipline=COALESCE(discipline,$2) WHERE concept_id=$3",
                m["level"], m["discipline"], cid)
            stats["concept_meta"] = stats.get("concept_meta", 0) + 1
            # 有 invariant 且该概念尚无 invariant_id → 建单本性节点(is_concept=false)并回链
            if m["invariant"]:
                has_inv = await conn.fetchval(
                    "SELECT invariant_id FROM aii.concept_onto WHERE concept_id=$1", cid)
                if has_inv is None:
                    iv = (await loop.run_in_executor(
                        None, lambda t=m["invariant"]: vector_encode(texts=[t], provider="default")))[0]
                    inv_id = await conn.fetchval(
                        """INSERT INTO aii.invariant(statement, vector, member_concept_ids, is_concept)
                           VALUES ($1, $2, $3::jsonb, false) RETURNING id""",
                        m["invariant"], iv, json.dumps([str(cid)]))
                    await conn.execute(
                        "UPDATE aii.concept_onto SET invariant_id=$1 WHERE concept_id=$2", inv_id, cid)
                    stats["invariants"] = stats.get("invariants", 0) + 1

        return stats
    finally:
        await conn.close()
