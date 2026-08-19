"""MVP week 5–6 unit tests (vault sync, purge, lint, digest — no live DB when mocked)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch


# ── vault path safety ───────────────────────────────────────────────────────


def test_assert_safe_vault_path_rejects_outside():
    from stratum.services.vault_sync_service import assert_safe_vault_path

    try:
        assert_safe_vault_path("/etc/passwd")
        assert False, "should reject"
    except ValueError as e:
        assert "allowed roots" in str(e)


def test_assert_safe_vault_path_allows_tmp(tmp_path, monkeypatch):
    from stratum.services import vault_sync_service as vs

    monkeypatch.setenv("STRATUM_VAULT_SYNC_ROOTS", str(tmp_path))
    # re-read roots
    p = vs.assert_safe_vault_path(str(tmp_path / "vault"))
    assert str(p).startswith(str(tmp_path.resolve()))


def test_export_vault_to_path_writes_files(tmp_path, monkeypatch):
    from stratum.services import vault_sync_service as vs

    monkeypatch.setenv("STRATUM_VAULT_SYNC_ROOTS", str(tmp_path))
    fake = {
        "README.md": "# vault\n",
        "notes/a.md": "---\nid: 1\ntype: note\ntitle: a\naliases: []\nsources: []\nupdated: 2026-07-29\n---\n\n# a\n",
        "index.json": "{}",
    }
    with patch.object(vs, "build_vault_files", return_value=fake):
        out = vs.export_vault_to_path("user-1", str(tmp_path / "out"))
    assert out["status"] == "ok"
    assert out["files_written"] == 3
    assert (tmp_path / "out" / "README.md").exists()
    assert (tmp_path / "out" / ".aii-vault-sync.json").exists()


def test_parse_frontmatter_and_import(tmp_path, monkeypatch):
    from stratum.services import vault_sync_service as vs

    monkeypatch.setenv("STRATUM_VAULT_SYNC_ROOTS", str(tmp_path))
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "hello.md").write_text(
        "---\nid: 01HELLO\ntype: note\ntitle: Hello\naliases: []\nsources: []\nupdated: 2026-07-29\n---\n\n# Hello\n\nbody\n",
        encoding="utf-8",
    )

    inserts = []

    def fake_read(table, rid):
        return None

    def fake_insert(table, data):
        inserts.append((table, data))
        return data.get("id")

    with patch.object(vs, "read", side_effect=fake_read):
        with patch.object(vs, "insert", side_effect=fake_insert):
            with patch.object(vs, "update"):
                with patch.object(vs, "query", return_value=[]):
                    out = vs.import_notes_from_path("user-1", str(tmp_path))
    assert out["status"] == "ok"
    assert out["created"] == 1
    assert inserts[0][1]["id"] == "01HELLO"
    assert inserts[0][1]["title"] == "Hello"


def test_sync_vault_mode_validation(tmp_path, monkeypatch):
    from stratum.services import vault_sync_service as vs

    monkeypatch.setenv("STRATUM_VAULT_SYNC_ROOTS", str(tmp_path))
    try:
        vs.sync_vault("u", str(tmp_path), mode="nope")
        assert False
    except ValueError:
        pass


# ── purge helpers ───────────────────────────────────────────────────────────


def test_purge_note_not_found():
    from stratum.services import purge_service as ps

    with patch.object(ps, "read", return_value=None):
        out = ps.purge_note("x", "u")
    assert out["status"] == "not_found"


def test_purge_note_hard():
    from stratum.services import purge_service as ps

    with patch.object(ps, "read", return_value={"id": "n1", "user_id": "u"}):
        with patch.object(ps, "hard_delete_row") as hd:
            out = ps.purge_note("n1", "u")
    assert out["status"] == "purged"
    assert out["mode"] == "hard"
    hd.assert_called_once_with("notes_sl", "n1")


def test_hard_delete_db_helper_exists():
    from stratum.db import hard_delete

    assert callable(hard_delete)


# ── lint pure logic via source markers ───────────────────────────────────────


def test_lint_wikilink_regex():
    from stratum.services.knowledge_lint_service import _WIKILINK

    found = _WIKILINK.findall("see [[abc]] and [[Title|label]]")
    assert "abc" in found
    assert "Title|label" in found


def test_lint_and_digest_agent_helpers():
    from stratum.api.routers import agents

    assert "knowledge_lint" in agents._NATIVE_AGENTS
    assert "daily_digest_simple" in agents._NATIVE_AGENTS
    assert hasattr(agents, "_run_knowledge_lint_agent")
    assert hasattr(agents, "_run_daily_digest_simple")


def test_sync_router_has_vault():
    from stratum.api.routers import sync as s

    paths = {getattr(r, "path", "") for r in s.router.routes}
    assert any("vault" in p for p in paths)
