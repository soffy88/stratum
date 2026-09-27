import pytest

from stratum.db.run_pg_migrations import _apply_migration


class _Connection:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class _Cursor:
    def __init__(self, *, fail_on: str | None = None):
        self.fail_on = fail_on
        self.statements: list[tuple[str, object]] = []

    def execute(self, statement: str, params=None):
        self.statements.append((statement, params))
        if self.fail_on and self.fail_on in statement:
            raise RuntimeError("synthetic migration failure")


def test_apply_migration_records_only_after_sql_succeeds():
    connection = _Connection()
    cursor = _Cursor()

    _apply_migration(connection, cursor, "020_test.sql", "CREATE TABLE test (id INT)")

    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert len(cursor.statements) == 2


def test_apply_migration_rolls_back_when_tracking_insert_fails():
    connection = _Connection()
    cursor = _Cursor(fail_on="INSERT INTO public._pg_migrations")

    with pytest.raises(RuntimeError, match="synthetic migration failure"):
        _apply_migration(connection, cursor, "020_test.sql", "CREATE TABLE test (id INT)")

    assert connection.commits == 0
    assert connection.rollbacks == 1
