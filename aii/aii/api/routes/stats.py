"""Stats endpoints — read-only dashboard data."""
import os
from pathlib import Path

from fastapi import APIRouter

from aii.api._dependencies import backend
from aii.api._envelope import success_response, error_response

router = APIRouter()

_SHARED_DIR = Path(os.getenv("FLYWHEEL_SHARED_DIR", "/home/soffy/shared/stratum-to-aii"))


@router.get("/stats/overview")
async def stats_overview():
    try:
        pool = await backend._ensure_pool()
        async with pool.acquire() as conn:
            ku_row = await conn.fetchrow("""
                SELECT
                  count(*) FILTER(WHERE is_synthesis IS NOT TRUE)                          AS ku_count,
                  count(*) FILTER(WHERE knowledge_type = 'synthesis')                      AS kc_count,
                  count(*) FILTER(WHERE knowledge_type = 'book_understanding')             AS bu_count,
                  count(*) FILTER(WHERE is_synthesis IS NOT TRUE AND merge_count > 1)      AS merged_ku_count,
                  COALESCE(sum(merge_count - 1) FILTER(
                      WHERE is_synthesis IS NOT TRUE AND merge_count > 1), 0)              AS dedup_saved
                FROM aii.ku
            """)
            grade_rows = await conn.fetch("""
                SELECT grade, count(*) AS cnt
                FROM aii.ku WHERE is_synthesis IS NOT TRUE
                GROUP BY grade ORDER BY cnt DESC
            """)
            edge_count = await conn.fetchval("SELECT count(*) FROM aii.edge")
            rel_rows = await conn.fetch("""
                SELECT relation_type, count(*) AS cnt
                FROM aii.edge GROUP BY relation_type ORDER BY cnt DESC
            """)
            contradicts = await conn.fetchval(
                "SELECT count(*) FROM aii.edge WHERE relation_type = 'contradicts'"
            )

        return success_response({
            "ku_count": ku_row["ku_count"],
            "kc_count": ku_row["kc_count"],
            "bu_count": ku_row["bu_count"],
            "edge_count": edge_count,
            "grade_dist": {r["grade"]: r["cnt"] for r in grade_rows},
            "merge_count": ku_row["merged_ku_count"],
            "dedup_saved": int(ku_row["dedup_saved"]),
            "relation_type_dist": {r["relation_type"]: r["cnt"] for r in rel_rows},
            "contradicts_count": contradicts,
        })
    except Exception as e:
        return error_response("STATS_ERROR", str(e))


@router.get("/stats/ingestion")
async def stats_ingestion():
    try:
        total_files = len(list(_SHARED_DIR.glob("*.md"))) if _SHARED_DIR.is_dir() else 0

        pool = await backend._ensure_pool()
        async with pool.acquire() as conn:
            ingested = await conn.fetchval("SELECT count(*) FROM aii.ingested_substrate")
            medium_rows = await conn.fetch(
                "SELECT medium, count(*) AS cnt FROM aii.ingested_substrate GROUP BY medium ORDER BY cnt DESC"
            )
            deep_done = await conn.fetchval(
                "SELECT count(*) FROM aii.ingested_substrate WHERE deep_understood_at IS NOT NULL"
            )

        return success_response({
            "total_files": total_files,
            "ingested": ingested,
            "by_medium": {r["medium"]: r["cnt"] for r in medium_rows},
            "deep_understood": deep_done,
        })
    except Exception as e:
        return error_response("STATS_ERROR", str(e))
