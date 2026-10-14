"""Learning-guide cache — task E persistence.

The guide is a topological order over the run's reasoning graph. These tests pin
the two properties the cache has to preserve: it never serves a guide built from
a graph the run no longer has (a rebuild is a miss), and it is never an authority
(a missing row costs a recomputation, not a wrong answer).

The store is an in-memory fake behind the module's connection seam, so the SQL
and the ordering are exercised without a live database and every test starts from
an empty cache.
"""

from __future__ import annotations

import asyncio

import pytest

from stratum.services.bu_v2_learning_guide import GuideStep, LearningGuide
from stratum.services.bu_v2_learning_guide_cache import (
    guide_version_of,
    invalidate_run,
    normalise,
    read_cache,
    write_cache,
)

RUN = "br_LG_TEST"


class FakeCursor:
    """Answers the four statements the cache issues, from `store`.

    The seam's shape follows ``psycopg2``: ``cursor()`` yields, the SQL is then
    handed to ``execute``, and results leave through ``fetchall``/``fetchone``.
    """

    def __init__(self, store: dict):
        self._store = store
        self.description: list[tuple[str]] = []
        self._rows: list[tuple] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql: str, params: dict | None = None) -> None:
        params = params or {}
        body = " ".join(sql.split()).upper()
        if body.startswith("SELECT COUNT(*)"):
            # Honour the WHERE: with a version predicate only that row counts.
            if "GRAPH_VERSION = %(V)S" in body:
                matching = [(params["r"], params["v"]) in self._store]
            else:
                matching = [k[0] == params["r"] for k in self._store]
            # The seam hands rows to fetchall as tuples; the real db.query turns
            # them into dicts by column name, which is what the caller reads.
            self.description = [("n",)]
            self._rows = [(sum(matching),)]
        elif body.startswith("SELECT"):
            row = self._store.get((params["run_id"], params["v"]))
            self.description = [
                ("payload",),
                ("step_count",),
                ("graph_version",),
            ]
            self._rows = [(row["payload"], row["step_count"], row["graph_version"])] if row else []
        elif body.startswith("INSERT"):
            key = (params["run_id"], params["graph_version"])
            self._store[key] = {
                "payload": params["payload"],
                "step_count": params["step_count"],
                "graph_version": params["graph_version"],
            }
            self.description = [("run_id",)]
            self._rows = [(key[0],)]
        elif body.startswith("DELETE"):
            if "GRAPH_VERSION = %(V)S" in body:
                self._store.pop((params["r"], params["v"]), None)
            else:
                for k in [k for k in self._store if k[0] == params["r"]]:
                    del self._store[k]
        else:
            raise AssertionError(f"unexpected SQL: {body[:80]}")

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class FakeConnection:
    """The cache's connection seam: reads and writes over one in-memory dict."""

    def __init__(self) -> None:
        self.store: dict[tuple[str, str], dict] = {}

    def cursor(self):
        return FakeCursor(self.store)

    def write(self, table, data, conflict_on=None, returning="id") -> str:
        """The upsert the write path uses; must key on the cache identity."""
        assert conflict_on == ["run_id", "graph_version"], "must upsert on the cache key"
        key = (data["run_id"], data["graph_version"])
        self.store[key] = {
            "payload": data["payload"],
            "step_count": data["step_count"],
            "graph_version": data["graph_version"],
        }
        return key[0]


@pytest.fixture
def conn() -> FakeConnection:
    return FakeConnection()


def _guide(steps: list[str]) -> LearningGuide:
    return LearningGuide(book_id="sub_LG", run_id=RUN, steps=[_step(s) for s in steps])


def _step(name: str) -> GuideStep:
    return GuideStep(concept=name, chapter_id="ch1")


def _store(conn: FakeConnection, version: str, steps: list[str]) -> None:
    payload = _guide(steps).to_dict()
    write_cache(
        run_id=RUN,
        graph_version=version,
        book_id="sub_LG",
        guide=payload,
        graph_id=version,
        connection=conn,
    )


def test_miss_returns_none(conn):
    assert read_cache(RUN, "g1", conn) is None


def test_round_trip_preserves_the_payload(conn):
    _store(conn, "g1", ["sequence", "series", "power series"])
    cached = read_cache(RUN, "g1", conn)
    assert [s["concept"] for s in cached["steps"]] == ["sequence", "series", "power series"]
    assert cached["run_id"] == RUN


def test_a_rebuilt_graph_is_a_miss_not_a_stale_hit(conn):
    """The whole point of keying on the graph, not the run."""
    _store(conn, "g_old", ["sequence", "series"])
    _store(conn, "g_new", ["limit", "continuity"])
    old_row = read_cache(RUN, "g_old", conn)
    new_row = read_cache(RUN, "g_new", conn)
    assert [s["concept"] for s in old_row["steps"]] == ["sequence", "series"]
    assert [s["concept"] for s in new_row["steps"]] == ["limit", "continuity"]


def test_rewrite_under_the_same_identity_replaces_not_duplicates(conn):
    """>fresh=1 rewrites the row; a plain INSERT would collide silently."""
    _store(conn, "g1", ["a"])
    _store(conn, "g1", ["b", "c"])
    cached = read_cache(RUN, "g1", conn)
    assert [s["concept"] for s in cached["steps"]] == ["b", "c"]
    assert len(conn.store) == 1


def test_invalidate_drops_the_versions_it_names(conn):
    _store(conn, "g1", ["x"])
    _store(conn, "g2", ["x"])
    assert invalidate_run(RUN, graph_version="g1", connection=conn) == 1
    assert read_cache(RUN, "g1", conn) is None
    assert read_cache(RUN, "g2", conn) is not None


def test_invalidate_without_a_version_drops_every_version(conn):
    for v in ("g1", "g2", "g3"):
        _store(conn, v, ["x"])
    assert invalidate_run(RUN, connection=conn) == 3
    assert all(read_cache(RUN, v, conn) is None for v in ("g1", "g2", "g3"))


def test_guide_version_is_stable_without_a_persisted_graph():
    """Two requests must not race to write two rows for the same run."""
    assert guide_version_of(None, RUN) == guide_version_of(None, RUN)
    assert guide_version_of("g1", RUN) == "g1"
    assert guide_version_of(None, RUN) != guide_version_of(None, "br_OTHER")


def test_normalise_handles_every_shape_a_jsonb_column_arrives_in():
    assert normalise('{"steps": []}') == {"steps": []}
    assert normalise('"[\\"a\\"]"') == ["a"]
    assert normalise({"a": 1}) == {"a": 1}
    assert normalise([1]) == [1]
    assert normalise(None) is None
    assert normalise("not json") == "not json"


# ── router integration ──────────────────────────────────────────────────────


def _owned(monkeypatch, graph_id="g1", chapters=None):
    def fake_query(sql, params=None, limit=100):
        if "book_understandings_v2" in sql:
            return [
                {
                    "id": "bu1",
                    "substrate_id": "s",
                    "book_id": "b",
                    "reasoning_graph_id": graph_id,
                }
            ]
        if "chapter_understandings" in sql:
            return (
                chapters
                if chapters is not None
                else [{"chapter_id": "ch1", "concepts_introduced_refs": ["limit"]}]
            )
        if "reasoning_node" in sql:
            return [
                {
                    "id": "n1",
                    "node_type": "CONCEPT",
                    "label": "limit",
                    "chapter_id": "ch1",
                    "metadata": None,
                }
            ]
        if "reasoning_edge" in sql:
            return []
        return []

    from stratum.api.routers import bu

    monkeypatch.setattr(bu, "query", fake_query)


def _patch_cache(monkeypatch, store):
    """Stub the cache over one dict.

    ``read_cache`` decodes a fresh jsonb value on every call, so it hands back a
    new object each time and the caller may mutate it. The stub copies for the
    same reason: without it, page two would mutate page one's response.
    """
    import copy as _copy

    from stratum.api.routers import bu

    monkeypatch.setattr(
        bu,
        "read_cache",
        lambda run, version, connection=None: (
            _copy.deepcopy(store[version]) if version in store else None
        ),
    )
    monkeypatch.setattr(
        bu,
        "write_cache",
        lambda **kw: (store.__setitem__(kw["graph_version"], kw["guide"]), kw["guide"])[1],
    )


def test_second_request_is_served_from_the_cache(monkeypatch):
    from stratum.api.routers import bu

    store: dict = {}
    _owned(monkeypatch)
    _patch_cache(monkeypatch, store)
    first = asyncio.run(bu.get_learning_guide(RUN, "u"))
    assert first["cached"] is False
    assert len(store) == 1
    second = asyncio.run(bu.get_learning_guide(RUN, "u"))
    assert second["cached"] is True
    assert second["steps"] == first["steps"]


def test_fresh_bypasses_the_cache_and_rewrites(monkeypatch):
    from stratum.api.routers import bu

    store: dict = {}
    _owned(monkeypatch)
    _patch_cache(monkeypatch, store)
    asyncio.run(bu.get_learning_guide(RUN, "u"))
    # Poison the cache: fresh=1 must not read it, and must replace it.
    store["g1"] = {"steps": [{"concept": "stale"}]}
    out = asyncio.run(bu.get_learning_guide(RUN, "u", fresh=True))
    assert out["cached"] is False
    assert store["g1"]["steps"] == out["steps"]
    assert store["g1"]["steps"][0]["concept"] != "stale"


def test_a_missing_cache_row_still_produces_a_guide(monkeypatch):
    """The cache is not an authority: a cold table yields the same answer."""
    from stratum.api.routers import bu

    _owned(monkeypatch)
    writes = []
    monkeypatch.setattr(bu, "read_cache", lambda *a, **kw: None)
    monkeypatch.setattr(
        bu,
        "write_cache",
        lambda **kw: (writes.append(kw), kw["guide"])[1],
    )
    out = asyncio.run(bu.get_learning_guide(RUN, "u"))
    assert out["cached"] is False
    assert out["steps"], "a cold cache must still compute the guide"
    assert len(writes) == 1


def test_paging_pages_over_the_cached_guide_not_the_window(monkeypatch):
    from stratum.api.routers import bu

    # Two concept nodes, one per chapter, so the guide has two steps to page over.
    def fake_query(sql, params=None, limit=100):
        if "book_understandings_v2" in sql:
            return [{"id": "bu1", "substrate_id": "s", "book_id": "b", "reasoning_graph_id": "g1"}]
        if "chapter_understandings" in sql:
            return [
                {"chapter_id": "ch1", "concepts_introduced_refs": ["scarcity"]},
                {"chapter_id": "ch2", "concepts_introduced_refs": ["opportunity cost"]},
            ]
        if "reasoning_node" in sql:
            return [
                {
                    "id": "n1",
                    "node_type": "CONCEPT",
                    "label": "scarcity",
                    "chapter_id": "ch1",
                    "metadata": None,
                },
                {
                    "id": "n2",
                    "node_type": "CONCEPT",
                    "label": "opportunity cost",
                    "chapter_id": "ch2",
                    "metadata": None,
                },
            ]
        if "reasoning_edge" in sql:
            return []
        return []

    monkeypatch.setattr(bu, "query", fake_query)
    store: dict = {}
    _patch_cache(monkeypatch, store)
    p1 = asyncio.run(bu.get_learning_guide(RUN, "u", limit=1, offset=0))
    after_p1 = {k: [s["concept"] for s in v.get("steps", [])] for k, v in store.items()}
    p2 = asyncio.run(bu.get_learning_guide(RUN, "u", limit=1, offset=1))
    after_p2 = {k: [s["concept"] for s in v.get("steps", [])] for k, v in store.items()}
    # The whole guide is cached, not the window, so page 2 continues page 1.
    assert len(store["g1"]["steps"]) == 2, f"{after_p1} -> {after_p2}"
    assert p1["steps"][0]["concept"] != p2["steps"][0]["concept"]


def test_a_run_with_no_graph_gets_a_stable_cache_key(monkeypatch):
    store: dict = {}
    _owned(monkeypatch, graph_id=None)
    _patch_cache(monkeypatch, store)
    from stratum.api.routers import bu

    asyncio.run(bu.get_learning_guide(RUN, "u"))
    asyncio.run(bu.get_learning_guide(RUN, "u"))
    # One key, not one per request: concurrent callers would each write their own.
    assert list(store) == [f"nograph:{RUN}"]


# ── against the real table ─────────────────────────────────────────────────


@pytest.mark.production_runtime
def test_real_round_trip_and_invalidate():
    """The migration's table and the cache's SQL must agree.

    ``production_runtime`` because it writes to a live database, which CI runs
    only on a dispatch. The fake above pins the behaviour; this pins the schema.

    It uses an existing run row rather than creating one (the table has an FK to
    a real substrate), and removes only the cache row it wrote, under a graph
    version nothing else could have used.
    """
    from stratum.db import query

    runs = query("SELECT id FROM stratum.book_reading_run LIMIT 1")
    if not runs:
        pytest.skip("no persisted book run to key the cache row against")
    run_id = runs[0]["id"]
    version = "g_TEST_canary"

    invalidate_run(run_id, graph_version=version)
    try:
        assert read_cache(run_id, version) is None
        payload = _guide(["first", "second"]).to_dict()
        write_cache(
            run_id=run_id,
            graph_version=version,
            book_id="sub_test",
            guide=payload,
            graph_id=version,
        )
        cached = read_cache(run_id, version)
        assert cached is not None, "the real table must return what the real write stored"
        assert [s["concept"] for s in cached["steps"]] == ["first", "second"]
        # An upsert, not an insert: a refresh under the same identity replaces.
        write_cache(
            run_id=run_id,
            graph_version=version,
            book_id="sub_test",
            guide=_guide(["replaced"]).to_dict(),
            graph_id=version,
        )
        assert [s["concept"] for s in read_cache(run_id, version)["steps"]] == ["replaced"]
        assert invalidate_run(run_id, graph_version=version) == 1
        assert read_cache(run_id, version) is None
    finally:
        # A canary version only. Never a row this test did not create.
        invalidate_run(run_id, graph_version=version)
