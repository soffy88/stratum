from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

import pytest

from stratum.services import evidence_brief_mcp


class FakeMCP:
    def __init__(self) -> None:
        self.registered: list[Callable[..., Any]] = []
        self.constructed_runtime = False

    def tool(self) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def capture(function: Callable[..., Any]) -> Callable[..., Any]:
            self.registered.append(function)
            return function

        return capture


def _brief_request(request):
    assert request.query == "black holes"
    assert request.user_id == "user-42"
    assert request.top_k == 3
    assert request.rerank is False
    return {
        "query": request.query,
        "result_count": 1,
        "items": [
            {
                "rank": 1,
                "title": "Source A",
                "quote": "direct evidence",
                "source_id": "source-a",
                "fragment_id": "frag-1",
                "deep_link": "stratum://substrate/source-a#p3",
            }
        ],
        "trajectory_id": "traj-1",
        "authority": "KnowledgeView",
    }


def _expected_brief() -> dict[str, Any]:
    return _brief_request(
        type(
            "Request",
            (),
            {
                "query": "black holes",
                "user_id": "user-42",
                "top_k": 3,
                "rerank": False,
            },
        )()
    )


@pytest.mark.asyncio
async def test_registers_tool_and_propagates_authenticated_user(monkeypatch) -> None:
    mcp = FakeMCP()
    seen: list[str] = []

    def require_user() -> str:
        seen.append("required")
        return "user-42"

    monkeypatch.setattr(evidence_brief_mcp, "build_evidence_brief", _brief_request)
    tool = evidence_brief_mcp.register_evidence_brief_tool(mcp, require_user)

    assert mcp.registered == [tool]
    assert await tool("black holes", top_k=3, rerank=False) == _expected_brief()
    assert seen == ["required"]


@pytest.mark.asyncio
async def test_structured_output_is_unchanged_and_markdown_uses_renderer(monkeypatch) -> None:
    mcp = FakeMCP()
    brief = {"query": "q", "items": [], "authority": "KnowledgeView"}
    monkeypatch.setattr(evidence_brief_mcp, "build_evidence_brief", lambda _request: brief)
    monkeypatch.setattr(
        evidence_brief_mcp,
        "render_evidence_brief_markdown",
        lambda actual: "rendered:" + str(actual),
    )
    tool = evidence_brief_mcp.register_evidence_brief_tool(mcp, lambda: "user-1")

    assert await tool("q") is brief
    assert await tool("q", output_format="markdown") == "rendered:" + str(brief)


@pytest.mark.asyncio
async def test_missing_user_error_is_not_softened() -> None:
    mcp = FakeMCP()

    def require_user() -> str:
        raise RuntimeError("missing authenticated user")

    tool = evidence_brief_mcp.register_evidence_brief_tool(mcp, require_user)
    with pytest.raises(RuntimeError, match="missing authenticated user"):
        await tool("q")


@pytest.mark.asyncio
async def test_invalid_output_format_fails_closed() -> None:
    mcp = FakeMCP()
    called = False

    def require_user() -> str:
        nonlocal called
        called = True
        return "user-1"

    tool = evidence_brief_mcp.register_evidence_brief_tool(mcp, require_user)
    with pytest.raises(ValueError, match="unsupported output_format"):
        await tool("q", output_format="xml")
    assert called is False


def test_adapter_does_not_construct_or_import_mcp_runtime() -> None:
    source = inspect.getsource(evidence_brief_mcp)
    assert "FastMCP(" not in source
    assert "from stratum.api.mcp" not in source
