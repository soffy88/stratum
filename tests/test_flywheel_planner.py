import asyncio
import json
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "aii" / "scripts"))
sys.path.insert(0, str(ROOT / "aii" / "aii"))
pytest.importorskip("obase")
import chapter_synthesize_llm_v1 as planner


def test_parse_points_accepts_nested_and_alternate_schema():
    text = "```json\n" + json.dumps(
        {"analysis": {"key_concepts": [{"concept": "market failure", "type": "concept"}]}}
    ) + "\n```"
    assert planner._parse_points(text) == [{"name": "market failure", "type": "concept"}]


def test_plan_puts_instruction_first_and_chunks_long_chapter(monkeypatch):
    calls = []

    async def fake_llm(*, messages, system, max_tokens):
        calls.append(messages[0]["content"])
        return {"content": [{"type": "text", "text": '{"points":[{"name":"demand"}]}' }]}

    monkeypatch.setenv("PLAN_CHUNK_CHARS", "8000")
    points = asyncio.run(planner._plan(fake_llm, "x" * 17000, 1))

    assert len(calls) == 3
    assert all(call.startswith("List ONLY") for call in calls)
    assert points == [{"name": "demand", "type": "concept", "pos": 0}]
