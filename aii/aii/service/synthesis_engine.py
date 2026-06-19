import logging
from typing import Any

from oprim import epistemic_confidence_compute as ecc_fn
from oprim import failure_lesson_extract
from obase import ProviderRegistry
from aii.storage.pg_backend import PgBackend

logger = logging.getLogger(__name__)

# Strong global triggers: always route to Global regardless of other keywords
_GLOBAL_STRONG = ["什么关系", "关系是", "总结", "综述", "概括", "全书", "脉络", "体系"]
# Weak global triggers: route to Global only if no local keyword also present
_GLOBAL_WEAK = ["之间", "综合", "整体", "全局", "哪些", "族"]
# Local-intent (specific concept) triggers (override weak global only)
_LOCAL_KW = ["是什么", "怎么", "怎样", "公式", "证明", "怎么样", "能不能", "定义"]


def _embed_query(query: str) -> list[float] | None:
    """Embed query text using registered embedding provider."""
    try:
        reg = ProviderRegistry.get()
        embed_fn = reg._generic.get("embedding", {}).get("default")
        if embed_fn is None:
            return None
        import numpy as np
        vecs = embed_fn([query])
        arr = np.array(vecs, dtype="float32")
        norm = float(np.linalg.norm(arr[0]))
        return [float(x) / norm for x in arr[0]] if norm > 0 else [float(x) for x in arr[0]]
    except Exception as e:
        logger.error("embed_query failed: %s", e)
        return None


class SynthesisEngine:
    """Dialog engine for AII, routing intents and computing epistemic confidence."""

    def __init__(self, backend: PgBackend):
        self.backend = backend

    async def chat(self, message: str) -> dict[str, Any]:
        """Process a user message. Routes to Local (detail KU) or Global (synthesis KU) path."""
        has_strong_global = any(kw in message for kw in _GLOBAL_STRONG)
        has_weak_global = any(kw in message for kw in _GLOBAL_WEAK)
        has_local = any(kw in message for kw in _LOCAL_KW)
        is_global = has_strong_global or (has_weak_global and not has_local)
        if is_global:
            return await self._handle_global(message)
        if has_local or any(kw in message for kw in ["靠谱吗", "？", "?", "建议"]):
            return await self._handle_grounded(message)
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

    async def _handle_global(self, query: str) -> dict[str, Any]:
        """Global path: search synthesis KUs + 1-hop graph expansion for relational/overview questions."""
        qv = _embed_query(query)
        if qv is None:
            return {"mode": "error", "answer": "内部错误：无法编码查询", "epistemic_confidence": 0.0}

        # 1. Vector search on is_synthesis KUs
        synthesis_results = await self.backend.search_synthesis_kus(qv, limit=3)

        # 2. 1-hop graph expansion from top synthesis KU's source KUs
        extra_ku_ids: set[str] = set()
        if synthesis_results:
            all_edges = await self.backend.get_relation_edges()
            top_id = str(synthesis_results[0]["ku_id"])
            for e in all_edges:
                if str(e["src_id"]) == top_id or str(e["dst_id"]) == top_id:
                    extra_ku_ids.add(str(e["src_id"]))
                    extra_ku_ids.add(str(e["dst_id"]))

        # Fetch related detail KUs
        graph_kus: list[dict] = []
        if extra_ku_ids:
            all_kus = await self.backend.list_kus()
            ku_by_id = {str(ku["ku_id"]): ku for ku in all_kus}
            graph_kus = [ku_by_id[kid] for kid in extra_ku_ids if kid in ku_by_id and not ku_by_id[kid].get("is_synthesis")]

        # Merge: synthesis KUs first, then graph-expanded detail KUs (dedup)
        context = list(synthesis_results)
        seen_ids = {str(r["ku_id"]) for r in context}
        for ku in graph_kus[:3]:
            if str(ku["ku_id"]) not in seen_ids:
                context.append(ku)
                seen_ids.add(str(ku["ku_id"]))

        if not context:
            return {
                "mode": "no_knowledge",
                "answer": "抱歉，知识库中尚未有相关综合摘要，请先完成知识摄入。",
                "epistemic_confidence": 0.0,
                "citations": [],
            }

        grades = [r.get("grade", "unverified") for r in context]
        try:
            confidence = ecc_fn(grades=grades)
        except Exception:
            confidence = 0.3

        answer = await self._call_deepseek(query, context)
        return {
            "mode": "global",
            "answer": answer,
            "epistemic_confidence": confidence,
            "citations": [
                {
                    "ku_id": str(r["ku_id"]),
                    "grade": r.get("grade"),
                    "is_synthesis": bool(r.get("is_synthesis")),
                    "snippet": r.get("natural_text", "")[:100],
                } for r in context
            ],
            "confidence_basis": f"全局摘要检索 + 图谱扩展，共 {len(context)} 条上下文",
            "disclaimer": "本回答基于 AII 综合摘要，非原文断言，仅供参考。",
        }

    async def _handle_grounded(self, query: str) -> dict[str, Any]:
        """Handle questions requiring knowledge base grounding (Local path, detail KUs)."""
        # Check known blind spots before KB search (pure stats lookup)
        blind_spots = await self._get_known_blind_spots()
        is_known_blind_spot = any(bs in query or query[:30] in bs for bs in blind_spots)

        qv = _embed_query(query)
        if qv is None:
            return {
                "mode": "error",
                "answer": "内部错误：无法编码查询",
                "epistemic_confidence": 0.0,
            }

        # Search DB (detail KUs only)
        results = await self.backend.search_ku_by_vector(qv, limit=3)

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
        """Call DeepSeek via the registered async LLM callable."""
        try:
            llm = ProviderRegistry.get().llm("default")
        except Exception as e:
            logger.warning(f"LLM provider not found: {e}")
            return "(MOCK) LLM provider not configured."

        system_prompt = "你是一个严谨的 AI 助手。请基于以下知识回答问题。如果知识未提及，请说不知道。不要给出投资建议。\n\n"
        for i, ku in enumerate(context):
            system_prompt += f"[{i+1}] {ku.get('natural_text')}\n"

        try:
            resp = await llm(
                messages=[{"role": "user", "content": query}],
                system=system_prompt,
                max_tokens=2048,
            )
            for block in resp.get("content", []):
                if isinstance(block, dict) and block.get("type") == "text":
                    return block["text"].strip()
            return ""
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return f"(LLM_ERROR) {e}"

