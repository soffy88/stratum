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
from pathlib import Path
from typing import Any

import asyncpg
from oprim import vector_encode

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
            reg = await loop.run_in_executor(
                None, lambda: register_ku_ontology(cfg, inp, trail_dir)
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
            content = ku.get("content", "")
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
                         provenance, embedding)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,'unverified',$9,$10,$11)
                    ON CONFLICT (ku_id) DO UPDATE SET
                        natural_text=EXCLUDED.natural_text,
                        knowledge_type=EXCLUDED.knowledge_type,
                        sub_type=EXCLUDED.sub_type,
                        stance_holder=EXCLUDED.stance_holder,
                        example=EXCLUDED.example,
                        embedding=EXCLUDED.embedding
                    """,
                    _ns(ku_id), substrate_id,
                    ku.get("title"), content,
                    ku.get("knowledge_type"),
                    ku.get("sub_type") or None,
                    ku.get("stance_holder") or None,
                    ku.get("example") or None,
                    json.dumps({"method": "default"}),
                    json.dumps({"chunk": ku.get("_chunk"), "extractor": "ontology_extract"}),
                    _emb,
                )
                stats["registered"] += 1

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

        return stats
    finally:
        await conn.close()
