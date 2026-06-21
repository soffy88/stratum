"""RelationEngine — 关系抽取编排 (P-AII-3 / K-AII-3).

两步流水线:
  1. 规则抽取 (relation_extract_rule): 确定性, 有溯源证据, grade 由 confidence_signal 映射
  2. LLM 兜底 (relation_extract_llm): 软关系, grade 硬编码 unverified (RelationResult.__post_init__)

命门:
  - LLM 边 grade 永远 unverified (RelationResult 强制)
  - 规则边 grade 由 confidence_signal 决定, 最高 medium
  - 无关系不硬造 (target_ref 未能解析到已知 KU 时跳过)
  - LLM 出错不中断, 记警告继续
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from obase import ProviderRegistry
from oprim import relation_extract_rule
from oprim._aii_graph_types import RelationCandidate, RelationResult
from oskill import relation_extract_llm

from aii.storage.pg_backend import PgBackend


logger = logging.getLogger(__name__)

# confidence_signal → edge grade 映射 (规则边, 最高 moderate)
_SIGNAL_GRADE: dict[str, str] = {
    "rule_match":  "moderate",
    "symbol_dep":  "moderate",
    "citation":    "low",
    "ambiguous":   "low",
}


def _resolve_target(target_ref: str, ku_by_id: dict[str, dict], ku_by_text: dict[str, str]) -> str | None:
    """解析 target_ref 到已知 KU 的 ku_id 字符串, 未命中返回 None."""
    if target_ref in ku_by_id:
        return target_ref
    lower = target_ref.lower()
    for text_fragment, kid in ku_by_text.items():
        if lower in text_fragment or text_fragment in lower:
            return kid
    return None


class RelationEngine:
    """Orchestrates relation extraction for a set of KUs."""

    def __init__(self, backend: PgBackend):
        self.backend = backend

    def extract_relations_for_book(self, ku_ids: list[str], provider: str = "default") -> dict[str, Any]:
        """同步入口; 在现有事件循环内调用时走线程."""
        try:
            asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                return ex.submit(asyncio.run, self._extract_async(ku_ids, provider=provider)).result()
        except RuntimeError:
            return asyncio.run(self._extract_async(ku_ids, provider=provider))

    async def extract_relations_async(self, ku_ids: list[str], provider: str = "default") -> dict[str, Any]:
        """异步公开入口; 供 ingest_one 等 async 调用者直接 await."""
        return await self._extract_async(ku_ids, provider=provider)

    async def _extract_async(self, ku_ids: list[str], provider: str = "default") -> dict[str, Any]:
        # ── 加载 KU 数据 ──────────────────────────────────────────────────
        all_kus = await self.backend.list_kus()
        ku_map: dict[str, dict] = {str(ku["ku_id"]): ku for ku in all_kus}

        # 只处理指定 ku_ids 中存在于库的
        ku_ids = [kid for kid in ku_ids if kid in ku_map]
        if not ku_ids:
            return {"rule_edges": 0, "llm_edges": 0, "skipped": 0, "total": 0}

        # 用于 target_ref 解析: {lower_text_fragment: ku_id}
        ku_by_text: dict[str, str] = {}
        for kid, ku in ku_map.items():
            text = (ku.get("natural_text") or "")[:80].lower()
            if text:
                ku_by_text[text] = kid

        known_entities = [
            (ku_map[kid].get("natural_text") or "")[:40]
            for kid in ku_ids
        ]

        rule_edges = 0
        llm_edges = 0
        skipped = 0

        # ── Step 1: 规则抽取 ─────────────────────────────────────────────
        logger.info("RelationEngine Step1: rule extraction for %d KUs", len(ku_ids))
        for src_id in ku_ids:
            ku = ku_map[src_id]
            ku_text = ku.get("natural_text") or ""
            ku_symbolic = ku.get("symbolic_form") if isinstance(ku.get("symbolic_form"), dict) else None

            try:
                candidates: list[RelationCandidate] = relation_extract_rule(
                    ku_text=ku_text,
                    ku_symbolic=ku_symbolic,
                    known_entities=known_entities,
                )
            except Exception as e:
                logger.warning("rule extraction failed for %s: %s", src_id[:8], e)
                continue

            for cand in candidates:
                dst_id = _resolve_target(cand.target_ref, ku_map, ku_by_text)
                if dst_id is None or dst_id == src_id:
                    skipped += 1
                    continue
                grade = _SIGNAL_GRADE.get(cand.confidence_signal, "low")
                try:
                    await self.backend.add_relation_edge(
                        src_id=src_id,
                        relation_type=cand.relation_type,
                        dst_id=dst_id,
                        grade=grade,
                        evidence={"text": cand.evidence, "signal": cand.confidence_signal},
                        extraction_method="rule",
                    )
                    rule_edges += 1
                except Exception as e:
                    logger.warning("edge write failed: %s", e)

        # ── Step 2: LLM 兜底 (pairwise near-neighbor) ────────────────────
        logger.info("RelationEngine Step2: LLM extraction for %d KU pairs", len(ku_ids))
        llm = None
        try:
            llm = ProviderRegistry.get().llm(provider)
        except Exception as e:
            logger.warning("LLM provider not available, skipping LLM step: %s", e)

        if llm is not None:
            # 对每对 (i, j), i<j, 仅测试相邻对避免 O(n²) 爆炸
            pairs = [(ku_ids[i], ku_ids[i + 1]) for i in range(len(ku_ids) - 1)]
            # 也加跨组对 (0,2), (1,3) 等
            if len(ku_ids) >= 3:
                pairs += [(ku_ids[i], ku_ids[i + 2]) for i in range(len(ku_ids) - 2)]
            seen_pairs: set[frozenset] = set()
            for src_id, dst_id in pairs:
                pair_key = frozenset([src_id, dst_id])
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                ku_a = ku_map[src_id]
                ku_b = ku_map[dst_id]
                try:
                    result: RelationResult | None = await relation_extract_llm(
                        ku_a={"ku_id": src_id, "natural_text": ku_a.get("natural_text", "")},
                        ku_b={"ku_id": dst_id, "natural_text": ku_b.get("natural_text", "")},
                        llm=llm,
                    )
                    if result is None:
                        continue
                    if not result.relation_type:
                        continue  # LLM determined no relationship exists; null type must not be written
                    # result.grade is hardcoded "unverified" by RelationResult.__post_init__
                    await self.backend.add_relation_edge(
                        src_id=src_id if result.direction in ("a_to_b", "bidirectional") else dst_id,
                        relation_type=result.relation_type,
                        dst_id=dst_id if result.direction in ("a_to_b", "bidirectional") else src_id,
                        grade=result.grade,  # always "unverified"
                        evidence={"rationale": result.rationale, "direction": result.direction},
                        extraction_method="llm",
                    )
                    llm_edges += 1
                except Exception as e:
                    logger.warning("LLM relation extract failed for pair (%s, %s): %s",
                                   src_id[:8], dst_id[:8], e)

        total = rule_edges + llm_edges
        logger.info("RelationEngine done: rule=%d llm=%d skipped=%d total=%d",
                    rule_edges, llm_edges, skipped, total)
        return {
            "rule_edges": rule_edges,
            "llm_edges": llm_edges,
            "skipped": skipped,
            "total": total,
        }
