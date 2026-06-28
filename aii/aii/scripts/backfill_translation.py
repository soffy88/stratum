#!/usr/bin/env python3
"""批量回填英文KU的中文译文 (natural_text_zh).

断点续传: 只取 natural_text_zh IS NULL 的行，中断后重跑自动续传。
低优先级: 以 nice -n 19 后台运行，不抢飞轮资源。
失败标记: 翻译失败填占位符，避免无限重试同一条。

使用:
    nohup nice -n 19 .venv/bin/python scripts/backfill_translation.py \
        > /tmp/backfill_trans.log 2>&1 &
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from pathlib import Path

# ── 环境 ───────────────────────────────────────────────────────────────────
os.environ.setdefault("no_proxy", "localhost,127.0.0.1,loogle.lean-lang.org")
os.environ.setdefault("NO_PROXY", os.environ["no_proxy"])

# Load .env from sibling directory
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

DSN = os.environ.get(
    "DATABASE_URL",
    "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg",
)

# ── 日志 ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("backfill")

# ── 参数 ───────────────────────────────────────────────────────────────────
BATCH_SIZE = 20        # 每批条数
INTER_BATCH_SLEEP = 2  # 批间 sleep(s)，让出资源给飞轮
PROGRESS_EVERY = 100   # 每N条打一次进度
FAIL_PLACEHOLDER = "[翻译失败,待重试]"

# ── 翻译 ───────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))
from aii.service.ku_translate import translate_ku_to_zh, _OLLAMA_BASE, _MODEL


def _warmup_model() -> None:
    """Ping Ollama to load qwen3.5:9b into VRAM before batch starts."""
    import requests
    try:
        log.info("Warming up %s ...", _MODEL)
        r = requests.post(
            f"{_OLLAMA_BASE}/api/chat",
            json={
                "model": _MODEL,
                "think": False,
                "keep_alive": "1h",
                "messages": [{"role": "user", "content": "ping"}],
                "stream": False,
                "options": {"temperature": 0.1},
            },
            timeout=300,
        )
        r.raise_for_status()
        log.info("Model warm, ready to translate.")
    except Exception as e:
        log.warning("Warmup failed (will try anyway): %s", e)


# ── 主循环 ─────────────────────────────────────────────────────────────────
async def main() -> None:
    import asyncpg

    pool = await asyncpg.create_pool(DSN, min_size=1, max_size=3)
    log.info("DB connected. Warming up model...")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _warmup_model)
    log.info("Starting backfill...")

    done = 0
    failed = 0

    while True:
        # ★断点续传: 只取还没翻译的英文KU
        rows = await pool.fetch(
            """
            SELECT ku_id::text, natural_text,
                   (symbolic_form IS NOT NULL AND symbolic_form != 'null'::jsonb) AS has_f
            FROM aii.ku
            WHERE natural_text !~ '[一-龥]'
              AND natural_text_zh IS NULL
              AND is_synthesis IS NOT TRUE
            ORDER BY created_at
            LIMIT $1
            """,
            BATCH_SIZE,
        )

        if not rows:
            log.info("全部完成! done=%d failed=%d", done, failed)
            break

        updates: list[tuple[str, str]] = []
        for r in rows:
            try:
                # translate_ku_to_zh 是同步调用 Ollama HTTP，放 executor 不堵事件循环
                _nt = r["natural_text"]
                _hf = r["has_f"]
                zh = await loop.run_in_executor(
                    None, lambda nt=_nt, hf=_hf: translate_ku_to_zh(nt, hf)
                )
                if zh:
                    updates.append((zh, r["ku_id"]))
                    done += 1
                else:
                    # 空字符串 = 翻译失败或本来就是中文（后者不该进来）
                    updates.append((FAIL_PLACEHOLDER, r["ku_id"]))
                    failed += 1
                    log.warning("translate returned empty for %s", r["ku_id"][:8])
            except Exception as e:
                updates.append((FAIL_PLACEHOLDER, r["ku_id"]))
                failed += 1
                log.warning("translate exception %s: %s", r["ku_id"][:8], str(e)[:80])

        # ★批量写入 — 只动 natural_text_zh，不碰 natural_text/embedding
        if updates:
            await pool.executemany(
                "UPDATE aii.ku SET natural_text_zh = $1 WHERE ku_id = $2::uuid",
                updates,
            )

        if done > 0 and done % PROGRESS_EVERY < BATCH_SIZE:
            remaining = await pool.fetchval(
                """SELECT count(*) FROM aii.ku
                   WHERE natural_text !~ '[一-龥]'
                     AND natural_text_zh IS NULL
                     AND is_synthesis IS NOT TRUE"""
            )
            log.info("进度: done=%d failed=%d 剩余=%d", done, failed, remaining)

        await asyncio.sleep(INTER_BATCH_SLEEP)

    await pool.close()
    log.info("回填脚本退出.")


if __name__ == "__main__":
    asyncio.run(main())
