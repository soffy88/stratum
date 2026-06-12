import logging
from typing import Any

from oprim.epistemic_confidence_compute import epistemic_confidence_compute
from obase import ProviderRegistry
from aii.storage.pg_backend import PgBackend
from oprim.vector_encode import vector_encode

logger = logging.getLogger(__name__)

class SynthesisEngine:
    """Dialog engine for AII, routing intents and computing epistemic confidence."""

    def __init__(self, backend: PgBackend):
        self.backend = backend
        # We fetch the LLM provider from the registry as configured in _provider.py
        # It should be registered as a dict with 'api_key', 'base_url', etc.
        try:
            self.llm_config = ProviderRegistry.get("llm", "default")
        except Exception as e:
            logger.warning(f"Failed to load LLM config: {e}")
            self.llm_config = None

    async def chat(self, message: str) -> dict[str, Any]:
        """Process a user message and return a synthesized response."""
        
        # 1. Intent Routing (Rule-based)
        if any(kw in message for kw in ["是什么", "怎么", "靠谱吗", "？", "?", "建议"]):
            return await self._handle_grounded(message)
        else:
            return await self._handle_chitchat(message)

    async def _handle_grounded(self, query: str) -> dict[str, Any]:
        """Handle questions requiring knowledge base grounding."""
        
        # 1. Vector Search
        # We must use the original query string as requested, not Strategy B prefix
        try:
            qv = vector_encode(texts=[query], normalize=True)[0]
        except Exception as e:
            logger.error(f"Vector encoding failed: {e}")
            return {
                "mode": "error",
                "answer": "内部错误：无法编码查询",
                "epistemic_confidence": 0.0
            }

        # Search DB
        results = await self.backend.search_ku_by_vector(list(qv), limit=3)
        
        # 2. No Knowledge Check
        # Threshold check: if top result has distance > 0.5 (similarity < 0.5)
        if not results or results[0].get("distance", 1.0) > 0.5:
            return {
                "mode": "no_knowledge",
                "answer": "抱歉，我的知识库中尚未覆盖相关内容，无法为您提供准确解答。",
                "epistemic_confidence": 0.0,
                "citations": [],
                "disclaimer": "AI 的回答基于有限库，当前无可靠依据。"
            }

        # 3. Compute Epistemic Confidence
        # Uses oprim logic, NOT LLM self-evaluation
        grades = [ku.get("grade", "unverified") for ku in results]
        confidence = epistemic_confidence_compute(grades=grades)

        # 4. Generate Answer via LLM
        answer = await self._call_deepseek(query, results)

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
            "confidence_basis": f"基于检索到的 {len(results)} 条记录加权计算 (包含最高等级: {grades[0] if grades else 'N/A'})",
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
        """Call DeepSeek API using the registered configuration."""
        if not self.llm_config:
            return "(MOCK) LLM provider not configured. This is a simulated response based on context."
        
        # In a real environment, we would use an async HTTP client (like httpx) 
        # to call the DeepSeek API directly or use an openai client.
        # For this test, if httpx is available, we can mock or do a simple call.
        import httpx
        
        api_key = self.llm_config.get("api_key")
        base_url = self.llm_config.get("base_url")
        model = self.llm_config.get("model", "deepseek-chat")
        
        if not api_key or api_key == "your_key_here":
             return "(MOCK) API key missing. Simulated context-aware response."
             
        system_prompt = "你是一个严谨的 AI 助手。请基于以下知识回答问题。如果知识未提及，请说不知道。不要给出投资建议。\n\n"
        for i, ku in enumerate(context):
            system_prompt += f"[{i+1}] {ku.get('natural_text')}\n"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": model, "messages": messages},
                    timeout=10.0
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return f"(LLM_ERROR) Failed to generate response: {e}"
