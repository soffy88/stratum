"""书籍自动分类配置 + 触发 + 历史。前端"文件分类"设置页对应的后端。

单配置(owner='default')起步, owner 留多租户扩展口。分类逻辑在 scripts/auto_classify_books.py,
定时器和本路由的 /run 都复用它。
"""

import json
import subprocess
from pathlib import Path

from fastapi import APIRouter, Body

from aii.api._dependencies import backend
from aii.api._envelope import error_response, success_response

router = APIRouter()

_OWNER = "default"
_ROOT = Path(__file__).resolve().parents[4]  # …/aii (仓库根, 含 scripts/)
_SCRIPT = _ROOT / "scripts" / "auto_classify_books.py"
_PY = _ROOT / ".venv" / "bin" / "python"


def _obj(v):
    return json.loads(v) if isinstance(v, str) else v


@router.get("/classify/config")
async def get_config():
    try:
        pool = await backend._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT source, categories, skip_patterns, enabled, updated_at "
                "FROM aii.book_classify_config WHERE owner=$1",
                _OWNER,
            )
        if not row:
            return success_response(
                {
                    "source": "gdrive-rw:books/all",
                    "categories": [],
                    "skip_patterns": [],
                    "enabled": True,
                }
            )
        return success_response(
            {
                "source": row["source"],
                "categories": _obj(row["categories"]),
                "skip_patterns": _obj(row["skip_patterns"]),
                "enabled": row["enabled"],
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            }
        )
    except Exception as e:
        return error_response("CLASSIFY_CONFIG_ERROR", str(e))


@router.put("/classify/config")
async def put_config(
    categories: list = Body(..., description="[{folder, keywords:[], description}]"),
    skip_patterns: list = Body(default=[]),
    enabled: bool = Body(default=True),
    source: str = Body(default="gdrive-rw:books/all"),
):
    try:
        pool = await backend._ensure_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO aii.book_classify_config(owner,source,categories,skip_patterns,enabled,updated_at)
                VALUES($1,$2,$3,$4,$5,now())
                ON CONFLICT (owner) DO UPDATE SET source=$2, categories=$3, skip_patterns=$4,
                    enabled=$5, updated_at=now()""",
                _OWNER,
                source,
                json.dumps(categories, ensure_ascii=False),
                json.dumps(skip_patterns, ensure_ascii=False),
                enabled,
            )
        return success_response({"saved": True, "categories": len(categories)})
    except Exception as e:
        return error_response("CLASSIFY_SAVE_ERROR", str(e))


@router.post("/classify/run")
async def run_now():
    """立即分类一次: 后台起 auto_classify_books.py(不阻塞), 结果去 /classify/log 看。"""
    try:
        subprocess.Popen(
            [str(_PY), str(_SCRIPT), "--owner", _OWNER, "--force"],
            cwd=str(_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return success_response({"started": True})
    except Exception as e:
        return error_response("CLASSIFY_RUN_ERROR", str(e))


@router.get("/classify/log")
async def get_log(limit: int = 50):
    try:
        pool = await backend._ensure_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT filename, category, method, moved_ok, ts FROM aii.book_classify_log "
                "WHERE owner=$1 ORDER BY ts DESC LIMIT $2",
                _OWNER,
                min(limit, 200),
            )
        return success_response(
            [
                {
                    "filename": r["filename"],
                    "category": r["category"],
                    "method": r["method"],
                    "moved_ok": r["moved_ok"],
                    "ts": r["ts"].isoformat() if r["ts"] else None,
                }
                for r in rows
            ]
        )
    except Exception as e:
        return error_response("CLASSIFY_LOG_ERROR", str(e))
