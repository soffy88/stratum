"""Call Chain Tracker — Dispatcher 风格的链式调用追踪.

对标 My Brain Is Full Crew Dispatcher 的链式调用机制:
  - 调用链追踪: [] → [agent1] → [agent1, agent2] → 最大深度 3
  - 防重复: 同一请求中不重复调用同一 Agent
  - 防循环: A→B→A 循环自动跳过
  - 溢出处理: 超过最大深度时返回结果 + 延迟建议

在 Stratum 中的应用:
  - Mix Retrieval: 防止 KG→Vector→KG 无限循环
  - Pipeline 执行: 追踪 L0→L1→L2→KG→Enrich 的执行链
  - Agent 编排: 为 future agent 系统提供基础

输出:
  - 调用链记录 (list[str])
  - 当前深度和最大深度
  - 每个步骤的耗时和状态
  - 溢出时的延迟建议列表
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

MAX_CHAIN_DEPTH = 3
DEFAULT_TIMEOUT = 300.0  # 5 minutes max for entire chain


@dataclass
class ChainStep:
    """链式调用中的单步记录."""
    agent_name: str
    status: str  # "running" | "completed" | "skipped" | "failed"
    start_time: float
    end_time: float | None = None
    elapsed_ms: float | None = None
    result_summary: str = ""
    suggestion: str | None = None  # Next agent suggested by this step


@dataclass
class CallChain:
    """完整的调用链记录."""
    chain_id: str
    chain: list[str]
    steps: list[ChainStep]
    max_depth: int
    current_depth: int
    start_time: float
    total_elapsed_ms: float | None = None
    is_complete: bool = False
    deferred_suggestions: list[str] = field(default_factory=list)
    overflow: bool = False


class ChainTracker:
    """调用链追踪器.

    用法:
        tracker = ChainTracker()

        # 执行一个 Agent
        result = tracker.execute(
            agent_name="mix_retrieval",
            fn=lambda: mix_retrieve(query, embedding, mode="mix"),
        )

        # 检查是否可以链式调用下一个
        if tracker.can_chain("graph_health"):
            next_result = tracker.execute("graph_health", compute_graph_health)

        # 完成
        report = tracker.finish()
    """

    def __init__(
        self,
        max_depth: int = MAX_CHAIN_DEPTH,
        chain_id: str | None = None,
    ):
        self.chain_id = chain_id or uuid.uuid4().hex[:12]
        self.max_depth = max_depth
        self.chain: list[str] = []
        self.steps: list[ChainStep] = []
        self.start_time = time.time()
        self.deferred_suggestions: list[str] = []

    @property
    def current_depth(self) -> int:
        return len(self.chain)

    @property
    def is_full(self) -> bool:
        return self.current_depth >= self.max_depth

    @property
    def can_chain_any(self) -> bool:
        return not self.is_full

    def can_chain(self, agent_name: str) -> bool:
        """检查是否可以链式调用指定 Agent.

        Args:
            agent_name: 要调用的 Agent 名称

        Returns:
            True if:
              - Depth < max_depth
              - Agent not already in chain (no duplicates)
              - Agent not in circular pattern
        """
        if self.is_full:
            return False

        # No duplicates
        if agent_name in self.chain:
            return False

        # Check for circular patterns (A→B→A)
        if len(self.chain) >= 2:
            last_two = self.chain[-2:]
            if agent_name == last_two[0]:
                return False

        return True

    def execute(
        self,
        agent_name: str,
        fn: Callable,
        *args,
        timeout: float = DEFAULT_TIMEOUT,
        **kwargs,
    ) -> Any | None:
        """执行一个 Agent 并追踪调用链.

        Args:
            agent_name: Agent 名称
            fn: 要执行的函数
            *args, **kwargs: 传递给 fn 的参数
            timeout: 单步超时 (秒)

        Returns:
            Agent 的执行结果, 如果不能链式调用则返回 None.
        """
        # Check if we can chain
        if not self.can_chain(agent_name):
            step = ChainStep(
                agent_name=agent_name,
                status="skipped",
                start_time=time.time(),
                result_summary=f"Skipped: {'depth limit reached' if self.is_full else 'duplicate or circular'}",
                end_time=time.time(),
                elapsed_ms=0,
            )
            self.steps.append(step)
            if self.is_full:
                self.deferred_suggestions.append(
                    f"Delay {agent_name}: max depth {self.max_depth} reached"
                )
            return None

        # Execute with timing
        step = ChainStep(
            agent_name=agent_name,
            status="running",
            start_time=time.time(),
        )

        logger.info(
            "chain[%s]: step %d/%d — %s",
            self.chain_id, self.current_depth + 1, self.max_depth, agent_name,
        )

        try:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(fn, *args, **kwargs)
                result = future.result(timeout=timeout)

            step.status = "completed"
            step.end_time = time.time()
            step.elapsed_ms = round((step.end_time - step.start_time) * 1000, 1)
            step.result_summary = f"OK ({step.elapsed_ms:.0f}ms)"

            # Add to chain
            self.chain.append(agent_name)
            self.steps.append(step)

            return result

        except Exception as exc:
            step.status = "failed"
            step.end_time = time.time()
            step.elapsed_ms = round((step.end_time - step.start_time) * 1000, 1)
            step.result_summary = f"ERROR: {exc}"

            self.steps.append(step)
            logger.error("chain[%s]: %s failed: %s", self.chain_id, agent_name, exc)
            return None

    def suggest_next(self, agent_name: str, reason: str) -> None:
        """记录 Agent 的下一步建议 (不立即执行).

        Args:
            agent_name: 建议的下一个 Agent
            reason: 建议原因
        """
        self.deferred_suggestions.append(f"Suggest {agent_name}: {reason}")

    def finish(self) -> CallChain:
        """完成调用链, 计算总耗时.

        Returns:
            CallChain with final stats.
        """
        total_elapsed = (time.time() - self.start_time) * 1000

        chain = CallChain(
            chain_id=self.chain_id,
            chain=list(self.chain),
            steps=list(self.steps),
            max_depth=self.max_depth,
            current_depth=self.current_depth,
            start_time=self.start_time,
            total_elapsed_ms=round(total_elapsed, 1),
            is_complete=True,
            overflow=self.is_full and len(self.deferred_suggestions) > 0,
            deferred_suggestions=list(self.deferred_suggestions),
        )

        logger.info(
            "chain[%s]: completed depth=%d/%d elapsed=%.0fms overflow=%d",
            self.chain_id, len(self.chain), self.max_depth,
            total_elapsed, len(self.deferred_suggestions),
        )
        return chain

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict."""
        return {
            "chain_id": self.chain_id,
            "chain": list(self.chain),
            "depth": f"{self.current_depth}/{self.max_depth}",
            "steps": [
                {
                    "agent": s.agent_name,
                    "status": s.status,
                    "elapsed_ms": s.elapsed_ms,
                    "summary": s.result_summary,
                }
                for s in self.steps
            ],
            "overflow": self.is_full,
            "deferred": self.deferred_suggestions,
        }


# ── Mix Retrieval Integration ────────────────────────────────────────────────

def mix_retrieve_with_chain(
    query: str,
    query_embedding: list[float],
    mode: str = "mix",
    top_k: int = 10,
    user_id: str | None = None,
    tracker: ChainTracker | None = None,
) -> dict[str, Any]:
    """带调用链追踪的 Mix Retrieval.

    追踪三种检索源的执行链, 防止循环:
      vector → kg → chunk → RRF merge

    Args:
        query: 查询文本
        query_embedding: 查询向量
        mode: 检索模式
        top_k: 返回结果数
        user_id: 用户 ID
        tracker: 外部追踪器 (None 则创建新的)

    Returns:
        带 chain 信息的检索结果.
    """
    from stratum.services.mix_retrieval import (
        _vector_search, _kg_entity_expansion, _chunk_search, _merge_rrf,
    )

    if tracker is None:
        tracker = ChainTracker(chain_id=f"mix-{uuid.uuid4().hex[:8]}")

    sources: dict[str, list] = {}

    if mode in ("vector", "mix"):
        result = tracker.execute("vector_search", _vector_search, query_embedding, top_k * 2)
        if result is not None:
            sources["vector"] = result

    if mode in ("kg", "mix"):
        result = tracker.execute("kg_expansion", _kg_entity_expansion, query, top_k * 2)
        if result is not None:
            sources["kg"] = result

    if mode in ("chunk", "mix"):
        result = tracker.execute("chunk_search", _chunk_search, query_embedding, top_k * 2)
        if result is not None:
            sources["chunk"] = result

    # RRF merge (final step, not tracked as agent)
    merged = _merge_rrf(sources, top_k=top_k) if sources else []

    chain = tracker.finish()

    return {
        "query": query,
        "mode": mode,
        "result_count": len(merged),
        "results": merged,
        "chain": chain.to_dict(),
    }


# ── Pipeline Chain Tracker ───────────────────────────────────────────────────

def execute_pipeline_chain(
    pipeline_name: str,
    steps: list[tuple[str, Callable, tuple, dict]],
    max_depth: int = MAX_CHAIN_DEPTH,
) -> CallChain:
    """执行带调用链追踪的 Pipeline.

    Args:
        pipeline_name: Pipeline 名称
        steps: [(agent_name, fn, args, kwargs), ...]
        max_depth: 最大调用深度

    Returns:
        CallChain 记录.
    """
    tracker = ChainTracker(chain_id=f"pipeline-{pipeline_name}", max_depth=max_depth)

    for agent_name, fn, args, kwargs in steps:
        tracker.execute(agent_name, fn, *args, **kwargs)

    return tracker.finish()
