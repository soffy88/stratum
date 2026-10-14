"""Cache for the dependency-ordered learning guide — task E persistence.

The guide is a rendering of the run's reasoning graph: an expensive topological
sort over every concept node and dependency edge, and a stable result for the
life of that graph. Computing it per request meant a book with 1000 concept nodes
re-derived the ordering on every page load, which is what the guide endpoint
was doing.

This is a cache, not an authority. ``build_guide_payload`` recomputes from the
database whenever the row is missing or the graph has been rebuilt, so deleting
every row costs a recomputation and nothing else. The docstring in
``bu_v2_learning_guide.py`` calls the guide a rendering of a verified BU and
forbids it becoming a second authority — this module preserves that by making
the graph identity part of the cache key.

Why the graph identity and not the run alone: a graph rebuild writes new node ids
and edges under a new ``reasoning_graph_id`` while the ``run_id`` is unchanged. A
cache keyed only on the run would then serve a guide ordered by a graph that no
longer exists, with concept ids that resolve to nothing. That is a silent wrong
answer, so the graph id is part of the key and a rebuild is simply a miss.
"""

from __future__ import annotations

import json
from typing import Any


def normalise(payload: Any) -> Any:
    """Decode a jsonb value the same way the router's ``_j`` does.

    psycopg2 is configured to hand jsonb back as text, and older rows were written
    double-encoded, so a payload can be text holding text holding JSON.
    """
    if not isinstance(payload, str):
        return payload
    for _ in range(2):
        try:
            payload = json.loads(payload)
        except ValueError:
            return payload
        if not isinstance(payload, str):
            break
    return payload


def _query(sql: str, params: dict, connection: Any = None) -> list[dict]:
    """Run a read, on the injected connection when one is given.

    The seam exists for the same reason ``FrozenKUReader`` has one: a test must be
    able to exercise the SQL without a live database, and the query shape is the
    part worth pinning.
    """
    if connection is not None:
        with connection.cursor() as cur:
            cur.execute(sql, params)
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    from stratum.db import query

    return query(sql, params)


def _execute(sql: str, params: dict, connection: Any = None) -> None:
    """Run DML, on the injected connection when one is given."""
    if connection is not None:
        with connection.cursor() as cur:
            cur.execute(sql, params)
        return
    from stratum.db import execute

    execute(sql, params)


def guide_version_of(graph_id: str | None, run_id: str) -> str:
    """The cache key's graph component.

    A run with no persisted graph still gets a stable key, built from the run id,
    so the same run never produces two cache rows for the same graph identity.
    Without this the key would be empty and every concurrent request would race to
    write, each believing it had computed the only guide.
    """
    return graph_id if graph_id else f"nograph:{run_id}"


def read_cache(run_id: str, graph_version: str, connection: Any = None) -> dict | None:
    """The cached guide payload for this run and graph, or None on a miss."""
    rows = _query(
        """
        SELECT payload, step_count, graph_version FROM stratum.bu2_learning_guide
        WHERE run_id = %(run_id)s AND graph_version = %(v)s
        LIMIT 1
        """,
        {"run_id": run_id, "v": graph_version},
        connection,
    )
    if not rows:
        return None
    payload = normalise(rows[0].get("payload"))
    return payload if isinstance(payload, dict) else None


def write_cache(
    *,
    run_id: str,
    graph_version: str,
    book_id: str | None,
    guide: dict,
    graph_id: str | None,
    engine_version: str | None = None,
    connection: Any = None,
) -> dict:
    """Persist a computed guide payload and return it.

    ``guide`` is already the payload (``LearningGuide.to_dict()``): the router
    caches the full guide and pages over it afterwards, so the cached form and the
    returned form must be identical or page two of a paged client would disagree
    with page one.

    A failure to write is not a failure to serve: the caller already holds the
    guide, so a cache that cannot be written is a performance problem rather than
    a correctness one. The narrow ``except`` is deliberate — a full disk or a
    read-only replica must degrade to uncached, not 500 the page — and it returns
    the payload it was given so the response is identical either way.
    """
    payload = guide
    step_count = len(payload.get("steps") or [])
    try:
        if connection is None:
            from stratum.db import write as _write
        else:
            _write = connection.write

        # Upsert on the primary key: ?fresh=1 recomputes under the same
        # (run, graph) identity, and a plain INSERT would collide and leave the
        # previous row in place — so a refresh would look like it had worked.
        _write(
            "bu2_learning_guide",
            {
                "run_id": run_id,
                "graph_version": graph_version,
                "book_id": book_id,
                "payload": payload,
                "step_count": step_count,
                "graph_id": graph_id,
                "engine_version": engine_version,
            },
            conflict_on=["run_id", "graph_version"],
            returning="run_id",
        )
    except Exception:
        # Caching is an optimisation. An unwritable cache — full disk, read-only
        # replica, a foreign-key violation from a run that was rolled back —
        # must never turn a correct answer into an error. The payload is returned
        # unchanged, so the response is identical either way.
        pass
    return payload


def invalidate_run(run_id: str, *, graph_version: str | None = None, connection: Any = None) -> int:
    """Drop cached guides for a run.

    Called when the run's graph is rebuilt, so a stale ordering is never served.
    Without a graph_version it drops every version, which is what a full rebuild
    wants. Returns how many rows were removed, so a caller can tell a rebuild
    that actually cleared something from one that had nothing to clear.
    """
    if graph_version:
        counted = _query(
            "SELECT count(*) AS n FROM stratum.bu2_learning_guide "
            "WHERE run_id = %(r)s AND graph_version = %(v)s",
            {"r": run_id, "v": graph_version},
            connection,
        )
        _execute(
            "DELETE FROM stratum.bu2_learning_guide WHERE run_id = %(r)s AND graph_version = %(v)s",
            {"r": run_id, "v": graph_version},
            connection,
        )
    else:
        counted = _query(
            "SELECT count(*) AS n FROM stratum.bu2_learning_guide WHERE run_id = %(r)s",
            {"r": run_id},
            connection,
        )
        _execute(
            "DELETE FROM stratum.bu2_learning_guide WHERE run_id = %(r)s",
            {"r": run_id},
            connection,
        )
    return int(counted[0]["n"]) if counted else 0
