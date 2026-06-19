import asyncio
import concurrent.futures
import json
import logging
from typing import Any, AsyncIterator
from uuid import UUID

import asyncpg
from obase.persistence import PgPool, transaction, upsert_batch, vector_search, ensure_table
from aii.storage.backend import StorageBackend, EpistemicStore

logger = logging.getLogger(__name__)


def _run_coro(coro):
    """Run an async coroutine from sync context, even if an event loop is already running.
    Uses a thread executor when called from within an existing event loop (e.g. omodul
    sync callbacks triggered during an async engine run).

    Wraps the coro in cleanup logic that closes any PgPool instances created inside the
    thread's event loop before asyncio.run() returns — preventing orphaned background tasks
    (asyncpg keepalive/recycler futures) that would otherwise log
    'Future exception was never retrieved' when the thread loop closes.
    """
    try:
        asyncio.get_running_loop()
        # Already inside a running loop — offload to a new thread with its own loop

        async def _with_pool_cleanup():
            pool_ids_before = {id(p) for p in PgPool._registry.values()}
            try:
                return await coro
            finally:
                for p in list(PgPool._registry.values()):
                    if id(p) not in pool_ids_before:
                        try:
                            await p.close()
                        except Exception:
                            pass

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(asyncio.run, _with_pool_cleanup()).result()
    except RuntimeError:
        return asyncio.run(coro)


class PgBackend(StorageBackend, EpistemicStore):
    """PostgreSQL implementation of StorageBackend and EpistemicStore using obase.persistence."""

    def __init__(self, pool_name: str = "aii_pool", dsn: str | None = None):
        self.pool_name = pool_name
        import os
        self.dsn = dsn or os.getenv("AII_PG_DSN") or os.getenv("DATABASE_URL")
        if not self.dsn and os.getenv("POSTGRES_USER"):
            user = os.getenv("POSTGRES_USER")
            password = os.getenv("POSTGRES_PASSWORD")
            db = os.getenv("POSTGRES_DB")
            self.dsn = f"postgresql://{user}:{password}@localhost:5435/{db}"
        self._pool = None

    async def _ensure_pool(self) -> PgPool:
        # Check obase registry first
        try:
            pool = PgPool.get(self.pool_name)
            # Test if pool is alive and on the current loop
            async with pool.acquire() as conn:
                await conn.execute("SELECT 1")
            self._pool = pool
        except (KeyError, Exception):
            # If not in registry or pool is dead/on closed loop, try to clean up
            try:
                pool = PgPool.get(self.pool_name)
                # We can't easily close it if the loop is closed, 
                # but we MUST remove it from registry to recreate.
                # Accessing private _registry to force clear if needed
                PgPool._registry.pop(self.pool_name, None)
            except KeyError:
                pass
            
            if not self.dsn:
                raise ValueError("DSN must be provided to initialize PgPool")
            self._pool = await PgPool.create(name=self.pool_name, dsn=self.dsn, enable_vector=True)
        
        return self._pool

    # --- StorageBackend Implementation ---

    def put_node(self, node_id: str, payload: dict[str, Any]) -> None:
        """Synchronous wrapper for put_ku (standard omodul behavior)."""
        self.put_ku(payload)

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        return _run_coro(self.get_ku(node_id))

    def list_nodes(self) -> list[str]:
        async def _list():
            pool = await self._ensure_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch("SELECT ku_id FROM aii.ku")
                return [str(r["ku_id"]) for r in rows]
        return _run_coro(_list())

    def put_edge(self, src_id: str, relation: str, dst_id: str) -> None:
        async def _put():
            pool = await self._ensure_pool()
            row = {"src_id": UUID(src_id), "relation": relation, "dst_id": UUID(dst_id)}
            await upsert_batch(pool=pool, table="aii.edge", rows=[row], conflict_columns=["src_id", "relation", "dst_id"])
        _run_coro(_put())

    def list_edges(self, node_id: str | None = None) -> list[dict[str, Any]]:
        async def _list():
            pool = await self._ensure_pool()
            async with pool.acquire() as conn:
                if node_id:
                    rows = await conn.fetch("SELECT * FROM aii.edge WHERE src_id = $1 OR dst_id = $1", UUID(node_id))
                else:
                    rows = await conn.fetch("SELECT * FROM aii.edge")
                return [dict(r) for r in rows]
        return _run_coro(_list())

    # --- EpistemicStore Implementation ---

    def put_ku(self, ku: dict[str, Any]) -> None:
        """Sync entry point called by omodul. Delegates to async impl via _run_coro."""
        _run_coro(self._put_ku_async(ku))

    async def _put_ku_async(self, ku: dict[str, Any]) -> None:
        """Async KU write. Uses a fresh direct connection (not the shared pool) so it
        works correctly when invoked from a thread executor with its own event loop."""
        import asyncpg as _asyncpg
        if not self.dsn:
            raise ValueError("DSN must be provided to initialize PgPool")

        ku_id = ku.get("ku_id")
        if not ku_id:
            raise ValueError("ku_id is required")
        if isinstance(ku_id, str):
            ku_id = UUID(ku_id)

        import hashlib as _hashlib
        fingerprint = ku.get("fingerprint")
        if not fingerprint:
            # Derive fingerprint from natural_text so dedup still works
            _text = ku.get("natural_text", str(ku_id))
            fingerprint = _hashlib.sha256(_text.encode()).hexdigest()[:32]

        conn = await _asyncpg.connect(self.dsn)
        try:
            from pgvector.asyncpg import register_vector as _register_vector
            await _register_vector(conn)
            async with conn.transaction():
                # 1. Fingerprint de-duplication
                if fingerprint:
                    existing = await conn.fetchrow(
                        "SELECT ku_id FROM aii.ku WHERE fingerprint = $1 AND is_quarantined = FALSE",
                        fingerprint
                    )
                    if existing and existing["ku_id"] != ku_id:
                        logger.info("KU fingerprint dup %s → skipping", fingerprint[:8])
                        return

                # 2. Get old grade for audit
                old_row = await conn.fetchrow(
                    "SELECT grade FROM aii.ku WHERE ku_id = $1 FOR UPDATE", ku_id
                )
                old_grade = old_row["grade"] if old_row else None
                new_grade = ku.get("grade", "unverified")

                # 3. Build column lists dynamically from what's in ku
                _allowed = {
                    "ku_id", "project_id", "natural_text", "knowledge_type",
                    "symbolic_form", "embedding", "grade", "source",
                    "verified", "is_quarantined", "provenance", "fingerprint",
                    "is_synthesis", "synthesis_meta", "substrate_id",
                    "sources", "merge_count",
                }
                row = {k: v for k, v in ku.items() if k in _allowed}
                row["ku_id"] = ku_id
                row["fingerprint"] = fingerprint
                for json_field in ("symbolic_form", "provenance", "synthesis_meta"):
                    if json_field in row and isinstance(row[json_field], dict):
                        row[json_field] = json.dumps(row[json_field])
                if "sources" in row and isinstance(row["sources"], list):
                    row["sources"] = json.dumps(row["sources"])

                cols = list(row.keys())
                placeholders = ", ".join(f"${i+1}" for i in range(len(cols)))
                updates = ", ".join(
                    f"{c}=EXCLUDED.{c}" for c in cols if c != "ku_id"
                )
                sql = (
                    f"INSERT INTO aii.ku ({', '.join(cols)}) VALUES ({placeholders}) "
                    f"ON CONFLICT (ku_id) DO UPDATE SET {updates}"
                )
                await conn.execute(sql, *[row[c] for c in cols])

                # 4. Record state change if grade changed
                if old_grade != new_grade:
                    await conn.execute(
                        """
                        INSERT INTO aii.ku_state_history
                            (ku_id, from_grade, to_grade, trigger, decision_trail)
                        VALUES ($1, $2, $3, $4, $5)
                        """,
                        ku_id, old_grade, new_grade, "put_ku",
                        json.dumps(ku.get("decision_trail", {})),
                    )
        finally:
            await conn.close()

    async def get_ku(self, ku_id: str) -> dict[str, Any] | None:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM aii.ku WHERE ku_id = $1", UUID(ku_id))
            return dict(row) if row else None

    async def query_ku_by_grade(self, grade: str) -> list[dict[str, Any]]:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM aii.ku WHERE grade = $1", grade)
            return [dict(r) for r in rows]

    async def search_ku_by_vector(self, query_vector: list[float], limit: int = 5) -> list[dict[str, Any]]:
        pool = await self._ensure_pool()
        # Use direct asyncpg query with vector distance operator
        # Since we use enable_vector=True, asyncpg handles list[float] correctly
        sql = f"""
            SELECT *, embedding <=> $1 AS distance
            FROM aii.ku
            ORDER BY embedding <=> $1
            LIMIT $2
        """
        async with pool.acquire() as conn:
            records = await conn.fetch(sql, query_vector, limit)
        return [dict(r) for r in records]

    async def record_state_change(self, ku_id: str, to_grade: str, reason: str | None = None, decision_trail: dict[str, Any] | None = None) -> None:
        pool = await self._ensure_pool()
        async with transaction(pool) as conn:
            old_row = await conn.fetchrow("SELECT grade FROM aii.ku WHERE ku_id = $1 FOR UPDATE", UUID(ku_id))
            if not old_row:
                raise ValueError(f"KU {ku_id} not found")
            
            from_grade = old_row["grade"]
            await conn.execute("UPDATE aii.ku SET grade = $1, updated_at = CURRENT_TIMESTAMP WHERE ku_id = $2", to_grade, UUID(ku_id))
            await conn.execute(
                """
                INSERT INTO aii.ku_state_history (ku_id, from_grade, to_grade, trigger, decision_trail)
                VALUES ($1, $2, $3, $4, $5)
                """,
                UUID(ku_id), from_grade, to_grade, reason or "manual_update", json.dumps(decision_trail or {})
            )

    async def quarantine_ku(self, ku_id: str, reason: str) -> None:
        await self.record_state_change(ku_id, to_grade="quarantined", reason=f"quarantine: {reason}")
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE aii.ku SET is_quarantined = TRUE WHERE ku_id = $1", UUID(ku_id))

    # --- New Methods for Failure Lessons and Capability Gaps ---

    def record_failure_lesson(self, trigger_type: str, subject_ref: str, evidence: dict, lesson: str) -> None:
        async def _record():
            pool = await self._ensure_pool()
            sql = """
                INSERT INTO aii.failure_lesson (trigger_type, subject_ref, evidence, lesson, occurrences)
                VALUES ($1, $2, $3, $4, 1)
                ON CONFLICT (trigger_type, COALESCE(subject_ref, ''))
                DO UPDATE SET
                    occurrences = aii.failure_lesson.occurrences + 1,
                    evidence = EXCLUDED.evidence,
                    lesson = EXCLUDED.lesson,
                    updated_at = NOW();
            """
            async with pool.acquire() as conn:
                await conn.execute(sql, trigger_type, subject_ref, json.dumps(evidence), lesson)
        asyncio.run(_record())

    async def record_failure_lesson_async(self, trigger_type: str, subject_ref: str | None, evidence: dict, lesson: str) -> None:
        pool = await self._ensure_pool()
        sql = """
            INSERT INTO aii.failure_lesson (trigger_type, subject_ref, evidence, lesson, occurrences)
            VALUES ($1, $2, $3, $4, 1)
            ON CONFLICT (trigger_type, COALESCE(subject_ref, ''))
            DO UPDATE SET
                occurrences = aii.failure_lesson.occurrences + 1,
                evidence = EXCLUDED.evidence,
                lesson = EXCLUDED.lesson,
                updated_at = NOW();
        """
        async with pool.acquire() as conn:
            await conn.execute(sql, trigger_type, subject_ref, json.dumps(evidence), lesson)

    async def has_failure_lesson_async(self, trigger_type: str, subject_ref: str) -> bool:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM aii.failure_lesson WHERE trigger_type = $1 AND subject_ref = $2",
                trigger_type, subject_ref
            )
            return row is not None

    def query_failure_lessons(self, trigger_type: str = None, subject_ref: str = None) -> list[dict]:
        async def _query():
            pool = await self._ensure_pool()
            sql = "SELECT * FROM aii.failure_lesson WHERE 1=1"
            params = []
            if trigger_type:
                params.append(trigger_type)
                sql += f" AND trigger_type = ${len(params)}"
            if subject_ref:
                params.append(subject_ref)
                sql += f" AND subject_ref = ${len(params)}"
            
            async with pool.acquire() as conn:
                rows = await conn.fetch(sql, *params)
                return [dict(r) for r in rows]
        return asyncio.run(_query())

    def has_failure_lesson(self, trigger_type: str, subject_ref: str) -> bool:
        async def _has():
            pool = await self._ensure_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT 1 FROM aii.failure_lesson WHERE trigger_type = $1 AND subject_ref = $2",
                    trigger_type, subject_ref
                )
                return row is not None
        return asyncio.run(_has())

    def save_capability_gap(self, report: dict) -> None:
        async def _save():
            pool = await self._ensure_pool()
            async with pool.acquire() as conn:
                await conn.execute("INSERT INTO aii.capability_gap (report) VALUES ($1)", json.dumps(report))
        asyncio.run(_save())

    def get_latest_capability_gap(self) -> dict | None:
        async def _get():
            pool = await self._ensure_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow("SELECT report FROM aii.capability_gap ORDER BY snapshot_at DESC LIMIT 1")
                return json.loads(row["report"]) if row else None
        return asyncio.run(_get())

    def get_grade_distribution(self) -> dict:
        async def _get():
            pool = await self._ensure_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT knowledge_type, grade, COUNT(*) as count FROM aii.ku GROUP BY knowledge_type, grade"
                )
                res = {}
                for r in rows:
                    kt = r["knowledge_type"]
                    grade = r["grade"]
                    count = r["count"]
                    if kt not in res: res[kt] = {}
                    res[kt][grade] = count
                return res
        return asyncio.run(_get())

    async def get_grade_distribution_async(self) -> dict:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT knowledge_type, grade, COUNT(*) as count FROM aii.ku GROUP BY knowledge_type, grade"
            )
            res = {}
            for r in rows:
                kt = r["knowledge_type"]
                grade = r["grade"]
                count = r["count"]
                if kt not in res: res[kt] = {}
                res[kt][grade] = count
            return res

    def get_stale_unverified(self, days: int) -> list[dict]:
        async def _get():
            pool = await self._ensure_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT * FROM aii.ku WHERE grade = 'unverified' AND provenance IS NOT NULL AND updated_at < NOW() - $1::interval",
                    f"{days} days"
                )
                return [dict(r) for r in rows]
        return asyncio.run(_get())

    async def get_stale_unverified_async(self, days: int) -> list[dict]:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM aii.ku WHERE grade = 'unverified' AND provenance IS NOT NULL AND updated_at < NOW() - make_interval(days => $1)",
                days
            )
            return [dict(r) for r in rows]

    def get_isolated_kus(self) -> list[str]:
        async def _get():
            pool = await self._ensure_pool()
            async with pool.acquire() as conn:
                sql = """
                    SELECT ku_id FROM aii.ku
                    WHERE ku_id NOT IN (SELECT src_id FROM aii.edge)
                      AND ku_id NOT IN (SELECT dst_id FROM aii.edge)
                """
                rows = await conn.fetch(sql)
                return [str(r["ku_id"]) for r in rows]
        return asyncio.run(_get())

    async def get_isolated_kus_async(self) -> list[str]:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            sql = """
                SELECT ku_id FROM aii.ku
                WHERE ku_id NOT IN (SELECT src_id FROM aii.edge)
                  AND ku_id NOT IN (SELECT dst_id FROM aii.edge)
            """
            rows = await conn.fetch(sql)
            return [str(r["ku_id"]) for r in rows]

    async def query_failure_lessons_async(self, trigger_type: str = None, subject_ref: str = None) -> list[dict]:
        pool = await self._ensure_pool()
        sql = "SELECT * FROM aii.failure_lesson WHERE 1=1"
        params = []
        if trigger_type:
            params.append(trigger_type)
            sql += f" AND trigger_type = ${len(params)}"
        if subject_ref:
            params.append(subject_ref)
            sql += f" AND subject_ref = ${len(params)}"
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
            return [dict(r) for r in rows]

    async def save_capability_gap_async(self, report: dict) -> None:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            await conn.execute("INSERT INTO aii.capability_gap (report) VALUES ($1)", json.dumps(report))

    async def get_latest_capability_gap_async(self) -> dict | None:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT report FROM aii.capability_gap ORDER BY snapshot_at DESC LIMIT 1")
            return json.loads(row["report"]) if row else None

    # --- Deep Understanding methods ---

    async def list_kus(self) -> list[dict[str, Any]]:
        """Return all non-quarantined KUs (detail only, not synthesis)."""
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM aii.ku WHERE is_quarantined = FALSE ORDER BY created_at"
            )
            return [dict(r) for r in rows]

    async def add_relation_edge(
        self,
        src_id: str,
        relation_type: str,
        dst_id: str,
        *,
        grade: str = "unverified",
        evidence: dict | None = None,
        extraction_method: str = "rule",
    ) -> None:
        """Upsert a rich relation edge with grade, evidence, and extraction method."""
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO aii.edge (src_id, relation, dst_id, relation_type, grade, evidence, extraction_method)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (src_id, relation, dst_id) DO UPDATE SET
                    relation_type = EXCLUDED.relation_type,
                    grade = EXCLUDED.grade,
                    evidence = EXCLUDED.evidence,
                    extraction_method = EXCLUDED.extraction_method
                """,
                UUID(src_id), relation_type, UUID(dst_id),
                relation_type, grade,
                json.dumps(evidence or {}), extraction_method,
            )

    async def get_relation_edges(self, ku_id: str | None = None) -> list[dict[str, Any]]:
        """Return relation edges with grade and extraction metadata."""
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            if ku_id:
                rows = await conn.fetch(
                    "SELECT * FROM aii.edge WHERE src_id = $1 OR dst_id = $1",
                    UUID(ku_id),
                )
            else:
                rows = await conn.fetch("SELECT * FROM aii.edge")
            return [dict(r) for r in rows]

    async def get_ku_embeddings(self, ku_ids: list[str]) -> dict[str, list[float]]:
        """Return {ku_id: embedding_vector} for given ku_ids that have embeddings."""
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT ku_id, embedding FROM aii.ku WHERE ku_id = ANY($1) AND embedding IS NOT NULL",
                [UUID(kid) for kid in ku_ids],
            )
            return {str(r["ku_id"]): list(r["embedding"]) for r in rows}

    async def is_substrate_ingested(self, substrate_id: str) -> bool:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM aii.ingested_substrate WHERE substrate_id = $1",
                substrate_id,
            )
            return row is not None

    async def mark_substrate_ingested(
        self, substrate_id: str, title: str, medium: str, ku_count: int
    ) -> None:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO aii.ingested_substrate (substrate_id, title, medium, ku_count)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (substrate_id) DO UPDATE SET ku_count = EXCLUDED.ku_count
                """,
                substrate_id, title, medium, ku_count,
            )

    async def find_nearest_ku(
        self, embedding: list[float], exclude_synthesis: bool = True
    ) -> dict | None:
        """Return the single nearest KU by cosine distance (pgvector <=>), or None.
        Result includes 'distance' field (0=identical, 2=opposite)."""
        pool = await self._ensure_pool()
        clauses = ["embedding IS NOT NULL"]
        if exclude_synthesis:
            clauses.append("(is_synthesis IS NOT TRUE)")
        where = " AND ".join(clauses)
        sql = f"""
            SELECT ku_id, natural_text, grade, knowledge_type,
                   (embedding <=> $1) AS distance
            FROM aii.ku
            WHERE {where}
            ORDER BY embedding <=> $1
            LIMIT 1
        """
        async with pool.acquire() as conn:
            row = await conn.fetchrow(sql, embedding)
        return dict(row) if row else None

    async def merge_ku_sources(
        self, existing_ku_id: str, substrate_id: str, natural_text: str
    ) -> None:
        """Append a source record to existing KU's sources array and increment merge_count.
        Preserves all expressions — multi-perspective is better than lost provenance."""
        from datetime import datetime, timezone
        source_entry = json.dumps([{
            "substrate_id": substrate_id,
            "natural_text": natural_text[:200],
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }])
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE aii.ku
                SET sources = COALESCE(sources, '[]'::jsonb) || $2::jsonb,
                    merge_count = COALESCE(merge_count, 1) + 1
                WHERE ku_id = $1::uuid
                """,
                existing_ku_id, source_entry,
            )

    async def mark_deep_understood(self, substrate_id: str) -> None:
        """Set deep_understood_at = NOW() for a substrate after deep understanding pipeline completes."""
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE aii.ingested_substrate SET deep_understood_at = NOW() WHERE substrate_id = $1",
                substrate_id,
            )

    async def list_substrates_needing_deep_understanding(self, limit: int = 2) -> list[dict]:
        """Return substrates that have KUs but haven't had deep understanding run yet."""
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT substrate_id, title, medium
                FROM aii.ingested_substrate
                WHERE ku_count > 0 AND deep_understood_at IS NULL
                ORDER BY ingested_at
                LIMIT $1
                """,
                limit,
            )
        return [dict(r) for r in rows]

    async def search_synthesis_kus(self, query_vector: list[float], limit: int = 5) -> list[dict[str, Any]]:
        """Vector search restricted to synthesis (is_synthesis=true) KUs."""
        pool = await self._ensure_pool()
        sql = """
            SELECT *, embedding <=> $1 AS distance
            FROM aii.ku
            WHERE is_synthesis = TRUE AND embedding IS NOT NULL
            ORDER BY embedding <=> $1
            LIMIT $2
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, query_vector, limit)
            return [dict(r) for r in rows]
