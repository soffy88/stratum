"""background_flywheel_textbook — 管道2独立飞轮 (asyncio.create_task).

环境变量:
  TEXTBOOK_FLYWHEEL_ENABLED   = true      开关 (默认 true)
  TEXTBOOK_SHARED_DIR         = /home/soffy/shared/textbook-to-aii
  TEXTBOOK_MAX_FILES_ROUND    = 3         每轮最多处理 N 本教材
  TEXTBOOK_INTERVAL           = 120       轮间隔(秒)

与管道1飞轮完全独立:
  - 独立 ENABLED 开关, 一个停不影响另一个
  - 独立共享目录, 不与管道1竞争文件
  - CancelledError 立即退出 (lifespan shutdown)
  - 任何 per-file 异常 → 日志 + continue, 不 crash
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_SHARED_DIR = Path(os.getenv("TEXTBOOK_SHARED_DIR", "/home/soffy/shared/textbook-to-aii"))

TEXTBOOK_FLYWHEEL_ENABLED: bool = (
    os.getenv("TEXTBOOK_FLYWHEEL_ENABLED", "true").lower() not in {"false", "0", "no"}
)
TEXTBOOK_MAX_FILES_ROUND: int = int(os.getenv("TEXTBOOK_MAX_FILES_ROUND", "3"))
TEXTBOOK_INTERVAL: int = int(os.getenv("TEXTBOOK_INTERVAL", "120"))


async def _collect_new_textbooks(backend, limit: int) -> list[Path]:
    """返回至多 limit 个尚未摄入的教材 .md 文件 (需配对 .json)."""

    def _scan() -> list[tuple]:
        result = []
        if not _SHARED_DIR.exists():
            return result
        for md in sorted(_SHARED_DIR.glob("*.md")):
            jp = md.with_suffix(".json")
            if not jp.exists():
                continue
            try:
                meta = json.loads(jp.read_text(encoding="utf-8"))
                sid = meta.get("id", "")
                if sid:
                    result.append((md, sid))
            except Exception:
                logger.warning("textbook_flywheel: bad sidecar %s, skip", jp.name)
        return result

    candidates = await asyncio.to_thread(_scan)
    found: list[Path] = []
    for md, sid in candidates:
        if len(found) >= limit:
            break
        try:
            if not await backend.is_substrate_ingested(sid):
                found.append(md)
        except Exception:
            logger.warning("textbook_flywheel: error checking %s, skip", md.name)
    return found


async def textbook_flywheel_loop(backend) -> None:
    """管道2后台飞轮主循环. 由 app.py lifespan asyncio.create_task() 启动."""
    from aii.service.textbook_ingest import ingest_one_textbook

    round_num = 0
    logger.info(
        "textbook_flywheel: started (enabled=%s, dir=%s, max=%d, interval=%ds)",
        TEXTBOOK_FLYWHEEL_ENABLED, _SHARED_DIR, TEXTBOOK_MAX_FILES_ROUND, TEXTBOOK_INTERVAL,
    )

    while True:
        try:
            if not TEXTBOOK_FLYWHEEL_ENABLED:
                await asyncio.sleep(60)
                continue

            round_num += 1
            logger.info("textbook_flywheel: round %d begin", round_num)

            new_files = await _collect_new_textbooks(backend, TEXTBOOK_MAX_FILES_ROUND)
            if not new_files:
                logger.debug("textbook_flywheel: round %d — no new textbooks", round_num)
            else:
                for md in new_files:
                    try:
                        result = await ingest_one_textbook(md, backend=backend)
                        logger.info(
                            "textbook_flywheel: ingested %s → %s",
                            md.name, result,
                        )
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        logger.exception(
                            "textbook_flywheel: ingest_one_textbook failed for %s (non-fatal)",
                            md.name,
                        )

            logger.info("textbook_flywheel: round %d done, sleeping %ds", round_num, TEXTBOOK_INTERVAL)
            await asyncio.sleep(TEXTBOOK_INTERVAL)

        except asyncio.CancelledError:
            logger.info("textbook_flywheel: cancelled, shutting down")
            break
        except Exception:
            logger.exception("textbook_flywheel: unexpected error in round %d (continuing)", round_num)
            await asyncio.sleep(30)
