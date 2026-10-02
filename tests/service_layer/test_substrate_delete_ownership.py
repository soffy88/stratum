"""P0 adversarial coverage for substrate destructive operations."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def _conn(*, row=None):
    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    conn.execute.return_value.fetchone.return_value = row
    conn.execute.return_value.fetchall.return_value = []
    return conn


def test_cross_user_impact_is_fail_closed():
    from stratum.services import document_deletion as deletion

    conn = _conn(row=None)
    with patch.object(deletion, "get_conn", return_value=conn):
        result = deletion.analyze_substrate_impact("owner-b-substrate", user_id="user-a")

    assert result["error"] == "substrate_not_found"
    assert all("UPDATE" not in str(call.args[0]) for call in conn.execute.call_args_list)


def test_cross_user_delete_and_restore_do_not_write():
    from stratum.services import document_deletion as deletion

    conn = _conn(row=None)
    with patch.object(deletion, "get_conn", return_value=conn):
        deleted = deletion.soft_delete_substrate("owner-b-substrate", user_id="user-a")
        restored = deletion.restore_substrate("owner-b-substrate", user_id="user-a")
        purged = deletion.hard_delete_substrate("owner-b-substrate", user_id="user-a")

    assert deleted["errors"] == ["substrate_forbidden_or_not_found"]
    assert restored["errors"] == ["substrate_forbidden_or_not_found"]
    assert purged["errors"] == ["substrate_forbidden_or_not_found"]
    assert all(
        not any(keyword in str(call.args[0]) for keyword in ("UPDATE", "DELETE"))
        for call in conn.execute.call_args_list
    )


def test_cross_user_anchor_delete_matches_only_owned_rows():
    from stratum.services import document_deletion as deletion

    conn = _conn(row=None)
    conn.execute.return_value.fetchall.return_value = []
    with patch.object(deletion, "get_conn", return_value=conn):
        result = deletion.delete_by_anchor(
            "/private/b.pdf", anchor_type="source_path", user_id="user-a"
        )

    assert result["error"] == "no_matching_substrates"
    sql, params = conn.execute.call_args.args
    assert "user_id = ? OR user_id = ?" in sql
    assert params[1:] == (
        "user-a",
        deletion.owner_ids("user-a")[1],
    )
