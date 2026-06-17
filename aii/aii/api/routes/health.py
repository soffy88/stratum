from fastapi import APIRouter
from aii.api._dependencies import backend
from aii.api._envelope import success_response

router = APIRouter()

@router.get("/ping")
async def ping():
    return {"status": "ok"}

@router.get("/health/graph")
async def health_graph():
    pool = await backend._ensure_pool()
    async with pool.acquire() as conn:
        # Check PgBackend survival by a simple query
        await conn.execute("SELECT 1")
        
        # KU statistics
        total = await conn.fetchval("SELECT count(*) FROM aii.ku")
        by_grade_rows = await conn.fetch("SELECT grade, count(*) as count FROM aii.ku GROUP BY grade")
        by_grade = {row["grade"]: row["count"] for row in by_grade_rows}
        
    return success_response({
        "database": "connected",
        "ku_stats": {
            "total": total,
            "by_grade": by_grade
        }
    })
