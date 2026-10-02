from unittest.mock import patch

import pytest


def test_get_user_note_is_owner_scoped_and_ignores_deleted_rows():
    from stratum.services.note_queries import get_user_note

    with patch(
        "stratum.services.note_queries.read",
        return_value={"id": "n1", "user_id": "user-a", "deleted_at": None},
    ):
        assert get_user_note("user-a", "n1") is not None
        assert get_user_note("user-b", "n1") is None

    with patch(
        "stratum.services.note_queries.read",
        return_value={"id": "n1", "user_id": "user-a", "deleted_at": "now"},
    ):
        assert get_user_note("user-a", "n1") is None


def test_note_query_helpers_target_canonical_table_and_postgres_months():
    from stratum.services.note_queries import (
        list_recent_user_notes,
        list_user_notes_for_content,
        list_user_notes_in_range,
    )

    with patch("stratum.services.note_queries.query", return_value=[]) as query_mock:
        list_recent_user_notes("user-a", limit=7)
        list_user_notes_for_content("user-a", "content-1")
        list_user_notes_in_range("user-a", "2026-01-01", "2026-02-01")

    sqls = [call.args[0] for call in query_mock.call_args_list]
    assert all("FROM notes_sl" in sql for sql in sqls)
    assert "to_char(created_at, 'YYYY-MM')" in sqls[-1]
    assert query_mock.call_args_list[0].kwargs["limit"] == 7


@pytest.mark.asyncio
async def test_mcp_note_tools_delegate_to_canonical_helpers():
    from stratum.api import mcp

    with (
        patch("stratum.api.mcp._require_user", return_value="user-a"),
        patch(
            "stratum.api.mcp.get_user_note",
            return_value={"id": "n1", "title": "T", "content_markdown": "body"},
        ) as get_note,
        patch(
            "stratum.api.mcp.list_recent_user_notes",
            return_value=[{"id": "n1", "title": "T"}],
        ) as list_notes,
    ):
        note = await mcp.get_note("n1")
        recent = await mcp.list_recent_notes(limit=3)

    get_note.assert_called_once_with("user-a", "n1")
    list_notes.assert_called_once_with("user-a", limit=3)
    assert note["content_markdown"] == "body"
    assert recent == [{"id": "n1", "title": "T"}]
