"""background_flywheel — 常驻后台飞轮 (asyncio.create_task, 无新依赖).

配置 (环境变量 / 默认值):
  FLYWHEEL_ENABLED          = true      开关
  FLYWHEEL_MAX_FILES_ROUND  = 3         ★限流: 每轮最多处理 N 个文件
  FLYWHEEL_INTERVAL         = 300       轮间隔(秒)
  FLYWHEEL_EVOLVE_EVERY     = 4         每 N 轮跑一次 evolve+needs

守命门:
  - 单轮任何异常 → log + continue, 绝不 crash
  - CancelledError 立即退出 (lifespan shutdown)
  - evolve() 每 EVOLVE_EVERY 轮跑一次, 失败非致命
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_SHARED_DIR = Path(os.getenv("FLYWHEEL_SHARED_DIR", "/home/soffy/shared/stratum-to-aii"))
_OUTPUT_DIR = Path(os.getenv("FLYWHEEL_OUTPUT_DIR", "/home/soffy/shared/aii-to-stratum"))

FLYWHEEL_ENABLED: bool = os.getenv("FLYWHEEL_ENABLED", "true").lower() not in {"false", "0", "no"}
FLYWHEEL_MAX_FILES_ROUND: int = int(os.getenv("FLYWHEEL_MAX_FILES_ROUND", "3"))
FLYWHEEL_INTERVAL: int = int(os.getenv("FLYWHEEL_INTERVAL", "300"))
FLYWHEEL_EVOLVE_EVERY: int = int(os.getenv("FLYWHEEL_EVOLVE_EVERY", "4"))


async def _collect_new_files(backend, limit: int) -> list[Path]:
    """返回至多 limit 个尚未摄入的 .md 文件 (配对 .json 必须存在)."""
    found: list[Path] = []
    for md in sorted(_SHARED_DIR.glob("*.md")):
        if len(found) >= limit:
            break
        jp = md.with_suffix(".json")
        if not jp.exists():
            continue
        try:
            meta = json.loads(jp.read_text(encoding="utf-8"))
            sid = meta.get("id", "")
            if sid and not await backend.is_substrate_ingested(sid):
                found.append(md)
        except Exception:
            logger.warning("flywheel: bad sidecar %s, skip", jp.name)
    return found


def _write_needs(gaps: dict) -> None:
    try:
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        high_miss = gaps.get("high_miss_topics", [])
        needs = [
            {
                "topic": t["topic"] if isinstance(t, dict) else str(t),
                "reason": "high_miss",
                "miss_count": t.get("miss_count", 0) if isinstance(t, dict) else 0,
            }
            for t in high_miss
        ]
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "needs": needs,
        }
        (_OUTPUT_DIR / "needs.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("flywheel: wrote needs.json (%d topics)", len(needs))
    except Exception:
        logger.exception("flywheel: needs.json write failed (non-fatal)")


async def flywheel_loop(backend) -> None:
    """后台飞轮主循环. 由 app.py lifespan asyncio.create_task() 启动."""
    from aii.service.auto_ingest import ingest_one
    from aii.service.evolution_engine import EvolutionEngine

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    round_num = 0

    logger.info(
        "flywheel: started (enabled=%s max_files=%d interval=%ds evolve_every=%d)",
        FLYWHEEL_ENABLED, FLYWHEEL_MAX_FILES_ROUND, FLYWHEEL_INTERVAL, FLYWHEEL_EVOLVE_EVERY,
    )

    while True:
        try:
            if not FLYWHEEL_ENABLED:
                await asyncio.sleep(60)
                continue

            round_num += 1
            logger.info("flywheel: round %d begin", round_num)

            # ── A. 扫新文件, ★限流 MAX_FILES_ROUND ─────────────────────────
            new_files = await _collect_new_files(backend, FLYWHEEL_MAX_FILES_ROUND)
            if new_files:
                logger.info("flywheel: ingesting %d file(s) this round", len(new_files))
                for md in new_files:
                    try:
                        n = await ingest_one(md, backend)
                        logger.info("flywheel: %s → %s KUs", md.name, n if n >= 0 else "skip")
                    except Exception:
                        logger.exception("flywheel: ingest_one failed for %s (non-fatal)", md.name)
            else:
                logger.info("flywheel: no new files this round")

            # ── B. 定期 evolve + 写需求文件 ──────────────────────────────────
            if round_num % FLYWHEEL_EVOLVE_EVERY == 0:
                try:
                    logger.info("flywheel: running evolution (round %d)", round_num)
                    ev = EvolutionEngine(backend)
                    report = await ev.evolve()
                    gaps = report.get("gaps") or {}
                    _write_needs(gaps)
                    logger.info(
                        "flywheel: evolve done upgraded=%d gaps=%s",
                        len(report.get("upgraded", [])),
                        {k: v for k, v in gaps.items() if k != "grade_imbalance"},
                    )
                except Exception:
                    logger.exception("flywheel: evolve failed (non-fatal)")

        except asyncio.CancelledError:
            logger.info("flywheel: cancelled, shutting down")
            break
        except Exception:
            logger.exception("flywheel: round %d unhandled error (non-fatal, continuing)", round_num)

        await asyncio.sleep(FLYWHEEL_INTERVAL)
