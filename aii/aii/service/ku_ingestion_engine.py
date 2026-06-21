import asyncio
import concurrent.futures
import functools
import logging
import os
import re
from typing import Any
import numpy as np

from obase import ProviderRegistry
from oskill.ku_extract_pipeline import ku_extract_pipeline
from omodul.register_ku import register_ku, RegisterKuConfig
from omodul.knowledge_reflux import run_reflux, KnowledgeRefluxConfig
from oprim import vector_encode

from aii.storage.pg_backend import PgBackend

logger = logging.getLogger(__name__)

# ku_extract_pipeline makes HTTP calls to DeepSeek/Ollama (I/O-bound), so a
# ThreadPoolExecutor is sufficient.  ProcessPoolExecutor was causing ~52s OS-level
# fork freezes on WSL2 after CUDA (BGE-M3) was initialised in the parent process.
_EXTRACT_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=1)

# 粗筛阈值: cosine distance (pgvector <=>), 0=完全相同, 2=完全相反
# distance <= 0.15 (similarity >= 0.85) 才触发 LLM 精确确认
DEDUP_COARSE_THRESHOLD: float = float(os.getenv("DEDUP_COARSE_THRESHOLD", "0.15"))


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
            # call_sync_plain: 不带 format=json, 返回自然语言不受 JSON 结构干扰
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

        # 1. Extraction Pipeline — ProcessPoolExecutor (独立进程, 真正绕过 GIL)
        # functools.partial 而非 lambda — ProcessPoolExecutor 需要可 pickle 的 callable
        logger.info(f"Extracting KUs from text (length: {len(text)}) provider={provider}")
        loop = asyncio.get_event_loop()
        extracted = await loop.run_in_executor(
            _EXTRACT_POOL,
            functools.partial(ku_extract_pipeline, text=text, project_id=project_id, provider=provider),
        )

        candidates = extracted.get("candidates", [])
        rejected = extracted.get("rejected", [])

        results = {
            "registered": [],
            "merged": [],       # KU ids that were merged into existing KUs
            "quarantined": [],
            "chunks_processed": extracted.get("chunks_processed", 0),
        }

        # Apply substrate_id + grade_cap before registration
        cap_rank = self._GRADE_RANKS.get(grade_cap, 999) if grade_cap else 999
        for cand in candidates:
            if substrate_id:
                cand["substrate_id"] = substrate_id
            if grade_cap:
                g = cand.get("grade", "unverified")
                if self._GRADE_RANKS.get(g, 0) > cap_rank:
                    cand["grade"] = grade_cap

        # 2. Register Candidates (omodul) with two-level dedup
        config = RegisterKuConfig(backend=self.backend)

        for cand in candidates:
            name = cand.get("name") or cand.get("title", "unnamed")
            natural_text = cand.get("natural_text", "")
            embed_input = f"{name}:{natural_text}"

            logger.info(f"Encoding vector for KU: {name}")
            _ei = embed_input
            embedding = await loop.run_in_executor(
                None, lambda: vector_encode(texts=[_ei], provider="default")
            )
            cand["embedding"] = embedding[0].tolist() if isinstance(embedding, np.ndarray) else embedding[0]

            # ── 两级查重 ──────────────────────────────────────────────────
            existing_ku_id, is_same = await self._dedupe_check(cand, provider=provider)
            if is_same and existing_ku_id:
                # 确认相同 → 合并: 追加来源, 不新建
                try:
                    await self.backend.merge_ku_sources(
                        existing_ku_id,
                        substrate_id=cand.get("substrate_id", ""),
                        natural_text=natural_text,
                    )
                    results["merged"].append(existing_ku_id)
                    logger.info("dedup: merged KU '%s' → existing %s", name[:30], existing_ku_id[:8])
                except Exception as e:
                    logger.error("dedup: merge_ku_sources failed for %s: %s", existing_ku_id[:8], e)
                continue  # 不调 register_ku

            # 不重复 → 正常注册
            try:
                _cand = cand
                await loop.run_in_executor(None, lambda: register_ku(config, {"ku": _cand}))
                results["registered"].append(cand.get("ku_id"))
            except Exception as e:
                logger.error(f"Failed to register KU {name}: {e}")

        # 3. Handle Rejected (Quarantine)
        for rej in rejected:
            ku_id = rej.get("ku_id")
            if ku_id:
                await self.backend.quarantine_ku(ku_id, reason="extraction_rejected")
                results["quarantined"].append(ku_id)

        # 4. Trigger Reflux (omodul)
        if not skip_reflux:
            logger.info("Triggering knowledge reflux for graph completion")
            reflux_config = KnowledgeRefluxConfig(backend=self.backend)
            try:
                _rc = reflux_config
                await loop.run_in_executor(None, lambda: run_reflux(_rc, {}))
            except Exception as e:
                logger.warning(f"Knowledge reflux failed: {e}")

        return results
