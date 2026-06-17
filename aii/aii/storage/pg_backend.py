import asyncio
import json
import logging
from typing import Any, AsyncIterator
from uuid import UUID

import asyncpg
from obase.persistence import PgPool, transaction, upsert_batch, vector_search, ensure_table
from aii.storage.backend import StorageBackend, EpistemicStore

logger = logging.getLogger(__name__)

class PgBackend(StorageBackend, EpistemicStore):
    """PostgreSQL implementation of StorageBackend and EpistemicStore using obase.persistence."""

    def __init__(self, pool_name: str = "aii_pool", dsn: str | None = None):
        self.pool_name = pool_name
        self.dsn = dsn
        self._pool = None

    async def _ensure_pool(self) -> PgPool:
        if self._pool is None:
            if not self.dsn:
                raise ValueError("DSN must be provided to initialize PgPool")
            self._pool = await PgPool.create(name=self.pool_name, dsn=self.dsn, enable_vector=True)
        return self._pool

    # --- StorageBackend Implementation ---

    def put_node(self, node_id: str, payload: dict[str, Any]) -> None:
        """Synchronous wrapper for put_ku (standard omodul behavior)."""
        asyncio.run(self.put_ku(payload))

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        return asyncio.run(self.get_ku(node_id))

    def list_nodes(self) -> list[str]:
        async def _list():
            pool = await self._ensure_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch("SELECT ku_id FROM aii.ku")
                return [str(r["ku_id"]) for r in rows]
        return asyncio.run(_list())

    def put_edge(self, src_id: str, relation: str, dst_id: str) -> None:
        async def _put():
            pool = await self._ensure_pool()
            row = {"src_id": UUID(src_id), "relation": relation, "dst_id": UUID(dst_id)}
            await upsert_batch(pool=pool, table="aii.edge", rows=[row], conflict_columns=["src_id", "relation", "dst_id"])
        asyncio.run(_put())

    def list_edges(self, node_id: str | None = None) -> list[dict[str, Any]]:
        async def _list():
            pool = await self._ensure_pool()
            async with pool.acquire() as conn:
                if node_id:
                    rows = await conn.fetch("SELECT * FROM aii.edge WHERE src_id = $1 OR dst_id = $1", UUID(node_id))
                else:
                    rows = await conn.fetch("SELECT * FROM aii.edge")
                return [dict(r) for r in rows]
        return asyncio.run(_list())

    # --- EpistemicStore Implementation ---

    async def put_ku(self, ku: dict[str, Any]) -> None:
        pool = await self._ensure_pool()
        ku_id = ku.get("ku_id")
        if not ku_id:
            raise ValueError("ku_id is required")
        
        # Ensure UUID format
        if isinstance(ku_id, str):
            ku_id = UUID(ku_id)

        fingerprint = ku.get("fingerprint")
        
        async with transaction(pool) as conn:
            # 1. Fingerprint de-duplication
            if fingerprint:
                existing = await conn.fetchrow(
                    "SELECT ku_id FROM aii.ku WHERE fingerprint = $1 AND is_quarantined = FALSE", 
                    fingerprint
                )
                if existing and existing["ku_id"] != ku_id:
                    logger.info(f"KU with fingerprint {fingerprint} already exists as {existing['ku_id']}. Skipping.")
                    return

            # 2. Get old grade for audit
            old_row = await conn.fetchrow("SELECT grade FROM aii.ku WHERE ku_id = $1 FOR UPDATE", ku_id)
            old_grade = old_row["grade"] if old_row else None
            new_grade = ku.get("grade", "unverified")

            # 3. Upsert KU
            # Prepare row for upsert (excluding fields handled by DB defaults or special logic)
            row = {k: v for k, v in ku.items() if k in {
                "ku_id", "project_id", "natural_text", "knowledge_type", 
                "symbolic_form", "embedding", "grade", "source", 
                "verified", "is_quarantined", "provenance", "fingerprint"
            }}
            row["ku_id"] = ku_id
            
            # Serialize JSONB fields
            for json_field in ["symbolic_form", "provenance"]:
                if json_field in row and isinstance(row[json_field], dict):
                    row[json_field] = json.dumps(row[json_field])

            if "embedding" in row and isinstance(row["embedding"], list):
                # Ensure embedding is handled correctly (pgvector expects list of floats or np array)
                pass 

            await upsert_batch(pool=pool, table="aii.ku", rows=[row], conflict_columns=["ku_id"])

            # 4. Record state change if grade changed
            if old_grade != new_grade:
                await conn.execute(
                    """
                    INSERT INTO aii.ku_state_history (ku_id, from_grade, to_grade, trigger, decision_trail)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    ku_id, old_grade, new_grade, "put_ku", json.dumps(ku.get("decision_trail", {}))
                )

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
