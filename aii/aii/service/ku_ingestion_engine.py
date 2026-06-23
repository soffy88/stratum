import asyncio
import logging
import os
import uuid as _uuid
from typing import Any
import numpy as np

from obase import ProviderRegistry
from omodul.register_ku import register_ku, RegisterKuConfig
from omodul.knowledge_reflux import run_reflux, KnowledgeRefluxConfig
from oprim import vector_encode

from aii.storage.pg_backend import PgBackend

logger = logging.getLogger(__name__)

# 粗筛阈值: cosine distance (pgvector <=>), 0=完全相同, 2=完全相反
# distance <= 0.15 (similarity >= 0.85) 才触发 LLM 精确确认
DEDUP_COARSE_THRESHOLD: float = float(os.getenv("DEDUP_COARSE_THRESHOLD", "0.15"))

# 矛盾候选池阈值: cosine distance <= 0.4 (similarity >= 0.6) 进入矛盾检测
CONFLICT_DISTANCE_THRESHOLD: float = float(os.getenv("CONFLICT_DISTANCE_THRESHOLD", "0.4"))

# two_step_ingest confidence → EpistemicGrade mapping
# "medium" is not a valid EpistemicGrade — map to "moderate"
_CONFIDENCE_TO_GRADE: dict[str, str] = {
    "high": "high",
    "medium": "moderate",
    "low": "low",
}


def _convert_ku_candidates(ku_candidates: list[dict], substrate_id: str = "") -> list[dict]:
    """Map two_step_ingest ku_candidates format to ingestion pipeline format."""
    result = []
    for kc in ku_candidates:
        natural_text = kc.get("content", "").strip()
        if not natural_text:
            continue
        confidence = kc.get("confidence", "low")
        grade = _CONFIDENCE_TO_GRADE.get(confidence, "unverified")
        result.append({
            # Pre-assign clean UUID so register_ku uses it instead of generating "KU-{uuid}"
            # (put_ku calls UUID(ku_id) — "KU-" prefix is not a valid hex UUID string)
            "ku_id": str(_uuid.uuid4()),
            "name": kc.get("title", "unnamed"),
            "natural_text": natural_text,
            "knowledge_type": kc.get("type", "observation"),
            "grade": grade,
            "substrate_id": substrate_id,
            # register_ku validates this field exists (not stored in DB; grade column is the store)
            "epistemic_status": {"grade": grade, "source": None, "defeaters": [], "verified": False},
        })
    return result


class KuIngestionEngine:
    """End-to-end Knowledge Unit Ingestion Engine."""

    def __init__(self, backend: PgBackend):
        self.backend = backend

    _GRADE_RANKS: dict[str, int] = {
        "unverified": 0, "low": 1, "moderate": 2, "medium": 2,
        "high": 3, "verified": 4, "proven": 5,
    }

    async def _dedupe_check(
        self, cand: dict, provider: str = "default"
    ) -> tuple[str | None, bool]:
        """两级查重:
        ① 粗筛(免费): pgvector 最近邻 distance > COARSE_THRESHOLD → 无重复
        ② LLM精确确认(仅候选触发): 回答 SAME → 合并; DIFFERENT/不确定 → 新建

        守命门: 任何异常/不确定 → 返回 (None, False) 新建, 宁可重复不错合。
        返回: (existing_ku_id, True) = 确认相同; (None, False) = 新建
        """
        embedding = cand.get("embedding")
        if not embedding:
            return None, False

        # ── Level 1: 向量粗筛 (无 LLM, 免费) ─────────────────────────────
        try:
            nearest = await self.backend.find_nearest_ku(embedding, exclude_synthesis=True)
        except Exception as e:
            logger.warning("dedup: find_nearest_ku failed → new KU: %s", e)
            return None, False

        if nearest is None or nearest["distance"] > DEDUP_COARSE_THRESHOLD:
            return None, False  # 无近邻, 直接新建

        # ── Level 2: LLM 精确确认 (仅近邻触发) ──────────────────────────
        text_a = (nearest.get("natural_text") or "")[:300]
        text_b = (cand.get("natural_text") or "")[:300]
        if not text_a or not text_b:
            return None, False

        prompt = (
            "以下两个知识单元是否表达完全相同的知识点？"
            "（不是相关，而是同一个知识）\n"
            f"KU_A: {text_a}\n"
            f"KU_B: {text_b}\n"
            "只回答 SAME 或 DIFFERENT。如有任何不确定，回答 DIFFERENT。"
        )
        try:
            # 查重判断用本地模型(快/免费,SAME/DIFFERENT 够用); 失败降级到 provider
            try:
                llm = ProviderRegistry.get().llm("ollama-local")
            except Exception:
                llm = ProviderRegistry.get().llm(provider)
            caller = getattr(llm, "call_sync_plain", None) or getattr(llm, "call_sync", None) or llm
            loop = asyncio.get_event_loop()
            answer = (await loop.run_in_executor(None, caller, prompt)).strip().upper()
            # 只有明确回答 SAME(且没有 DIFFERENT) 才合并; 其余全部新建
            import re as _re
            tokens = _re.findall(r'\b(SAME|DIFFERENT)\b', answer)
            if tokens and tokens[-1] == "SAME":
                logger.info(
                    "dedup: SAME (dist=%.3f) → merge into %s",
                    nearest["distance"], str(nearest["ku_id"])[:8],
                )
                return str(nearest["ku_id"]), True
            logger.debug(
                "dedup: DIFFERENT (dist=%.3f, tokens=%r, answer=%r) → new KU",
                nearest["distance"], tokens, answer[:40],
            )
        except Exception as e:
            logger.warning("dedup: LLM check failed → DIFFERENT (new KU): %s", e)

        return None, False  # DIFFERENT 或异常 → 新建

    async def _conflict_detect_and_mark(
        self,
        new_ku_id: str,
        new_ku_text: str,
        new_ku_embedding: list[float],
        llm,
    ) -> None:
        """Detect and mark contradicts edges for a newly registered KU.

        Non-blocking: all exceptions caught and logged, never raises.
        ★ Mandate: grade=unverified hardcoded (ConflictPair.__post_init__).
        ★ Mandate: only ADDS contradicts edges — never deletes or modifies KUs.
        ★ Mandate: called AFTER register → conflict never blocks ingestion.
        """
        try:
            from oskill._conflict_resolution import conflict_resolution

            nearby = await self.backend.search_ku_by_vector(new_ku_embedding, limit=5)
            # Conflict candidate pool: same-domain KUs (cosine similarity >= 0.6)
            # Exclude the KU itself (just registered, will appear in results)
            pool = [
                r for r in nearby
                if r.get("distance", 2.0) <= CONFLICT_DISTANCE_THRESHOLD
                and str(r["ku_id"]) != new_ku_id
                and r.get("natural_text")
                and r.get("embedding") is not None
            ]
            if not pool:
                return

            pairs = await conflict_resolution(
                new_ku_texts=[new_ku_text],
                new_ku_embeddings=[new_ku_embedding],
                existing_ku_texts=[r["natural_text"] for r in pool],
                existing_ku_embeddings=[list(r["embedding"]) for r in pool],
                existing_ku_ids=[str(r["ku_id"]) for r in pool],
                llm=llm,
            )
            for pair in pairs:
                await self.backend.add_relation_edge(
                    new_ku_id, "contradicts", pair.existing_ku_id,
                    grade="unverified",
                    evidence={
                        "conflict_type": pair.conflict_type,
                        "severity": pair.severity,
                        "description": pair.description[:200],
                    },
                    extraction_method="conflict_detect",
                )
                logger.info(
                    "conflict: %s contradicts %s (%s, severity=%s)",
                    new_ku_id[:8], pair.existing_ku_id[:8],
                    pair.conflict_type, pair.severity,
                )
        except Exception as e:
            logger.warning(
                "conflict_detect non-blocking failure for %s: %s",
                new_ku_id[:8], e,
            )

    async def ingest(
        self,
        text: str,
        project_id: str = "default",
        substrate_id: str = "",
        grade_cap: str | None = None,
        provider: str = "default",
        skip_reflux: bool = False,
    ) -> dict[str, Any]:
        """Process raw text into knowledge units and store them.

        skip_reflux: set True when caller will run reflux once over the full
        batch (e.g. textbook ingest processes many chunks then refluxes once).
        run_reflux is O(N_graph) individual DB calls so calling it per-chunk
        on a large graph is prohibitively slow.
        """
        from aii.service.auto_ingest import _strip_omitted_lines
        text = _strip_omitted_lines(text).strip()

        # ── Step 0: Two-step CoT extraction (K-G2) ────────────────────────
        # Replaces ku_extract_pipeline (one-shot LLM).
        # Step 1 analysis yields conflict_candidates (耦合点 for Step 2.5).
        # Step 2 generates ku_candidates; prompt locks "do NOT confirm conflicts".
        logger.info(
            "Extracting KUs via two_step_ingest (length=%d, provider=%s)",
            len(text), provider,
        )
        loop = asyncio.get_event_loop()
        llm = ProviderRegistry.get().llm(provider)

        from oskill._two_step_ingest import two_step_ingest
        tsi_result = await two_step_ingest(
            source_text=text,
            existing_ku_summaries=[],
            llm=llm,
        )
        logger.debug(
            "two_step_ingest: entities=%d concepts=%d conflict_hints=%d ku_candidates=%d",
            len(tsi_result.analysis.get("entities", [])),
            len(tsi_result.analysis.get("concepts", [])),
            len(tsi_result.conflict_candidates),
            len(tsi_result.ku_candidates),
        )

        candidates = _convert_ku_candidates(tsi_result.ku_candidates, substrate_id)

        results: dict[str, Any] = {
            "registered": [],
            "merged": [],
            "quarantined": [],
            "chunks_processed": 1,
        }

        # Apply grade_cap before registration
        cap_rank = self._GRADE_RANKS.get(grade_cap, 999) if grade_cap else 999
        for cand in candidates:
            if grade_cap:
                g = cand.get("grade", "unverified")
                if self._GRADE_RANKS.get(g, 0) > cap_rank:
                    cand["grade"] = grade_cap

        # ── Step 1+2: Register candidates with dedup ──────────────────────
        config = RegisterKuConfig(backend=self.backend)

        for cand in candidates:
            name = cand.get("name") or cand.get("title", "unnamed")
            natural_text = cand.get("natural_text", "")
            # ★ embedding 用英文原文算，不受翻译影响（命门）
            embed_input = f"{name}:{natural_text}"

            logger.info("Encoding vector for KU: %s", name)
            _ei = embed_input
            embedding = await loop.run_in_executor(
                None, lambda: vector_encode(texts=[_ei], provider="default")
            )

            # ── 双语翻译: 英文 KU → natural_text_zh ───────────────────────
            # 中文 KU 跳过（natural_text_zh 留空）
            import re as _re
            if not _re.search(r'[一-龥]', natural_text):
                try:
                    from aii.service.ku_translate import translate_ku_to_zh
                    _has_formula = bool(cand.get("symbolic_form"))
                    _zh = await loop.run_in_executor(
                        None, lambda: translate_ku_to_zh(natural_text, _has_formula)
                    )
                    if _zh:
                        cand["natural_text_zh"] = _zh
                except Exception as _te:
                    logger.warning("ku_translate: skip (non-fatal): %s", _te)
            cand["embedding"] = (
                embedding[0].tolist() if isinstance(embedding, np.ndarray) else embedding[0]
            )

            # ── Step 1: Two-level dedup ────────────────────────────────────
            existing_ku_id, is_same = await self._dedupe_check(cand, provider=provider)
            if is_same and existing_ku_id:
                try:
                    await self.backend.merge_ku_sources(
                        existing_ku_id,
                        substrate_id=cand.get("substrate_id", ""),
                        natural_text=natural_text,
                    )
                    results["merged"].append(existing_ku_id)
                    logger.info(
                        "dedup: merged KU '%s' → existing %s",
                        name[:30], existing_ku_id[:8],
                    )
                except Exception as e:
                    logger.error(
                        "dedup: merge_ku_sources failed for %s: %s",
                        existing_ku_id[:8], e,
                    )
                continue

            # ── Step 2: Register new KU ────────────────────────────────────
            # Write complete sources entry before registration so provenance is
            # stored from first insert (命门: 溯源诚实完整).
            from datetime import datetime, timezone as _tz
            cand["sources"] = [{
                "substrate_id": cand.get("substrate_id", ""),
                "natural_text": natural_text[:200],
                "ingested_at": datetime.now(_tz.utc).isoformat(),
            }]

            # register_ku never raises (3O §5.12); check status field for failure.
            try:
                _cand = cand
                reg_result = await loop.run_in_executor(
                    None, lambda: register_ku(config, {"ku": _cand})
                )
            except Exception as e:
                logger.error("Failed to register KU %s: %s", name, e)
                continue
            if reg_result.get("status") != "completed":
                logger.error(
                    "register_ku failed for KU %s: %s", name, reg_result.get("error")
                )
                continue
            new_ku_id = cand.get("ku_id")
            results["registered"].append(new_ku_id)

            # ── Step 2.5: Conflict detection + contradicts edge (K-G1 P-G1) ─
            # ★ new KU registered above → conflict NEVER blocks ingestion.
            # ★ grade=unverified hardcoded in ConflictPair.__post_init__.
            # ★ only adds contradicts edges, never deletes or modifies KUs.
            if new_ku_id and natural_text:
                await self._conflict_detect_and_mark(
                    new_ku_id=new_ku_id,
                    new_ku_text=natural_text,
                    new_ku_embedding=cand["embedding"],
                    llm=llm,
                )

        # ── Step 3: Trigger Reflux (omodul) ───────────────────────────────
        if not skip_reflux:
            logger.info("Triggering knowledge reflux for graph completion")
            reflux_config = KnowledgeRefluxConfig(backend=self.backend)
            try:
                _rc = reflux_config
                await loop.run_in_executor(None, lambda: run_reflux(_rc, {}))
            except Exception as e:
                logger.warning("Knowledge reflux failed: %s", e)

        return results
