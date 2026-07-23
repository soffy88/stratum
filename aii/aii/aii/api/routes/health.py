import json
from pathlib import Path

from fastapi import APIRouter
from aii.api._dependencies import backend
from aii.api._envelope import success_response

router = APIRouter()

# 看门狗(scripts/watchdog.py, systemd timer每5min)写的结构化健康报告。
_WATCHDOG_REPORT = Path("/data/soffy/projects/stratum/aii/watchdog/health_report.json")


@router.get("/ping")
async def ping():
    return {"status": "ok"}


@router.get("/health/watchdog")
async def health_watchdog():
    """返回看门狗最近一次体检报告(前端健康横幅读这个; 零耦合, 只读文件)。"""
    try:
        report = json.loads(_WATCHDOG_REPORT.read_text(encoding="utf-8"))
        import time

        report["report_age_sec"] = int(time.time() - _WATCHDOG_REPORT.stat().st_mtime)
        return success_response(report)
    except FileNotFoundError:
        return success_response(
            {
                "overall": "unknown",
                "checks": [],
                "needs_human": [],
                "detail": "看门狗尚未产出报告(timer未跑或首次启动中)",
            }
        )
    except Exception as e:
        return success_response(
            {
                "overall": "unknown",
                "checks": [],
                "needs_human": [],
                "detail": f"读取健康报告失败: {str(e)[:100]}",
            }
        )


@router.get("/health/graph")
async def health_graph():
    pool = await backend._ensure_pool()
    async with pool.acquire() as conn:
        # Check PgBackend survival by a simple query
        await conn.execute("SELECT 1")

        # KU statistics
        total = await conn.fetchval("SELECT count(*) FROM aii.ku_onto")
        by_grade_rows = await conn.fetch(
            "SELECT grade, count(*) as count FROM aii.ku_onto GROUP BY grade"
        )
        by_grade = {row["grade"]: row["count"] for row in by_grade_rows}

    return success_response(
        {"database": "connected", "ku_stats": {"total": total, "by_grade": by_grade}}
    )
