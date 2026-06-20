"""AII 全自动回流：监控 needs.json → 自动拉料入库。

Pipeline:
  needs.json → 护栏检查 → 话题→查询条件映射 → 创建订阅 → 触发扫描 → 记日志

五道护栏 (§4):
  G1 MAX_PER_NEED=5       每个 need 最多创建 5 个订阅
  G2 MAX_PER_DAY=20       每天全局最多创建 20 个订阅
  G3 MAX_PER_MONTH=200    每月全局最多创建 200 个订阅
  G4 source whitelist     只用 arxiv / gutenberg（oapen 网络待修）
  G5 anti-loop            同 need 2 轮 ingested=0 → needs_human_review，停

§20: 只调 Layer3/4 接口，不改主库。
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

from stratum.db import get_conn

log = logging.getLogger(__name__)

# ── 常量 ────────────────────────────────────────────────────────────────────

NEEDS_FILE   = Path("/data/shared/aii-to-stratum/needs.json")
FEEDBACK_LOG = Path("/data/logs/aii_feedback.log")
UNRESOLVED_LOG = Path("/data/logs/aii_unresolved.log")

LOOP_INTERVAL   = 3600   # 1h
ALLOWED_SOURCES = {"arxiv", "gutenberg"}   # oapen 待网络修复

MAX_PER_NEED    = 5
MAX_PER_DAY     = 20
MAX_PER_MONTH   = 200
ANTI_LOOP_ROUNDS = 2   # 连续 N 轮 ingested=0 → 停

# ── 话题→查询 映射表（无需 LLM 的快速路径）────────────────────────────────

_TOPIC_MAP: list[tuple[list[str], list[dict]]] = [
    (
        ["概率", "probability", "随机", "stochastic", "统计", "统计学"],
        [
            {"source_type": "arxiv",    "query": {"categories": ["math.PR", "stat.TH"], "keywords": "probability distribution statistics"}},
            {"source_type": "gutenberg","query": {"topic": "probability", "languages": ["en"]}},
        ],
    ),
    (
        ["微积分", "calculus", "分析", "analysis", "实分析"],
        [
            {"source_type": "arxiv",    "query": {"categories": ["math.CA"], "keywords": "calculus analysis"}},
            {"source_type": "gutenberg","query": {"topic": "calculus", "languages": ["en"]}},
        ],
    ),
    (
        ["线性代数", "linear algebra", "矩阵", "matrix", "向量空间"],
        [
            {"source_type": "arxiv",    "query": {"categories": ["math.LA"], "keywords": "linear algebra matrix"}},
            {"source_type": "gutenberg","query": {"topic": "algebra", "languages": ["en"]}},
        ],
    ),
    (
        ["机器学习", "machine learning", "神经网络", "deep learning", "深度学习"],
        [
            {"source_type": "arxiv",    "query": {"categories": ["cs.LG", "stat.ML"], "keywords": "machine learning neural network"}},
            {"source_type": "gutenberg","query": {"topic": "computer science", "languages": ["en"]}},
        ],
    ),
    (
        ["强化学习", "reinforcement learning", "RL", "策略优化"],
        [
            {"source_type": "arxiv",    "query": {"categories": ["cs.LG", "cs.AI"], "keywords": "reinforcement learning policy optimization"}},
        ],
    ),
    (
        ["经济学", "economics", "宏观经济", "微观经济", "金融"],
        [
            {"source_type": "arxiv",    "query": {"categories": ["econ.GN", "q-fin.GN"], "keywords": "economics"}},
            {"source_type": "gutenberg","query": {"topic": "economics", "languages": ["en"]}},
        ],
    ),
    (
        ["数论", "number theory", "代数", "algebra", "拓扑", "topology"],
        [
            {"source_type": "arxiv",    "query": {"categories": ["math.NT", "math.GR", "math.AT"], "keywords": "mathematics"}},
            {"source_type": "gutenberg","query": {"topic": "mathematics", "languages": ["en"]}},
        ],
    ),
    (
        ["物理", "physics", "量子", "quantum", "力学", "mechanics"],
        [
            {"source_type": "arxiv",    "query": {"categories": ["physics.gen-ph", "quant-ph"], "keywords": "physics"}},
            {"source_type": "gutenberg","query": {"topic": "physics", "languages": ["en"]}},
        ],
    ),
]


def _map_topic_rule(topic: str) -> list[dict] | None:
    """快速规则映射：返回 [{source_type, query}, ...] 或 None（未命中）。"""
    topic_l = topic.lower()
    for keywords, queries in _TOPIC_MAP:
        if any(k.lower() in topic_l for k in keywords):
            return queries
    return None


def _map_topic_llm(topic: str) -> list[dict]:
    """LLM 兜底映射。失败则返回空列表（静默记日志）。"""
    try:
        from oprim.llm.llm_call import llm_call

        prompt = (
            f"学术知识需求: 「{topic}」\n\n"
            "将此需求映射到以下数据源的查询参数。只返回 JSON，不加解释。\n\n"
            "格式: [{\"source_type\": \"arxiv\", \"query\": {\"categories\": [\"math.XX\"], \"keywords\": \"english keywords\"}}, "
            "{\"source_type\": \"gutenberg\", \"query\": {\"topic\": \"english topic\", \"languages\": [\"en\"]}}]\n\n"
            "arxiv 分类示例: math.PR(概率), math.CA(分析), math.LA(线代), cs.LG(ML), econ.GN(经济), physics.gen-ph(物理)\n"
            "gutenberg 主题: 1-3 个英文单词描述学科"
        )
        result = llm_call(prompt=prompt, provider="qwen3_dashscope", model="qwen-plus")
        raw = result.text.strip()
        # 提取 JSON 数组
        m = re.search(r'\[.*\]', raw, re.DOTALL)
        if not m:
            raise ValueError(f"no JSON array in LLM response: {raw[:200]}")
        queries = json.loads(m.group(0))
        return [q for q in queries if q.get("source_type") in ALLOWED_SOURCES]
    except Exception as exc:
        log.warning("aii_feedback: LLM mapping failed for topic=%r: %s", topic[:50], exc)
        return []


def _map_topic(topic: str) -> list[dict]:
    """topic → [{source_type, query}] 列表（规则优先，LLM 兜底）。"""
    queries = _map_topic_rule(topic)
    if queries is not None:
        log.info("aii_feedback: rule-mapped topic=%r → %d sources", topic[:40], len(queries))
        return queries
    log.info("aii_feedback: no rule match for topic=%r, falling back to LLM", topic[:40])
    return _map_topic_llm(topic)


# ── 护栏 ────────────────────────────────────────────────────────────────────

def _need_hash(topic: str, reason: str = "") -> str:
    return hashlib.sha256(f"{topic}|{reason}".encode()).hexdigest()[:16]


def _guardrail_daily_monthly() -> tuple[int, int]:
    """返回 (today_count, month_count) from aii_processed_needs。"""
    now = datetime.now(timezone.utc)
    day_start   = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    try:
        with get_conn() as conn:
            day_c = conn.execute(
                "SELECT COUNT(*) FROM aii_processed_needs WHERE result='ok' AND processed_at >= ?",
                (day_start.isoformat(),)
            ).fetchone()[0]
            mon_c = conn.execute(
                "SELECT COUNT(*) FROM aii_processed_needs WHERE result='ok' AND processed_at >= ?",
                (month_start.isoformat(),)
            ).fetchone()[0]
        return day_c, mon_c
    except Exception as exc:
        log.warning("aii_feedback: guardrail count query failed: %s", exc)
        return 0, 0


def _guardrail_need_count(need_hash: str) -> int:
    """本 need 已创建的订阅数。"""
    try:
        with get_conn() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM aii_processed_needs WHERE need_hash=? AND result='ok'",
                (need_hash,)
            ).fetchone()[0]
    except Exception as exc:
        log.warning("aii_feedback: need_count query failed: %s", exc)
        return 0


def _anti_loop_check(need_hash: str, topic: str) -> bool:
    """G5: 检查是否连续 miss。True = 应停（记 needs_human_review）。"""
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT miss_rounds FROM aii_processed_needs WHERE need_hash=? ORDER BY processed_at DESC LIMIT 1",
                (need_hash,)
            ).fetchone()
        if row and row[0] >= ANTI_LOOP_ROUNDS:
            return True
        return False
    except Exception as exc:
        log.warning("aii_feedback: anti_loop query failed: %s", exc)
        return False


# ── 订阅创建 ─────────────────────────────────────────────────────────────────

def _get_default_user_id() -> str:
    """取现有订阅用的 user_id_hash（系统用户）。"""
    try:
        with get_conn() as conn:
            row = conn.execute("SELECT user_id FROM source_subscriptions LIMIT 1").fetchone()
        return row[0] if row else "56d6bc01edc35765"
    except Exception:
        pass
    return "56d6bc01edc35765"


async def _create_and_run_subscription(
    user_id: str,
    source_type: str,
    query: dict,
    name: str,
    max_results: int = 5,
) -> tuple[str | None, int]:
    """创建订阅并立即触发扫描。返回 (sub_id, ingested_count)。"""
    from ulid import ULID
    from stratum.services.source_watcher_service import _check_one_subscription

    sub_id = str(ULID())
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO source_subscriptions "
                "(id, user_id, source_type, name, query_json, max_results, status, scan_status) "
                "VALUES (?, ?, ?, ?, ?, ?, 'active', 'idle')",
                (sub_id, user_id, source_type, name[:200],
                 json.dumps(query, ensure_ascii=False), max_results),
            )
    except Exception as exc:
        log.error("aii_feedback: create subscription failed: %s", exc)
        return None, 0

    try:
        await _check_one_subscription(sub_id, user_id, source_type, query, max_results)
    except Exception as exc:
        log.error("aii_feedback: scan failed sub=%s: %s", sub_id, exc)

    # 读取最终 ingested_count（与 FastAPI 共享同一连接，无锁争用）
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT ingested_count FROM source_subscriptions WHERE id=?", (sub_id,)
            ).fetchone()
        return sub_id, (row[0] if row else 0)
    except Exception:
        pass
    return sub_id, 0


# ── 日志 ─────────────────────────────────────────────────────────────────────

def _log_to_file(path: Path, msg: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception as exc:
        log.warning("aii_feedback: write log failed %s: %s", path, exc)


def _record_need(need_hash: str, topic: str, source_type: str, sub_id: str | None,
                 result: str, miss_rounds: int, notes: str = "") -> None:
    from ulid import ULID
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO aii_processed_needs "
                "(id, need_hash, topic, source_type, sub_id, result, miss_rounds, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (str(ULID()), need_hash, topic[:300], source_type, sub_id,
                 result, miss_rounds, notes[:500]),
            )
    except Exception as exc:
        log.error("aii_feedback: record need failed: %s", exc)


# ── 主处理逻辑 ────────────────────────────────────────────────────────────────

async def _process_one_need(need: dict, user_id: str) -> None:
    topic  = (need.get("topic") or "").strip()
    reason = need.get("reason", "")
    if not topic:
        return

    nh = _need_hash(topic, reason)
    log.info("aii_feedback: processing need hash=%s topic=%r", nh, topic[:50])

    # G5: anti-loop
    if _anti_loop_check(nh, topic):
        log.warning("aii_feedback: G5 anti-loop triggered for topic=%r, skip", topic[:50])
        _log_to_file(UNRESOLVED_LOG,
            f"ANTI-LOOP topic={topic!r} reason={reason} — 已达 {ANTI_LOOP_ROUNDS} 轮 miss，转人工")
        return

    # G2/G3: daily/monthly cap
    day_c, mon_c = _guardrail_daily_monthly()
    if day_c >= MAX_PER_DAY:
        log.warning("aii_feedback: G2 daily cap reached (%d), skip", day_c)
        return
    if mon_c >= MAX_PER_MONTH:
        log.warning("aii_feedback: G3 monthly cap reached (%d), skip", mon_c)
        return

    # G1: per-need cap
    need_c = _guardrail_need_count(nh)
    if need_c >= MAX_PER_NEED:
        log.info("aii_feedback: G1 per-need cap reached (%d) for topic=%r", need_c, topic[:50])
        return

    # 映射话题 → 查询条件
    queries = _map_topic(topic)
    if not queries:
        log.warning("aii_feedback: no queries mapped for topic=%r", topic[:50])
        _record_need(nh, topic, "none", None, "error", 0, "mapping returned empty")
        _log_to_file(UNRESOLVED_LOG, f"NO-MAPPING topic={topic!r} — 无法映射到任何数据源")
        return

    total_ingested = 0
    for q_spec in queries:
        source_type = q_spec.get("source_type", "")
        # G4: whitelist
        if source_type not in ALLOWED_SOURCES:
            log.info("aii_feedback: G4 skip non-whitelisted source=%r", source_type)
            continue

        # G2/G3 re-check before each subscription (count may have grown)
        day_c, mon_c = _guardrail_daily_monthly()
        if day_c >= MAX_PER_DAY or mon_c >= MAX_PER_MONTH:
            log.warning("aii_feedback: cap reached mid-loop, stopping")
            break

        query   = q_spec.get("query", {})
        max_r   = min(q_spec.get("max_results", MAX_PER_NEED), MAX_PER_NEED)
        sub_name = f"[AII] {topic[:60]} ({source_type})"

        sub_id, ingested = await _create_and_run_subscription(
            user_id, source_type, query, sub_name, max_r
        )
        total_ingested += ingested

        miss_rounds = 0 if ingested > 0 else 1
        # 累加 miss_rounds（读上次记录，使用共享连接无锁争用）
        if ingested == 0:
            try:
                with get_conn() as _c:
                    prev = _c.execute(
                        "SELECT miss_rounds FROM aii_processed_needs WHERE need_hash=? ORDER BY processed_at DESC LIMIT 1",
                        (nh,)
                    ).fetchone()
                miss_rounds = (prev[0] if prev else 0) + 1
            except Exception:
                pass

        result = "ok" if ingested > 0 else ("needs_human_review" if miss_rounds >= ANTI_LOOP_ROUNDS else "ok")
        _record_need(nh, topic, source_type, sub_id, result, miss_rounds,
                     f"ingested={ingested} query={json.dumps(query, ensure_ascii=False)[:200]}")

        _log_to_file(FEEDBACK_LOG,
            f"need={topic!r} source={source_type} sub={sub_id} ingested={ingested} result={result}")

        if miss_rounds >= ANTI_LOOP_ROUNDS and ingested == 0:
            _log_to_file(UNRESOLVED_LOG,
                f"NEEDS-REVIEW topic={topic!r} source={source_type} — {ANTI_LOOP_ROUNDS} 轮 ingested=0")

    log.info("aii_feedback: need=%r done total_ingested=%d", topic[:40], total_ingested)

    if total_ingested > 0:
        # export_one 内部调 asyncio.run()，不能在已有 event loop 里直接调用；
        # 用 asyncio.to_thread 把它放到线程中运行，绕开嵌套 event loop 限制。
        try:
            from stratum.services.md_export_service import export_all
            result = await asyncio.to_thread(export_all)
            log.info("aii_feedback: md_export done: %s", result)
            _log_to_file(FEEDBACK_LOG, f"md_export {result}")
        except Exception as exc:
            log.warning("aii_feedback: md_export failed: %s", exc)


# ── 主循环 ────────────────────────────────────────────────────────────────────

async def aii_feedback_loop() -> None:
    """Lifespan 任务：每小时读 needs.json，处理新 need。"""
    await asyncio.sleep(120)  # 等待其他服务完全启动
    log.info("aii_feedback_loop: started, watching %s", NEEDS_FILE)

    while True:
        try:
            await _tick()
        except Exception:
            log.exception("aii_feedback_loop: tick failed")
        await asyncio.sleep(LOOP_INTERVAL)


async def _tick() -> None:
    if not NEEDS_FILE.exists():
        log.debug("aii_feedback: needs.json not found at %s", NEEDS_FILE)
        return

    try:
        raw = NEEDS_FILE.read_text(encoding="utf-8").strip()
        data = json.loads(raw)
    except Exception as exc:
        log.warning("aii_feedback: failed to read needs.json: %s", exc)
        return

    needs = data if isinstance(data, list) else [data]
    if not needs:
        return

    user_id = _get_default_user_id()
    log.info("aii_feedback: tick — %d need(s) found", len(needs))

    for need in needs:
        try:
            await _process_one_need(need, user_id)
        except Exception as exc:
            log.error("aii_feedback: error processing need=%r: %s",
                      str(need)[:80], exc)
