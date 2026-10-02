from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

import ulid


@dataclass
class Note:
    id: str
    corpus_id: str
    title: str
    content: str
    wikilinks: str
    substrate_id: Optional[str]
    meta_json: str
    created_at: datetime
    updated_at: datetime


class NoteDAO:
    def __init__(self, db_conn):
        self.conn = db_conn

    _COLS = (
        "id, corpus_id, title, content, wikilinks, substrate_id, meta_json, created_at, updated_at"
    )

    def _has_service_notes(self) -> bool:
        """Return whether the converged PostgreSQL notes_sl table is present.

        The legacy DuckDB fixture and older standalone deployments still expose
        the singular ``note`` table.  Detection is deliberately per connection
        so the compatibility path does not hard-code the deployment type.
        """
        try:
            self.conn.execute("SELECT 1 FROM notes_sl LIMIT 0")
        except Exception:
            return False
        return True

    @staticmethod
    def _service_owner_keys(corpus_id: str) -> tuple[str, str]:
        return corpus_id, corpus_id.removeprefix("user_")

    def _service_note_sql(self, where: str) -> str:
        """Project notes_sl into the legacy Note shape."""
        return (
            "SELECT n.id, COALESCE(u.corpus_id, ?), n.title, n.content_markdown, "
            "CAST('[]' AS TEXT), n.substrate_refs[1], CAST('{}' AS TEXT), "
            "n.created_at, n.updated_at "
            "FROM notes_sl n LEFT JOIN users u "
            "ON u.id = n.user_id OR u.email = n.user_id "
            f"WHERE {where}"
        )

    def list_notes(self, *, corpus_id: str, limit: int = 50) -> List[Note]:
        if self._has_service_notes():
            owner, user_key = self._service_owner_keys(corpus_id)
            res = self.conn.execute(
                self._service_note_sql(
                    "n.deleted_at IS NULL AND "
                    "(u.corpus_id = ? OR n.user_id = ? OR n.user_id = ?) "
                    "ORDER BY n.created_at DESC LIMIT ?"
                ),
                (corpus_id, owner, owner, user_key, limit),
            ).fetchall()
        else:
            res = self.conn.execute(
                f"SELECT {self._COLS} FROM note WHERE corpus_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (corpus_id, limit),
            ).fetchall()
        return [Note(*r) for r in res]

    def get_note(self, *, note_id: str, corpus_id: str) -> Optional[Note]:
        if self._has_service_notes():
            owner, user_key = self._service_owner_keys(corpus_id)
            res = self.conn.execute(
                self._service_note_sql(
                    "n.id = ? AND n.deleted_at IS NULL AND "
                    "(u.corpus_id = ? OR n.user_id = ? OR n.user_id = ?)"
                ),
                (corpus_id, note_id, owner, owner, user_key),
            ).fetchone()
        else:
            res = self.conn.execute(
                f"SELECT {self._COLS} FROM note WHERE id = ? AND corpus_id = ?",
                (note_id, corpus_id),
            ).fetchone()
        return Note(*res) if res else None

    def create_note(
        self, *, corpus_id: str, title: str, content: str, substrate_id: Optional[str] = None
    ) -> Note:
        note_id = str(ulid.ULID())
        now = datetime.now(timezone.utc)
        if self._has_service_notes():
            owner = self.conn.execute(
                "SELECT id FROM users WHERE corpus_id = ? LIMIT 1", (corpus_id,)
            ).fetchone()
            user_id = owner[0] if owner else corpus_id.removeprefix("user_")
            self.conn.execute(
                "INSERT INTO notes_sl "
                "(id, user_id, title, content_markdown, substrate_refs, concept_refs, "
                "content_refs, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    note_id,
                    user_id,
                    title,
                    content,
                    [substrate_id] if substrate_id else [],
                    [],
                    [],
                    now,
                    now,
                ),
            )
        else:
            self.conn.execute(
                "INSERT INTO note "
                "(id, corpus_id, title, content, substrate_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (note_id, corpus_id, title, content, substrate_id, now, now),
            )
        return self.get_note(note_id=note_id, corpus_id=corpus_id)

    def list_backlinks(self, *, note_id: str, corpus_id: str) -> list[tuple]:
        """Return legacy-shaped backlink rows for either storage schema."""
        if self._has_service_notes():
            owner, user_key = self._service_owner_keys(corpus_id)
            return self.conn.execute(
                "SELECT n.id, n.title, n.content_markdown "
                "FROM notes_sl n LEFT JOIN users u "
                "ON u.id = n.user_id OR u.email = n.user_id "
                "WHERE n.deleted_at IS NULL AND "
                "(u.corpus_id = ? OR n.user_id = ? OR n.user_id = ?) "
                "AND n.content_markdown LIKE ? AND n.id != ?",
                (owner, owner, user_key, f"%[[{note_id}]]%", note_id),
            ).fetchall()
        return self.conn.execute(
            "SELECT id, title, content FROM note "
            "WHERE corpus_id = ? AND wikilinks LIKE ? AND id != ?",
            (corpus_id, f"%{note_id}%", note_id),
        ).fetchall()
