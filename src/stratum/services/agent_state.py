"""Agent State Manager — Post-it 协议实现.

对标 My Brain Is Full Crew 的 Agent Post-it 协议:
  - 每个 Agent 有一个私有状态文件 (Meta/states/{agent-name}.md)
  - 每次执行前读取，结束时写入
  - 最大 30 行，覆盖式更新
  - 用于跨调用保持上下文

Stratum 映射:
  - Agent 名称 → service 名称 (graph_builder, layer_generator, ku_pipeline 等)
  - 状态文件 → 轻量级 JSON + Markdown 双格式
  - 持久化路径 → ~/.stratum/Meta/states/{service_name}.json
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────

STATES_DIR = Path.home() / ".stratum" / "Meta" / "states"
MAX_LINES = 30


@dataclass
class AgentState:
    """Agent 的运行时状态."""
    agent_name: str
    last_run: str
    version: int = 1
    data: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    phase: str = ""  # For multi-step flows
    step: int = 0
    context: dict[str, Any] = field(default_factory=dict)


class StateManager:
    """Post-it 协议的状态管理器.

    用法:
        manager = StateManager()

        # Agent 启动时
        state = manager.load_state("graph_builder")

        # Agent 执行中...
        state.data["entities_extracted"] = 42
        state.data["last_substrate_id"] = "sub-123"
        state.notes.append("Found 3 orphan entities in ML cluster")

        # Agent 结束时
        manager.save_state(state)
    """

    def __init__(self, states_dir: Path | None = None):
        self.states_dir = states_dir or STATES_DIR
        self.states_dir.mkdir(parents=True, exist_ok=True)

    def _state_path(self, agent_name: str) -> Path:
        return self.states_dir / f"{agent_name}.json"

    def load_state(self, agent_name: str) -> AgentState:
        """加载 Agent 状态 (启动时读取).

        Args:
            agent_name: Agent 名称 (e.g., "graph_builder", "layer_generator")

        Returns:
            AgentState with previously saved data, or fresh state if none exists.
        """
        path = self._state_path(agent_name)
        if path.exists():
            try:
                data = json.loads(path.read_text())
                state = AgentState(
                    agent_name=data.get("agent_name", agent_name),
                    last_run=data.get("last_run", ""),
                    version=data.get("version", 1),
                    data=data.get("data", {}),
                    notes=data.get("notes", []),
                    phase=data.get("phase", ""),
                    step=data.get("step", 0),
                    context=data.get("context", {}),
                )
                logger.debug("load_state: %s found (version=%d)", agent_name, state.version)
                return state
            except Exception as exc:
                logger.warning("load_state: failed for %s: %s", agent_name, exc)

        # Fresh state
        return AgentState(
            agent_name=agent_name,
            last_run="",
        )

    def save_state(self, state: AgentState) -> None:
        """保存 Agent 状态 (结束时写入).

        Args:
            state: AgentState with updated data.
        """
        state.last_run = datetime.now(timezone.utc).isoformat()
        state.version += 1

        path = self._state_path(state.agent_name)
        data = {
            "agent_name": state.agent_name,
            "last_run": state.last_run,
            "version": state.version,
            "data": state.data,
            "notes": state.notes[-MAX_LINES:],  # Keep max 30 lines
            "phase": state.phase,
            "step": state.step,
            "context": state.context,
        }

        try:
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str))
            logger.debug("save_state: %s v%d", state.agent_name, state.version)
        except Exception as exc:
            logger.warning("save_state: failed for %s: %s", state.agent_name, exc)

    def clear_state(self, agent_name: str) -> bool:
        """清除 Agent 状态 (重置).

        Args:
            agent_name: Agent 名称

        Returns:
            True if state was deleted.
        """
        path = self._state_path(agent_name)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_states(self) -> list[dict[str, Any]]:
        """列出所有 Agent 状态.

        Returns:
            List of state summaries.
        """
        states = []
        for path in sorted(self.states_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text())
                states.append({
                    "agent_name": data.get("agent_name", path.stem),
                    "last_run": data.get("last_run", ""),
                    "version": data.get("version", 0),
                    "phase": data.get("phase", ""),
                    "step": data.get("step", 0),
                    "notes_count": len(data.get("notes", [])),
                })
            except Exception:
                states.append({
                    "agent_name": path.stem,
                    "last_run": "",
                    "version": 0,
                })
        return states

    def get_state_summary(self, agent_name: str) -> dict[str, Any]:
        """获取单个 Agent 的状态摘要 (不加载完整数据).

        Args:
            agent_name: Agent 名称

        Returns:
            State summary dict.
        """
        path = self._state_path(agent_name)
        if not path.exists():
            return {"agent_name": agent_name, "exists": False}

        try:
            data = json.loads(path.read_text())
            return {
                "agent_name": data.get("agent_name", agent_name),
                "exists": True,
                "last_run": data.get("last_run", ""),
                "version": data.get("version", 0),
                "phase": data.get("phase", ""),
                "step": data.get("step", 0),
                "notes_count": len(data.get("notes", [])),
                "data_keys": list(data.get("data", {}).keys()),
            }
        except Exception as exc:
            return {"agent_name": agent_name, "exists": False, "error": str(exc)}


# ── Convenience Functions ─────────────────────────────────────────────────────

_manager = None

def get_manager() -> StateManager:
    global _manager
    if _manager is None:
        _manager = StateManager()
    return _manager


def load_agent_state(agent_name: str) -> AgentState:
    """便捷函数: 加载 Agent 状态."""
    return get_manager().load_state(agent_name)


def save_agent_state(state: AgentState) -> None:
    """便捷函数: 保存 Agent 状态."""
    get_manager().save_state(state)


def update_agent_data(agent_name: str, updates: dict[str, Any]) -> None:
    """便捷函数: 更新 Agent 状态的 data 字段.

    Args:
        agent_name: Agent 名称
        updates: 要合并到 data 的字典
    """
    state = load_agent_state(agent_name)
    state.data.update(updates)
    save_agent_state(state)


def add_agent_note(agent_name: str, note: str) -> None:
    """便捷函数: 添加一条 Agent 笔记.

    Args:
        agent_name: Agent 名称
        note: 笔记内容 (截断到单行)
    """
    state = load_agent_state(agent_name)
    state.notes.append(note.strip()[:200])  # Max 200 chars per note
    save_agent_state(state)


def set_agent_phase(agent_name: str, phase: str, step: int = 0) -> None:
    """便捷函数: 更新 Agent 的当前阶段.

    Args:
        agent_name: Agent 名称
        phase: 当前阶段名称
        step: 阶段内的步骤数
    """
    state = load_agent_state(agent_name)
    state.phase = phase
    state.step = step
    save_agent_state(state)
