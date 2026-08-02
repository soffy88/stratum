"""stratum.db._ConnWrapper placeholder translation — LIKE + params edge cases."""

import re

import pytest

from stratum.db import _ConnWrapper, _to_pyformat

# Replicate the translation logic (imported via _ConnWrapper.execute is hard to
# unit test without a live cursor, so test the pure translation behavior through
# a stub cursor).
import psycopg2


class _StubCursor:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((sql, params))


def _translate(sql: str, params) -> tuple[str, object]:
    conn = _ConnWrapper.__new__(_ConnWrapper)
    conn._raw = _RawStub()
    cur = conn.execute(sql, params)
    return cur.calls[0]


class _RawStub:
    def cursor(self):
        return _StubCursor()


def test_positional_like_literals_escaped():
    sql, params = _translate(
        "SELECT content FROM derivative WHERE substrate_id=? "
        "AND kind LIKE 'translation%zh%' ORDER BY seq LIMIT 1",
        ("abc",),
    )
    assert "%s" in sql
    assert "translation%%zh%%" in sql
    assert "translation%zh%" not in sql  # single-% LIKE literal must not survive
    assert params == ("abc",)


def test_positional_plain():
    sql, params = _translate("SELECT title FROM substrates WHERE id=?", ("s1",))
    assert sql == "SELECT title FROM substrates WHERE id=%s"


def test_named_keeps_markers_escapes_like():
    sql, params = _translate(
        "SELECT id FROM notes_sl WHERE user_id=$uid AND title=$name "
        "AND content_markdown LIKE 'x%y%'",
        {"uid": "u", "name": "n"},
    )
    assert "%(uid)s" in sql and "%(name)s" in sql
    assert "x%%y%%" in sql  # stray literal % must be escaped
    assert "LIKE 'x%y%'" not in sql


def test_dollar_named_translation():
    sql, _ = _translate("SELECT * FROM t WHERE a=$x", {"x": 1})
    assert sql == "SELECT * FROM t WHERE a=%(x)s"
