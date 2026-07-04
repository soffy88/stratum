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

# Canonical set of valid EpistemicGrade values — must match helios-blocks EPISTEMIC_GRADE_LABEL keys.
# Any grade value not in this set is a bug in the upstream code that produced it.
VALID_EPISTEMIC_GRADES: frozenset[str] = frozenset(
    {
        "proven",
        "high",
        "moderate",
        "low",
        "very_low",
        "unverified",
        "contradicted",
        "pending_verification",
    }
)


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
        # No running loop (plain thread context, e.g. run_in_executor callback).
        # Apply the same pool-cleanup wrapper so that any pools created inside
        # asyncio.run() are closed before the thread loop exits — prevents the
        # zombie asyncpg connections that caused "too many clients" errors.
        async def _with_pool_cleanup_sync():
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

        return asyncio.run(_with_pool_cleanup_sync())


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
        self._main_loop: asyncio.AbstractEventLoop | None = None

    async def _ensure_pool(self) -> PgPool:
        current_loop = asyncio.get_running_loop()

        # ── Main event loop (FastAPI/uvicorn) ──────────────────────────────
        # After first initialisation self._main_loop is set; subsequent calls on
        # the same loop return the cached pool immediately — no health-check, no
        # acquire() round-trip.  This eliminates the 31s "pool acquire hang" that
        # occurred when a thread's asyncio.run() health-check waited indefinitely
        # on a pool that belonged to the FastAPI loop.
        if self._main_loop is None:
            self._main_loop = current_loop  # first call — record the main loop

        if current_loop is self._main_loop:
            if self._pool is not None:
                return self._pool  # fast path — no DB round-trip
            # First time on main loop: grab from registry or create fresh
            try:
                self._pool = PgPool.get(self.pool_name)
            except KeyError:
                if not self.dsn:
                    raise ValueError("DSN must be provided to initialize PgPool")
                self._pool = await PgPool.create(
                    name=self.pool_name, dsn=self.dsn, enable_vector=True
                )
            return self._pool

        # ── Thread / secondary event loop (e.g. asyncio.run() in _run_coro) ─
        # Use a loop-specific pool name so thread pools never overwrite the main
        # pool in the global PgPool registry.  _run_coro's cleanup wrapper closes
        # these temporary pools after the coroutine finishes, preventing zombie
        # connections from accumulating (was the source of the 86 idle connections).
        thread_pool_name = f"{self.pool_name}_{id(current_loop)}"
        try:
            return PgPool.get(thread_pool_name)
        except KeyError:
            pass
        if not self.dsn:
            raise ValueError("DSN must be provided to initialize PgPool")
        return await PgPool.create(name=thread_pool_name, dsn=self.dsn, enable_vector=True)

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
                rows = await conn.fetch("SELECT ku_id FROM aii.ku_onto")
                return [str(r["ku_id"]) for r in rows]

        return _run_coro(_list())

    def put_edge(self, src_id: str, relation: str, dst_id: str) -> None:
        async def _put():
            pool = await self._ensure_pool()
            row = {"src_id": src_id, "relation": relation, "dst_id": dst_id}
            await upsert_batch(
                pool=pool,
                table="aii.edge_onto",
                rows=[row],
                conflict_columns=["src_id", "relation", "dst_id"],
            )

        _run_coro(_put())

    def list_edges(self, node_id: str | None = None) -> list[dict[str, Any]]:
        async def _list():
            pool = await self._ensure_pool()
            async with pool.acquire() as conn:
                if node_id:
                    rows = await conn.fetch(
                        "SELECT * FROM aii.edge_onto WHERE src_id = $1 OR dst_id = $1", node_id
                    )
                else:
                    rows = await conn.fetch("SELECT * FROM aii.edge_onto")
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
            ku_id = ku_id

        import hashlib as _hashlib

        fingerprint = ku.get("fingerprint")
        if not fingerprint:
            # Derive fingerprint from natural_text so dedup still works
            _text = ku.get("natural_text", str(ku_id))
            fingerprint = _hashlib.sha256(_text.encode()).hexdigest()[:32]

        # Grade validation — reject and record before opening any connection
        _grade_to_write = ku.get("grade", "unverified")
        if _grade_to_write not in VALID_EPISTEMIC_GRADES:
            await self.record_failure_lesson_async(
                trigger_type="invalid_grade",
                subject_ref=_grade_to_write,
                evidence={"ku_id": str(ku_id), "grade": _grade_to_write, "context": "put_ku"},
                lesson=(
                    f"grade='{_grade_to_write}' is not a valid EpistemicGrade; "
                    f"fix the upstream code that produced this value"
                ),
            )
            raise ValueError(
                f"invalid grade '{_grade_to_write}' for KU {ku_id}; "
                f"valid grades: {sorted(VALID_EPISTEMIC_GRADES)}"
            )

        conn = await _asyncpg.connect(self.dsn)
        try:
            from pgvector.asyncpg import register_vector as _register_vector

            await _register_vector(conn)
            async with conn.transaction():
                # 1. Fingerprint de-duplication
                if fingerprint:
                    existing = await conn.fetchrow(
                        "SELECT ku_id FROM aii.ku_onto WHERE fingerprint = $1 AND is_quarantined = FALSE",
                        fingerprint,
                    )
                    if existing and existing["ku_id"] != ku_id:
                        logger.info("KU fingerprint dup %s → skipping", fingerprint[:8])
                        return

                # 2. Get old grade for audit
                old_row = await conn.fetchrow(
                    "SELECT grade FROM aii.ku_onto WHERE ku_id = $1 FOR UPDATE", ku_id
                )
                old_grade = old_row["grade"] if old_row else None
                new_grade = ku.get("grade", "unverified")

                # 3. Build column lists dynamically from what's in ku
                _allowed = {
                    "ku_id",
                    "project_id",
                    "natural_text",
                    "knowledge_type",
                    "symbolic_form",
                    "embedding",
                    "grade",
                    "source",
                    "verified",
                    "is_quarantined",
                    "provenance",
                    "fingerprint",
                    "is_synthesis",
                    "synthesis_meta",
                    "substrate_id",
                    "sources",
                    "merge_count",
                    "natural_text_zh",
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
                placeholders = ", ".join(f"${i + 1}" for i in range(len(cols)))
                updates = ", ".join(f"{c}=EXCLUDED.{c}" for c in cols if c != "ku_id")
                sql = (
                    f"INSERT INTO aii.ku_onto ({', '.join(cols)}) VALUES ({placeholders}) "
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
                        ku_id,
                        old_grade,
                        new_grade,
                        "put_ku",
                        json.dumps(ku.get("decision_trail", {})),
                    )

                # 5. Save concept links from tags (concept = KU零件, 不带grade, 不当知识)
                tags = ku.get("tags")
                if tags and isinstance(tags, list):
                    cleaned = list({t.strip().lower() for t in tags if t and str(t).strip()})
                    for tag in cleaned:
                        if not tag:
                            continue
                        c_row = await conn.fetchrow(
                            """
                            INSERT INTO aii.concept_onto (name)
                            VALUES ($1)
                            ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                            RETURNING concept_id
                            """,
                            tag,
                        )
                        if c_row:
                            inserted = await conn.fetchrow(
                                """
                                INSERT INTO aii.ku_concept_onto (ku_id, concept_id)
                                VALUES ($1, $2)
                                ON CONFLICT DO NOTHING
                                RETURNING concept_id
                                """,
                                ku_id,
                                c_row["concept_id"],
                            )
                            if inserted:
                                await conn.execute(
                                    "UPDATE aii.concept_onto SET ku_count = ku_count + 1 WHERE concept_id = $1",
                                    c_row["concept_id"],
                                )
        finally:
            await conn.close()

    async def get_ku(self, ku_id: str) -> dict[str, Any] | None:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM aii.ku_onto WHERE ku_id = $1", ku_id)
            return dict(row) if row else None

    async def query_ku_by_grade(self, grade: str) -> list[dict[str, Any]]:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM aii.ku_onto WHERE grade = $1", grade)
            return [dict(r) for r in rows]

    async def search_ku_by_vector(
        self,
        query_vector: list[float],
        limit: int = 5,
        knowledge_type: "str | list[str] | None" = None,
    ) -> list[dict[str, Any]]:
        """向量检索 KU. ★knowledge_type 作为一等检索维度: 传单类或多类 → 只在该六类内检索
        (走 idx_ku_onto_type 索引). 不传 → 全类."""
        pool = await self._ensure_pool()
        params: list = [query_vector, limit]
        where = "WHERE valid_until IS NULL"  # 只检索当前版本(被 supersede 的旧版排除)
        if knowledge_type:
            kts = [knowledge_type] if isinstance(knowledge_type, str) else list(knowledge_type)
            params.append(kts)
            where += " AND knowledge_type = ANY($3)"
        sql = f"""
            SELECT *, embedding <=> $1 AS distance
            FROM aii.ku_onto
            {where}
            ORDER BY embedding <=> $1
            LIMIT $2
        """
        async with pool.acquire() as conn:
            records = await conn.fetch(sql, *params)
        return [dict(r) for r in records]

    async def search_ku_hybrid(
        self,
        query_vector: list[float],
        query_text: str,
        limit: int = 5,
        channel_depth: int = 40,
        knowledge_type: "str | list[str] | None" = None,
    ) -> list[dict[str, Any]]:
        """★混合检索: dense 主序 + lexical 召回回填(provably 不回退 dense).
        本库 KU 已精炼, dense 强(评测 recall@10≈.93/MRR≈.82); 等权/加权 RRF 都会让 dense 顶命中被
        '双通道命中但离题'的候选挤下 → MRR 反降. 故改 dense-primary + lexical-backfill:
        - dense 命中按 dense 名次在前(gold 保持 dense 名次 → MRR/nDCG 不降)
        - lexical 独有命中(dense 漏的专名/精确术语)回填在后 → 只增召回
        作为重排候选池时即 dense∪lexical 全召回. 返回含 distance 与 fusion_rank(升序=优)."""
        pool = await self._ensure_pool()
        kt_filter = ""
        params: list = [query_vector, query_text or "", channel_depth, limit]
        if knowledge_type:
            kts = [knowledge_type] if isinstance(knowledge_type, str) else list(knowledge_type)
            params.append(kts)
            kt_filter = "AND knowledge_type = ANY($5)"
        sql = f"""
            WITH dense AS (
                SELECT ku_id, row_number() OVER (ORDER BY embedding <=> $1) AS d_rnk
                FROM aii.ku_onto
                WHERE embedding IS NOT NULL AND valid_until IS NULL {kt_filter}
                ORDER BY embedding <=> $1 LIMIT $3
            ),
            lex AS (
                SELECT ku_id, row_number() OVER (ORDER BY ts_rank_cd(fts, q) DESC) AS l_rnk
                FROM aii.ku_onto, websearch_to_tsquery('english', $2) q
                WHERE fts @@ q AND valid_until IS NULL {kt_filter}
                ORDER BY ts_rank_cd(fts, q) DESC LIMIT $3
            ),
            merged AS (
                SELECT ku_id, COALESCE(d_rnk, 100000 + l_rnk) AS ord
                FROM dense FULL OUTER JOIN lex USING (ku_id)
            )
            SELECT k.*, m.ord AS fusion_rank, (k.embedding <=> $1) AS distance
            FROM merged m JOIN aii.ku_onto k USING (ku_id)
            ORDER BY m.ord ASC LIMIT $4
        """
        async with pool.acquire() as conn:
            records = await conn.fetch(sql, *params)
        return [dict(r) for r in records]

    async def supersede_ku(self, old_ku_id: str, new_ku_id: str | None = None) -> None:
        """★时序版本: 把旧 KU 标记为被取代(valid_until=now, superseded_by=new), 而非硬删.
        保留历史、可回溯; 检索默认只返回 valid_until IS NULL 的当前版本.
        re-ingest 应调本方法替代'删旧行', 让知识演化留痕."""
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE aii.ku_onto SET valid_until = now(), superseded_by = $2, updated_at = now() "
                "WHERE ku_id = $1 AND valid_until IS NULL",
                old_ku_id,
                new_ku_id,
            )

    async def reingest_substrate(self, substrate_id: str, reason: str) -> dict[str, Any]:
        """Force-supersede a previously-ingested substrate so it can be re-extracted.

        auto_ingest.is_substrate_ingested()/get_substrate_id_by_title() permanently
        skip anything already in ingested_substrate — there was no path to ever
        update a book once ingested. This retires every currently-valid KU for the
        substrate via supersede_ku (history preserved, not hard-deleted) and clears
        its ingested_substrate row so the next flywheel pass re-extracts it fresh.
        No 1:1 old->new KU pairing is attempted (re-extraction may chunk
        differently) — superseded_by is left NULL, meaning "retired by re-ingest",
        not "replaced by this specific KU".
        """
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            ku_ids = [
                r["ku_id"]
                for r in await conn.fetch(
                    "SELECT ku_id FROM aii.ku_onto WHERE substrate_id = $1 AND valid_until IS NULL",
                    substrate_id,
                )
            ]
            for ku_id in ku_ids:
                await conn.execute(
                    "UPDATE aii.ku_onto SET valid_until = now(), updated_at = now() WHERE ku_id = $1",
                    ku_id,
                )
                await conn.execute(
                    """
                    INSERT INTO aii.ku_state_history (ku_id, from_grade, to_grade, trigger, decision_trail)
                    SELECT ku_id, grade, grade, $2, $3 FROM aii.ku_onto WHERE ku_id = $1
                    """,
                    ku_id,
                    f"reingest: {reason}",
                    json.dumps(
                        {
                            "action": "reingest_supersede",
                            "substrate_id": substrate_id,
                            "reason": reason,
                        }
                    ),
                )
            await conn.execute(
                "DELETE FROM aii.ingested_substrate WHERE substrate_id = $1", substrate_id
            )
        return {"substrate_id": substrate_id, "superseded_ku_count": len(ku_ids)}

    async def record_state_change(
        self,
        ku_id: str,
        to_grade: str,
        reason: str | None = None,
        decision_trail: dict[str, Any] | None = None,
        grounded_by: dict[str, Any] | None = None,
    ) -> None:
        """Transition a KU's grade, with an audit row in ku_state_history.

        `to_grade` must be one of aii.service.onto_vocab.VALID_GRADES — that's
        the single source of truth the DB's ku_onto_grade_check constraint is
        generated from. Validating here turns a caller bug into a clear
        ValueError instead of a raw Postgres CheckViolation surfacing deep
        inside a transaction.

        Pass `grounded_by` when transitioning to "verified" — ck_ku_onto_grade_mandate
        rejects grade='verified' unless grounded_by->>'method' != 'default'.
        """
        from aii.service.onto_vocab import VALID_GRADES

        if to_grade not in VALID_GRADES:
            raise ValueError(
                f"invalid to_grade '{to_grade}' for KU {ku_id}; "
                f"valid grades: {sorted(VALID_GRADES)}"
            )

        pool = await self._ensure_pool()
        async with transaction(pool) as conn:
            old_row = await conn.fetchrow(
                "SELECT grade FROM aii.ku_onto WHERE ku_id = $1 FOR UPDATE", ku_id
            )
            if not old_row:
                raise ValueError(f"KU {ku_id} not found")

            from_grade = old_row["grade"]
            if grounded_by is not None:
                await conn.execute(
                    "UPDATE aii.ku_onto SET grade = $1, grounded_by = $2, updated_at = CURRENT_TIMESTAMP WHERE ku_id = $3",
                    to_grade,
                    json.dumps(grounded_by),
                    ku_id,
                )
            else:
                await conn.execute(
                    "UPDATE aii.ku_onto SET grade = $1, updated_at = CURRENT_TIMESTAMP WHERE ku_id = $2",
                    to_grade,
                    ku_id,
                )
            await conn.execute(
                """
                INSERT INTO aii.ku_state_history (ku_id, from_grade, to_grade, trigger, decision_trail)
                VALUES ($1, $2, $3, $4, $5)
                """,
                ku_id,
                from_grade,
                to_grade,
                reason or "manual_update",
                json.dumps(decision_trail or {}),
            )

    async def quarantine_ku(self, ku_id: str, reason: str) -> None:
        """Set is_quarantined=TRUE. Quarantine is orthogonal to `grade` in the
        ku_onto design (unlike the retired aii.ku table, there's no 'quarantined'
        grade value) — so this does not go through record_state_change."""
        pool = await self._ensure_pool()
        async with transaction(pool) as conn:
            row = await conn.fetchrow(
                "SELECT grade FROM aii.ku_onto WHERE ku_id = $1 FOR UPDATE", ku_id
            )
            if not row:
                raise ValueError(f"KU {ku_id} not found")
            await conn.execute(
                "UPDATE aii.ku_onto SET is_quarantined = TRUE, updated_at = CURRENT_TIMESTAMP WHERE ku_id = $1",
                ku_id,
            )
            # grade itself is unchanged by quarantine — from_grade==to_grade documents that.
            await conn.execute(
                """
                INSERT INTO aii.ku_state_history (ku_id, from_grade, to_grade, trigger, decision_trail)
                VALUES ($1, $2, $2, $3, $4)
                """,
                ku_id,
                row["grade"],
                f"quarantine: {reason}",
                json.dumps({"action": "quarantine", "reason": reason}),
            )

    async def unquarantine_ku(self, ku_id: str, reason: str) -> None:
        pool = await self._ensure_pool()
        async with transaction(pool) as conn:
            row = await conn.fetchrow(
                "SELECT grade FROM aii.ku_onto WHERE ku_id = $1 FOR UPDATE", ku_id
            )
            if not row:
                raise ValueError(f"KU {ku_id} not found")
            await conn.execute(
                "UPDATE aii.ku_onto SET is_quarantined = FALSE, updated_at = CURRENT_TIMESTAMP WHERE ku_id = $1",
                ku_id,
            )
            await conn.execute(
                """
                INSERT INTO aii.ku_state_history (ku_id, from_grade, to_grade, trigger, decision_trail)
                VALUES ($1, $2, $2, $3, $4)
                """,
                ku_id,
                row["grade"],
                f"unquarantine: {reason}",
                json.dumps({"action": "unquarantine", "reason": reason}),
            )

    async def list_quarantined_kus(self, limit: int = 100) -> list[dict[str, Any]]:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT ku_id, title, natural_text, knowledge_type, grade, substrate_id, updated_at "
                "FROM aii.ku_onto WHERE is_quarantined = TRUE ORDER BY updated_at DESC LIMIT $1",
                limit,
            )
        return [dict(r) for r in rows]

    async def list_pending_contradictions(self, limit: int = 100) -> list[dict[str, Any]]:
        """Contradiction pairs detected by scripts/detect_contradictions.py that
        haven't been reviewed yet, joined with both KUs' text for display."""
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    c.id, c.ku_a, c.ku_b, c.similarity, c.rationale, c.confidence,
                    c.judged_by, c.created_at,
                    a.natural_text AS ku_a_text, a.grade AS ku_a_grade,
                    b.natural_text AS ku_b_text, b.grade AS ku_b_grade
                FROM aii.ku_contradiction c
                LEFT JOIN aii.ku_onto a ON a.ku_id = c.ku_a
                LEFT JOIN aii.ku_onto b ON b.ku_id = c.ku_b
                WHERE c.status = 'pending'
                ORDER BY c.created_at DESC
                LIMIT $1
                """,
                limit,
            )
        return [dict(r) for r in rows]

    async def resolve_contradiction(
        self, contradiction_id: int, action: str, note: str | None = None
    ) -> dict[str, Any]:
        """Resolve a pending contradiction.

        action:
          keep_a   — ku_b is wrong; grade ku_b -> 'refuted', ku_a -> 'verified'
          keep_b   — mirror of keep_a
          keep_both — not a real contradiction (e.g. different contexts/scope);
                      both KUs are left as-is, just marks the pair reviewed
          dismiss  — false positive from the detector; marks reviewed, no grade change
        """
        valid_actions = {"keep_a", "keep_b", "keep_both", "dismiss"}
        if action not in valid_actions:
            raise ValueError(f"invalid action '{action}'; must be one of {sorted(valid_actions)}")

        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT ku_a, ku_b, status FROM aii.ku_contradiction WHERE id = $1",
                contradiction_id,
            )
            if not row:
                raise ValueError(f"contradiction {contradiction_id} not found")
            if row["status"] != "pending":
                raise ValueError(
                    f"contradiction {contradiction_id} already resolved ({row['status']})"
                )

            if action == "keep_a":
                await self.record_state_change(
                    row["ku_b"],
                    to_grade="refuted",
                    reason=f"contradiction #{contradiction_id}: keep_a",
                )
                await self.record_state_change(
                    row["ku_a"],
                    to_grade="verified",
                    reason=f"contradiction #{contradiction_id}: keep_a",
                    grounded_by={
                        "method": "contradiction_review",
                        "contradiction_id": contradiction_id,
                    },
                )
            elif action == "keep_b":
                await self.record_state_change(
                    row["ku_a"],
                    to_grade="refuted",
                    reason=f"contradiction #{contradiction_id}: keep_b",
                )
                await self.record_state_change(
                    row["ku_b"],
                    to_grade="verified",
                    reason=f"contradiction #{contradiction_id}: keep_b",
                    grounded_by={
                        "method": "contradiction_review",
                        "contradiction_id": contradiction_id,
                    },
                )
            # keep_both / dismiss: no grade change, just close out the review

            await conn.execute(
                "UPDATE aii.ku_contradiction SET status = $1, resolved_at = now(), resolution_note = $2 WHERE id = $3",
                action,
                note,
                contradiction_id,
            )
        return {"id": contradiction_id, "status": action}

    # --- New Methods for Failure Lessons and Capability Gaps ---

    def record_failure_lesson(
        self, trigger_type: str, subject_ref: str, evidence: dict, lesson: str
    ) -> None:
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

    async def record_failure_lesson_async(
        self, trigger_type: str, subject_ref: str | None, evidence: dict, lesson: str
    ) -> None:
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
                trigger_type,
                subject_ref,
            )
            return row is not None

    def query_failure_lessons(
        self, trigger_type: str = None, subject_ref: str = None
    ) -> list[dict]:
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
                    trigger_type,
                    subject_ref,
                )
                return row is not None

        return asyncio.run(_has())

    def save_capability_gap(self, report: dict) -> None:
        async def _save():
            pool = await self._ensure_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO aii.capability_gap (report) VALUES ($1)", json.dumps(report)
                )

        asyncio.run(_save())

    def get_latest_capability_gap(self) -> dict | None:
        async def _get():
            pool = await self._ensure_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT report FROM aii.capability_gap ORDER BY snapshot_at DESC LIMIT 1"
                )
                return json.loads(row["report"]) if row else None

        return asyncio.run(_get())

    def get_grade_distribution(self) -> dict:
        async def _get():
            pool = await self._ensure_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT knowledge_type, grade, COUNT(*) as count FROM aii.ku_onto GROUP BY knowledge_type, grade"
                )
                res = {}
                for r in rows:
                    kt = r["knowledge_type"]
                    grade = r["grade"]
                    count = r["count"]
                    if kt not in res:
                        res[kt] = {}
                    res[kt][grade] = count
                return res

        return asyncio.run(_get())

    async def get_grade_distribution_async(self) -> dict:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT knowledge_type, grade, COUNT(*) as count FROM aii.ku_onto GROUP BY knowledge_type, grade"
            )
            res = {}
            for r in rows:
                kt = r["knowledge_type"]
                grade = r["grade"]
                count = r["count"]
                if kt not in res:
                    res[kt] = {}
                res[kt][grade] = count
            return res

    def get_stale_unverified(self, days: int) -> list[dict]:
        async def _get():
            pool = await self._ensure_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT * FROM aii.ku_onto WHERE grade = 'unverified' AND provenance IS NOT NULL AND updated_at < NOW() - $1::interval",
                    f"{days} days",
                )
                return [dict(r) for r in rows]

        return asyncio.run(_get())

    async def get_stale_unverified_async(self, days: int) -> list[dict]:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM aii.ku_onto WHERE grade = 'unverified' AND provenance IS NOT NULL AND updated_at < NOW() - make_interval(days => $1)",
                days,
            )
            return [dict(r) for r in rows]

    def get_isolated_kus(self) -> list[str]:
        async def _get():
            pool = await self._ensure_pool()
            async with pool.acquire() as conn:
                sql = """
                    SELECT ku_id FROM aii.ku_onto
                    WHERE ku_id NOT IN (SELECT src_id FROM aii.edge_onto)
                      AND ku_id NOT IN (SELECT dst_id FROM aii.edge_onto)
                """
                rows = await conn.fetch(sql)
                return [str(r["ku_id"]) for r in rows]

        return asyncio.run(_get())

    async def get_isolated_kus_async(self) -> list[str]:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            sql = """
                SELECT ku_id FROM aii.ku_onto
                WHERE ku_id NOT IN (SELECT src_id FROM aii.edge_onto)
                  AND ku_id NOT IN (SELECT dst_id FROM aii.edge_onto)
            """
            rows = await conn.fetch(sql)
            return [str(r["ku_id"]) for r in rows]

    async def query_failure_lessons_async(
        self, trigger_type: str = None, subject_ref: str = None
    ) -> list[dict]:
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
            await conn.execute(
                "INSERT INTO aii.capability_gap (report) VALUES ($1)", json.dumps(report)
            )

    async def get_latest_capability_gap_async(self) -> dict | None:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT report FROM aii.capability_gap ORDER BY snapshot_at DESC LIMIT 1"
            )
            return json.loads(row["report"]) if row else None

    # --- Deep Understanding methods ---

    async def list_kus(self) -> list[dict[str, Any]]:
        """Return all non-quarantined KUs without the embedding column.

        Callers (synthesis_engine_deep) only need ku_id / natural_text / grade.
        Excluding the 4 KB embedding vector per row reduces the result set from
        ~54 MB to ~8 MB for 13 K rows and avoids a multi-second asyncio event-loop
        stall while Python decodes the float arrays.
        """
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT ku_id, natural_text, knowledge_type, grade, substrate_id, "
                "is_quarantined, merge_count, created_at "
                "FROM aii.ku_onto WHERE is_quarantined = FALSE ORDER BY created_at"
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
        if grade not in VALID_EPISTEMIC_GRADES:
            await self.record_failure_lesson_async(
                trigger_type="invalid_grade",
                subject_ref=grade,
                evidence={
                    "src_id": src_id,
                    "dst_id": dst_id,
                    "grade": grade,
                    "relation_type": relation_type,
                    "extraction_method": extraction_method,
                    "context": "add_relation_edge",
                },
                lesson=(
                    f"grade='{grade}' is not a valid EpistemicGrade; "
                    f"fix the upstream code that produced this value"
                ),
            )
            raise ValueError(
                f"invalid grade '{grade}' for edge {src_id[:8]}→{dst_id[:8]}; "
                f"valid grades: {sorted(VALID_EPISTEMIC_GRADES)}"
            )
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO aii.edge_onto (src_id, relation, dst_id, relation_type, grade, evidence, extraction_method)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (src_id, relation, dst_id) DO UPDATE SET
                    relation_type = EXCLUDED.relation_type,
                    grade = EXCLUDED.grade,
                    evidence = EXCLUDED.evidence,
                    extraction_method = EXCLUDED.extraction_method
                """,
                src_id,
                relation_type,
                dst_id,
                relation_type,
                grade,
                json.dumps(evidence or {}),
                extraction_method,
            )

    async def get_relation_edges(self, ku_id: str | None = None) -> list[dict[str, Any]]:
        """Return relation edges with grade and extraction metadata."""
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            if ku_id:
                rows = await conn.fetch(
                    "SELECT * FROM aii.edge_onto WHERE src_id = $1 OR dst_id = $1",
                    ku_id,
                )
            else:
                rows = await conn.fetch("SELECT * FROM aii.edge_onto")
            return [dict(r) for r in rows]

    async def get_ku_embeddings(self, ku_ids: list[str]) -> dict[str, list[float]]:
        """Return {ku_id: embedding_vector} for given ku_ids that have embeddings."""
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT ku_id, embedding FROM aii.ku_onto WHERE ku_id = ANY($1) AND embedding IS NOT NULL",
                [kid for kid in ku_ids],
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

    async def get_substrate_id_by_title(self, title: str) -> str | None:
        """Return existing substrate_id if this exact title was already ingested with ku_count>0."""
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT substrate_id FROM aii.ingested_substrate WHERE title = $1 AND ku_count > 0 LIMIT 1",
                title,
            )
        return str(row["substrate_id"]) if row else None

    async def mark_substrate_ingested(
        self,
        substrate_id: str,
        title: str,
        medium: str,
        ku_count: int,
        subject: str | None = None,
    ) -> None:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO aii.ingested_substrate (substrate_id, title, medium, ku_count, subject)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (substrate_id) DO UPDATE SET
                    ku_count = EXCLUDED.ku_count,
                    subject = COALESCE(EXCLUDED.subject, aii.ingested_substrate.subject)
                """,
                substrate_id,
                title,
                medium,
                ku_count,
                subject,
            )

    def list_ingested_substrates(self) -> list[dict]:
        async def _list():
            pool = await self._ensure_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT substrate_id, title, medium, ku_count, subject FROM aii.ingested_substrate ORDER BY ingested_at"
                )
            return [dict(r) for r in rows]

        return asyncio.run(_list())

    def update_substrate_subject(self, substrate_id: str, subject: str) -> None:
        async def _update():
            pool = await self._ensure_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE aii.ingested_substrate SET subject = $1 WHERE substrate_id = $2",
                    subject,
                    substrate_id,
                )

        asyncio.run(_update())

    async def find_nearest_ku(
        self, embedding: list[float], exclude_synthesis: bool = True
    ) -> dict | None:
        """Return the single nearest KU by cosine distance (pgvector <=>), or None.
        Result includes 'distance' field (0=identical, 2=opposite)."""
        pool = await self._ensure_pool()
        clauses = ["embedding IS NOT NULL"]  # onto: ku_onto 全是真 KU, 无 is_synthesis
        where = " AND ".join(clauses)
        sql = f"""
            SELECT ku_id, natural_text, grade, knowledge_type,
                   (embedding <=> $1) AS distance
            FROM aii.ku_onto
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

        source_entry = json.dumps(
            [
                {
                    "substrate_id": substrate_id,
                    "natural_text": natural_text[:200],
                    "ingested_at": datetime.now(timezone.utc).isoformat(),
                }
            ]
        )
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE aii.ku_onto
                SET sources = COALESCE(sources, '[]'::jsonb) || $2::jsonb,
                    merge_count = COALESCE(merge_count, 1) + 1
                WHERE ku_id = $1
                """,
                existing_ku_id,
                source_entry,
            )

    async def get_source_ids_for_ku(self, ku_id: str) -> list[str]:
        """Return substrate_ids that support this KU.

        Reads sources JSONB array first; falls back to substrate_id column
        (covers 97% of historical KUs with empty sources).
        Used by source_trace (P-G3) and cascade_delete (K-G5).
        """
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT substrate_id, sources FROM aii.ku_onto WHERE ku_id = $1",
                ku_id,
            )
        if not row:
            return []
        raw = row["sources"]
        sources: list[dict] = (
            raw
            if isinstance(raw, list)
            else (json.loads(raw) if isinstance(raw, str) and raw else [])
        )
        result = [s["substrate_id"] for s in sources if s.get("substrate_id")]
        if not result and row["substrate_id"]:
            result = [str(row["substrate_id"])]
        return list(dict.fromkeys(result))  # dedupe, preserve order

    async def get_ku_ids_for_source(self, source_id: str) -> list[str]:
        """Return ku_ids whose sources include this source_id.

        Matches substrate_id column OR sources JSONB array element.
        Used by cascade_delete (K-G5).
        """
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT ku_id FROM aii.ku_onto
                WHERE substrate_id = $1
                   OR sources @> $2::jsonb
                """,
                source_id,
                json.dumps([{"substrate_id": source_id}]),
            )
        return [str(r["ku_id"]) for r in rows]

    async def get_kus_by_ids(self, ku_ids: list[str]) -> list[dict[str, Any]]:
        """Batch-fetch KU rows by a list of ku_ids (non-quarantined only)."""
        if not ku_ids:
            return []
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT ku_id, natural_text, knowledge_type, grade, substrate_id, "
                "sources "
                "FROM aii.ku_onto WHERE ku_id = ANY($1) AND is_quarantined = FALSE",
                [kid for kid in ku_ids],
            )
        return [dict(r) for r in rows]

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

    # ── P3 cascade-delete interfaces (K-G5) ────────────────────────────────

    async def get_dangling_deps_count(self, ku_id: str) -> int:
        """Count edges that have this KU as src or dst (used by cascade_delete for reporting)."""
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT count(*) AS cnt FROM aii.edge_onto WHERE src_id = $1 OR dst_id = $1",
                ku_id,
            )
        return int(row["cnt"])

    async def clear_dangling_deps(self, ku_id: str) -> None:
        """Delete all edges where this KU is src or dst."""
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM aii.edge_onto WHERE src_id = $1 OR dst_id = $1",
                ku_id,
            )

    async def delete_ku(self, ku_id: str) -> None:
        """Delete a KU with full cascade:
        edges (no FK) + ku_state_history (no FK) + ku (ku_concept auto-cascades) + concept.ku_count sync.
        """
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                # 1. Capture concept_ids before deletion (ku_concept will auto-cascade)
                concept_rows = await conn.fetch(
                    "SELECT concept_id FROM aii.ku_concept_onto WHERE ku_id = $1",
                    ku_id,
                )
                concept_ids = [r["concept_id"] for r in concept_rows]

                # 2. Delete edges (no ON DELETE CASCADE)
                await conn.execute(
                    "DELETE FROM aii.edge_onto WHERE src_id = $1 OR dst_id = $1",
                    ku_id,
                )
                # 3. Delete state history (no ON DELETE CASCADE)
                await conn.execute(
                    "DELETE FROM aii.ku_state_history WHERE ku_id = $1",
                    ku_id,
                )
                # 4. Delete KU (ku_concept_onto rows auto-cascade via FK)
                await conn.execute(
                    "DELETE FROM aii.ku_onto WHERE ku_id = $1",
                    ku_id,
                )
                # (concept_onto 无 ku_count 列 — ku_count 由 display 实时聚合, 无需 sync)
                _ = concept_ids

    # ── end P3 ─────────────────────────────────────────────────────────────

    async def search_synthesis_kus(
        self, query_vector: list[float], limit: int = 5
    ) -> list[dict[str, Any]]:
        """onto: 综合(KC)无向量列, 不做向量检索 → 返回空; chat 回退到常规 KU 检索.
        ★已被 search_kc_by_vector 取代(KC 0004 迁移加了向量列). 保留兼容旧调用."""
        return []

    async def search_kc_by_vector(
        self, query_vector: list[float], limit: int = 5
    ) -> list[dict[str, Any]]:
        """★社区/知识簇(KC)摘要向量检索 — global '综述/体系' 问题的正解(GraphRAG global search).
        需先 0004 迁移 + embed_kc_summaries.py 补向量. 无向量的 KC 不参与检索."""
        pool = await self._ensure_pool()
        sql = """
            SELECT kc_id, substrate_id, level, community_label, summary, summary_en,
                   member_ku_ids, core_concept_id, grade, synthesis_marker,
                   embedding <=> $1 AS distance
            FROM aii.kc_onto
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> $1
            LIMIT $2
        """
        async with pool.acquire() as conn:
            records = await conn.fetch(sql, query_vector, limit)
        return [dict(r) for r in records]
