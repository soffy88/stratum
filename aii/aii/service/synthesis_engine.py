import logging
from typing import Any

from oprim import epistemic_confidence_compute as ecc_fn
from oprim import vector_encode as vector_encode_fn
from oprim import failure_lesson_extract
from obase import ProviderRegistry
from aii.storage.pg_backend import PgBackend

logger = logging.getLogger(__name__)

class SynthesisEngine:
    """Dialog engine for AII, routing intents and computing epistemic confidence."""

    def __init__(self, backend: PgBackend):
        self.backend = backend

    async def chat(self, message: str) -> dict[str, Any]:
        """Process a user message and return a synthesized response."""
        if any(kw in message for kw in ["是什么", "怎么", "靠谱吗", "？", "?", "建议"]):
            return await self._handle_grounded(message)
        else:
            return await self._handle_chitchat(message)

    async def _get_known_blind_spots(self) -> list[str]:
        """Return high_miss_topic strings from the latest gap report (pure stats, no LLM)."""
        try:
            gap = await self.backend.get_latest_capability_gap_async()
            if gap:
                return [t["topic"] for t in gap.get("high_miss_topics", [])]
        except Exception:
            pass
        return []

    async def _handle_grounded(self, query: str) -> dict[str, Any]:
        """Handle questions requiring knowledge base grounding."""
        # Check known blind spots before KB search (pure stats lookup)
        blind_spots = await self._get_known_blind_spots()
        is_known_blind_spot = any(bs in query or query[:30] in bs for bs in blind_spots)

        try:
            qv = vector_encode_fn(texts=[query], provider="default")[0]
        except Exception as e:
            logger.error(f"Vector encoding failed: {e}")
            return {
                "mode": "error",
                "answer": f"内部错误：无法编码查询 ({e})",
                "epistemic_confidence": 0.0
            }

        # Search DB
        results = await self.backend.search_ku_by_vector([float(x) for x in qv], limit=3)

        # 2. No Knowledge Check
        # Threshold: cosine distance > 0.75 (similarity < 0.25); BGE-M3 typical semantic match ~0.65
        if not results or results[0].get("distance", 1.0) > 0.75:
            logger.info(f"No grounding found. Top distance: {results[0].get('distance') if results else 'N/A'}")
            # 记 retrieval_miss，供缺口感知 step5 聚合（旁路，不改 grade）
            try:
                fl = failure_lesson_extract(
                    trigger_type="retrieval_miss",
                    evidence={"query": query},
                    subject_ref=query[:60],
                )
                await self.backend.record_failure_lesson_async(
                    fl.trigger_type, fl.subject_ref, fl.evidence, fl.lesson
                )
            except Exception as e:
                logger.warning(f"Retrieval miss lesson extract failed: {e}")
            return {
                "mode": "no_knowledge",
                "answer": "抱歉，我的知识库中尚未覆盖相关内容，无法为您提供准确解答。",
                "epistemic_confidence": 0.0,
                "citations": [],
                "disclaimer": "AI 的回答基于有限库，当前无可靠依据。"
            }

        # 3. Compute Epistemic Confidence
        grades = [ku.get("grade", "unverified") for ku in results]
        try:
            # FIX: explicit submodule function call
            confidence = ecc_fn(grades=grades)
        except Exception as e:
            logger.error(f"Confidence compute failed: {e}")
            confidence = 0.5

        # 4. Generate Answer via LLM
        answer = await self._call_deepseek(query, results)

        # 盲区诚实暴露：已知盲区主动声明（比硬答可信）
        if is_known_blind_spot:
            answer = f"[提示：此主题是我的已知盲区，知识储量有限，请谨慎参考。]\n\n{answer}"

        return {
            "mode": "grounded",
            "answer": answer,
            "epistemic_confidence": confidence,
            "citations": [
                {
                    "ku_id": str(r["ku_id"]),
                    "grade": r.get("grade"),
                    "snippet": r.get("natural_text", "")[:100]
                } for r in results
            ],
            "confidence_basis": f"基于检索到的 {len(results)} 条记录加权计算 (最高等级: {grades[0] if grades else 'N/A'})",
            "disclaimer": "本回答由 AI 基于内部知识图谱生成，仅供参考。"
        }

    async def _handle_chitchat(self, message: str) -> dict[str, Any]:
        """Handle general chitchat without grounding."""
        answer = await self._call_deepseek(message, [])
        return {
            "mode": "chitchat",
            "answer": answer,
            "epistemic_confidence": 0.0,
            "citations": [],
            "confidence_basis": "非知识查询，无事实依据",
            "disclaimer": "一般对话模式"
        }

    async def _call_deepseek(self, query: str, context: list[dict]) -> str:
        """Call DeepSeek via the registered LLM callable."""
        try:
            llm = ProviderRegistry.get("llm", "default")
        except Exception as e:
            logger.warning(f"LLM provider not found: {e}")
            llm = None

        if not llm or not callable(llm):
            return "(MOCK) LLM provider not configured."

        system_prompt = "你是一个严谨的 AI 助手。请基于以下知识回答问题。如果知识未提及，请说不知道。不要给出投资建议。\n\n"
        for i, ku in enumerate(context):
            system_prompt += f"[{i+1}] {ku.get('natural_text')}\n"

        full_prompt = system_prompt + "\n用户问题：" + query

        try:
            import asyncio as _asyncio
            import concurrent.futures as _cf
            # llm is a sync callable; run in thread to avoid blocking event loop
            loop = _asyncio.get_event_loop()
            with _cf.ThreadPoolExecutor(max_workers=1) as ex:
                answer = await loop.run_in_executor(ex, llm, full_prompt)
            return answer
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return f"(LLM_ERROR) {e}"

