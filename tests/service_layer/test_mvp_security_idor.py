"""IDOR / path-safety unit tests for audit fixes (2026-07-29)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


# ── vault path ──────────────────────────────────────────────────────────────


def test_default_roots_exclude_home(monkeypatch):
    monkeypatch.delenv("STRATUM_VAULT_SYNC_ROOTS", raising=False)
    from stratum.services.vault_sync_service import allowed_roots

    roots = [str(r) for r in allowed_roots()]
    assert not any(r == "/home" or r.endswith("/home") for r in roots)
    assert any("aii-vault" in r or "stratum" in r for r in roots)


def test_export_skips_parent_escape(tmp_path, monkeypatch):
    from stratum.services import vault_sync_service as vs

    monkeypatch.setenv("STRATUM_VAULT_SYNC_ROOTS", str(tmp_path))
    evil = {
        "notes/ok.md": "# ok\n",
        "../escape.md": "pwned\n",
        "notes/../../escape2.md": "pwned2\n",
    }
    with patch.object(vs, "build_vault_files", return_value=evil):
        out = vs.export_vault_to_path("user-1", str(tmp_path / "vault"))
    assert (tmp_path / "vault" / "notes" / "ok.md").exists()
    assert not (tmp_path / "escape.md").exists()
    assert not (tmp_path / "escape2.md").exists()
    assert out["files_written"] == 1


def test_assert_safe_watch_path_rejects_etc(tmp_path, monkeypatch):
    from stratum.services.vault_sync_service import assert_safe_watch_path

    monkeypatch.setenv("STRATUM_FOLDER_WATCH_ROOTS", str(tmp_path))
    try:
        assert_safe_watch_path("/etc/passwd")
        assert False, "should reject"
    except ValueError as e:
        assert "allowed roots" in str(e)


def test_assert_safe_watch_path_allows_under_root(tmp_path, monkeypatch):
    from stratum.services.vault_sync_service import assert_safe_watch_path

    monkeypatch.setenv("STRATUM_FOLDER_WATCH_ROOTS", str(tmp_path))
    target = tmp_path / "docs"
    target.mkdir()
    p = assert_safe_watch_path(str(target))
    assert str(p).startswith(str(tmp_path.resolve()))


# ── ownership helper ────────────────────────────────────────────────────────


def test_owns_substrate_row_raw_and_hash():
    from stratum.utils.ownership import owns_substrate_row, owner_ids

    raw, uh = owner_ids("alice@example.com")
    assert owns_substrate_row("alice@example.com", raw)
    assert owns_substrate_row("alice@example.com", uh)
    assert not owns_substrate_row("alice@example.com", "other")
    assert not owns_substrate_row("alice@example.com", None)


# ── sessions ownership ──────────────────────────────────────────────────────


def test_get_session_filters_user():
    from stratum.services import session_manager as sm

    fake_row = (
        "sess1", "user-a", "t", "active", 0, 0, 0, 0, 20, None, "t0", "t1"
    )
    conn = MagicMock()
    # first call with user filter returns None; without would return row
    conn.execute.return_value.fetchone.return_value = None
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)

    with patch.object(sm, "get_conn", return_value=conn):
        out = sm.get_session("sess1", user_id="user-b")
    assert out is None
    # SQL must include user_id
    sql = conn.execute.call_args[0][0]
    assert "user_id" in sql


def test_delete_session_not_owner():
    from stratum.services import session_manager as sm

    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)

    with patch.object(sm, "get_conn", return_value=conn):
        out = sm.delete_session("sess1", user_id="user-b")
    assert out.get("error") == "not_found"


def test_add_message_not_owner():
    from stratum.services import session_manager as sm

    with patch.object(sm, "require_session_owner", return_value=None):
        out = sm.add_message("sess1", "user", "hi", user_id="user-b")
    assert out.get("error") == "not_found"


# ── trajectory ownership ────────────────────────────────────────────────────


def test_get_trajectory_requires_user():
    from stratum.services import retrieval_engine as re

    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)

    with patch.object(re, "get_conn", return_value=conn):
        out = re.get_trajectory("traj1", user_id="user-a")
    assert out is None
    sql = conn.execute.call_args[0][0]
    assert "user_id" in sql


# ── retrieval search includes user filter ───────────────────────────────────


def test_vector_search_sql_joins_substrates_when_user():
    from stratum.services import retrieval_engine as re

    conn = MagicMock()
    # first execute (pgvector) fails → fallback
    conn.execute.side_effect = [
        Exception("no pgvector"),
        MagicMock(fetchall=MagicMock(return_value=[])),
    ]
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)

    emb = [0.1] * 8
    with patch.object(re, "get_conn", return_value=conn):
        re._vector_search_layers(emb, "L0", top_k=5, user_id="alice")
    # Last call is fallback SELECT — must join substrates and filter user
    calls = [c[0][0] for c in conn.execute.call_args_list]
    assert any("JOIN substrates" in s for s in calls)
    assert any("s.user_id" in s for s in calls)


def test_text_search_sql_user_filter():
    from stratum.services import retrieval_engine as re

    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = []
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)

    with patch.object(re, "get_conn", return_value=conn):
        re._text_search_layers("hello world", "L0", top_k=5, user_id="alice")
    sql = conn.execute.call_args[0][0]
    assert "JOIN substrates" in sql
    assert "s.user_id" in sql


# ── cornell machine delete ──────────────────────────────────────────────────


def test_cornell_machine_delete_forbidden():
    from fastapi import HTTPException
    import asyncio
    from stratum.api.routers import cornell as cr

    with patch.object(cr, "read", return_value={"id": "n1", "source": "machine", "deleted_at": None}):
        try:
            asyncio.run(cr.delete_cornell("n1", user_id="u"))
            assert False, "should 403"
        except HTTPException as e:
            assert e.status_code == 403


# ── metrics admin gate ──────────────────────────────────────────────────────


def test_metrics_require_admin_secret(monkeypatch):
    from fastapi import HTTPException
    from stratum.api.routers import metrics as m

    monkeypatch.delenv("ADMIN_SECRET", raising=False)
    try:
        m._require_admin_secret(None)
        assert False
    except HTTPException as e:
        assert e.status_code == 503

    monkeypatch.setenv("ADMIN_SECRET", "s3cret")
    try:
        m._require_admin_secret("wrong")
        assert False
    except HTTPException as e:
        assert e.status_code == 403

    m._require_admin_secret("s3cret")  # no raise


# ── layers ownership helper ─────────────────────────────────────────────────


def test_assert_owns_substrate_404():
    from fastapi import HTTPException
    from stratum.api.routers import layers as ly

    with patch.object(ly, "fetch_owned_substrate", return_value=None):
        try:
            ly._assert_owns_substrate("sid", "user-a")
            assert False
        except HTTPException as e:
            assert e.status_code == 404
