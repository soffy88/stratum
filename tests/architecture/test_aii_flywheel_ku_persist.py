"""AII flywheel KU-persistence repairs (2026-10-14).

- _provider: reasoning-preamble stripping + JSON object extraction for free reasoning models
- synthesize_book: explicit shell / language rejection reasons (no silent drop)
- paper_discover: doc_type: paper frontmatter backfill
- docs_client: cross-process conversion slot + no local re-conversion after a container timeout
"""

from __future__ import annotations

import ast
import importlib.util
import re
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AII = ROOT / "aii"


def _load(name: str, path: Path, stubs: dict[str, object] | None = None):
    for mod_name, mod in (stubs or {}).items():
        sys.modules.setdefault(mod_name, mod)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _provider():
    obase = types.ModuleType("obase")
    obase.ProviderRegistry = object
    return _load(
        "aii_provider_under_test",
        AII / "aii" / "aii" / "api" / "_provider.py",
        {"obase": obase, "httpx": types.ModuleType("httpx")},
    )


def test_extract_json_after_thinking_process_preamble():
    p = _provider()
    text = (
        'Thinking Process:\n1. The user wants points like {"name": "x"}.\n'
        "2. Let me list them.\n\n"
        '{"points":[{"name":"law of demand","type":"conceptual"}]}'
    )
    out = p.extract_json_object(text)
    assert out == '{"points":[{"name":"law of demand","type":"conceptual"}]}'


def test_extract_json_strips_think_blocks_and_fences():
    p = _provider()
    assert p.extract_json_object('<think>{"a": 1}</think>\n```json\n{"b": 2}\n```') == '{"b": 2}'
    assert p.extract_json_object('lots of reasoning</think>{"k": {"v": 2}}') == '{"k": {"v": 2}}'


def test_plain_reasoning_without_json_is_invalid():
    p = _provider()
    assert p.extract_json_object("Thinking Process: analyse the chapter, no answer") is None
    assert not p._has_json_object("Thinking Process: analyse the chapter, no answer")


def test_whole_json_array_is_returned_unchanged():
    p = _provider()
    assert p.extract_json_object("[1, 2]") == "[1, 2]"


def test_json_request_extras_env(monkeypatch):
    p = _provider()
    monkeypatch.delenv("AII_LLM_NO_THINK", raising=False)
    monkeypatch.delenv("AII_LLM_JSON_MODE", raising=False)
    assert p._json_request_extras() == {"response_format": {"type": "json_object"}}
    monkeypatch.setenv("AII_LLM_JSON_MODE", "0")
    assert p._json_request_extras() == {}


def _shell_reject_reason():
    """Load synthesize_book._shell_reject_reason without importing the whole script
    (its module level reads the book file and connects to providers)."""
    src = (AII / "scripts" / "synthesize_book.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_shell_reject_reason"
    )
    ns: dict = {
        "re": re,
        "is_empty_shell": lambda t: not (t or "").strip(),
        "is_junk": lambda t: "抱歉" in t,
    }
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "synthesize_book", "exec"), ns)
    return ns["_shell_reject_reason"]


def test_english_output_for_chinese_book_is_explicit_lang_mismatch():
    f = _shell_reject_reason()
    assert f("Price elasticity measures how quantity demanded responds.", "") == "LANG_MISMATCH"
    assert f("", "") == "EMPTY_SHELL"
    assert f("抱歉，我无法回答这个问题因为内容窗口为空的情况", "") == "JUNK"
    assert f("需求价格弹性衡量需求量对价格变动的敏感程度。", "") is None


def test_synthesize_book_checkpoints_only_on_written_rows():
    src = (AII / "scripts" / "synthesize_book.py").read_text(encoding="utf-8")
    assert 'stats["written"] += 1' in src
    assert "if written == 0:" in src
    # the old misleading line printed the candidate count unconditionally
    assert 'f"  ch{n}: {len(kus)} KU persisted;' not in src


def test_paper_frontmatter_backfill(tmp_path):
    stubs = {
        "asyncpg": types.ModuleType("asyncpg"),
        "dotenv": types.SimpleNamespace(load_dotenv=lambda *a, **k: None),
    }
    pd = _load("paper_discover_under_test", AII / "scripts" / "paper_discover.py", stubs)
    md = tmp_path / "arxiv_1.md"
    md.write_text("A RAINBOW VERSION\nAbstract. text", encoding="utf-8")
    assert pd._ensure_paper_frontmatter(str(md)) is True
    assert md.read_text(encoding="utf-8").startswith("---\ndoc_type: paper\n---\n\n")
    assert pd._ensure_paper_frontmatter(str(md)) is False  # idempotent
    md2 = tmp_path / "arxiv_2.md"
    md2.write_text("---\ntitle: x\n---\nbody", encoding="utf-8")
    pd._ensure_paper_frontmatter(str(md2))
    assert md2.read_text(encoding="utf-8").startswith("---\ndoc_type: paper\ntitle: x\n---")


def test_docs_client_single_slot_and_timeout_no_local_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCS_LOCK_DIR", str(tmp_path))
    monkeypatch.setenv("DOCS_MAX_CONCURRENCY", "1")
    dc = _load("docs_client_under_test", AII / "scripts" / "docs_client.py")
    assert dc.DocsTimeout.aii_no_local_fallback is True
    import fcntl

    with dc._ConvertSlot():
        fh = open(tmp_path / "docs_convert.0.lock", "a+")
        try:
            try:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                raise AssertionError("slot should be held")
            except OSError:
                pass
        finally:
            fh.close()
    fh = open(tmp_path / "docs_convert.0.lock", "a+")
    fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)  # released after the with-block
    fh.close()
