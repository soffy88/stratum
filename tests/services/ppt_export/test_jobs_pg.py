"""Job repository against PostgreSQL (CI applies all migrations, incl. 084)."""

from __future__ import annotations

import pytest

from stratum.services.ppt_export import jobs

SUB = "sub_test_ppt_export_jobs"
ALICE, BOB = "ppt-user-alice", "ppt-user-bob"


@pytest.fixture
def pg_book():
    try:
        from stratum.db import execute, query

        if not query("SELECT to_regclass('stratum.ppt_export_jobs') AS t")[0]["t"]:
            pytest.skip("migration 084 not applied")
    except Exception as exc:  # no database in this environment
        pytest.skip(f"PostgreSQL unavailable: {exc}")
    execute(
        "INSERT INTO stratum.substrates (id, user_id, title) VALUES (%(id)s, %(u)s, 'ppt fixture') "
        "ON CONFLICT (id) DO NOTHING",
        {"id": SUB, "u": jobs.owner_of(ALICE)},
    )
    yield SUB
    execute("DELETE FROM stratum.ppt_export_jobs WHERE substrate_id=%(id)s", {"id": SUB})
    execute("DELETE FROM stratum.substrates WHERE id=%(id)s", {"id": SUB})


def test_jobs_are_owner_scoped(pg_book):
    assert jobs.owned_substrate(ALICE, pg_book)
    assert jobs.owned_substrate(BOB, pg_book) is None

    job = jobs.create_job(ALICE, pg_book, style="dark-tech", pages=9, options={"audience": "学生"})
    assert job["status"] == "queued" and job["user_id"] == jobs.owner_of(ALICE)
    assert jobs.get_job(ALICE, job["id"])["pages"] == 9
    assert jobs.get_job(BOB, job["id"]) is None
    assert [j["id"] for j in jobs.list_jobs(ALICE, pg_book)] == [job["id"]]
    assert jobs.list_jobs(BOB) == [] or all(j["id"] != job["id"] for j in jobs.list_jobs(BOB))


def test_runner_records_failure_on_the_row(pg_book):
    job = jobs.create_job(ALICE, pg_book, style="paper-notes", pages=8)
    jobs.run_job(job["id"], jobs.owner_of(ALICE))  # no book understanding exists
    done = jobs.get_job(ALICE, job["id"])
    assert done["status"] == "failed"
    assert "book understanding" in (done["error"] or "")
    assert done["finished_at"] is not None


def test_runner_ignores_a_foreign_owner(pg_book):
    job = jobs.create_job(ALICE, pg_book, style="paper-notes", pages=8)
    jobs.run_job(job["id"], jobs.owner_of(BOB))
    assert jobs.get_job(ALICE, job["id"])["status"] == "queued"
