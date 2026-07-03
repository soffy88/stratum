"""AII 全自动回流：监控 needs.json → 自动拉料入库。

Pipeline:
  needs.json → 性质判断 → 护栏检查 → 话题→查询条件映射 → 创建订阅 → 触发扫描 → 记日志

五道护栏 (§4):
  G1 MAX_PER_NEED=5       一个 need 实际入库总篇数 ≤ 5（跨源累计，不是每源5）
  G2 MAX_PER_DAY=20       每天全局最多创建 20 个订阅
  G3 MAX_PER_MONTH=200    每月全局最多创建 200 个订阅
  G4 source whitelist     只用 arxiv / gutenberg（oapen 网络待修）
  G5 anti-loop            同 need 2 轮 ingested=0 → needs_human_review，停

need 性质判断 (§3):
  "是什么"/"基础"/"入门"/"原理" → 拉书（gutenberg/oapen）
  "最新"/"方法"/"算法"/"前沿"  → 拉论文（arxiv）
  不命中 → 默认偏书（书先，arxiv 少量补充）

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

NEEDS_FILE = Path("/data/shared/aii-to-stratum/needs.json")
FEEDBACK_LOG = Path("/data/logs/aii_feedback.log")
UNRESOLVED_LOG = Path("/data/logs/aii_unresolved.log")

LOOP_INTERVAL = 3600  # 1h
ALLOWED_SOURCES = {"arxiv", "gutenberg", "oapen", "openstax", "mit_ocw"}

MAX_PER_NEED = 5  # 一个 need 实际入库总篇数上限
MAX_PER_DAY = 20
MAX_PER_MONTH = 200
ANTI_LOOP_ROUNDS = 2  # 连续 N 轮 ingested=0 → 停

# ── need 性质信号词（§3）─────────────────────────────────────────────────────

_BOOK_SIGNALS = (
    "是什么",
    "什么是",
    "基础",
    "入门",
    "原理",
    "概念",
    "导论",
    "介绍",
    "教材",
    "what is",
    "introduction",
    "basics",
    "fundamentals",
)
_PAPER_SIGNALS = (
    "最新",
    "方法",
    "算法",
    "前沿",
    "sota",
    "进展",
    "研究",
    "模型",
    "如何",
    "怎么",
    "实现",
    "latest",
    "method",
    "algorithm",
    "survey",
)


def _classify_need_type(topic: str) -> str:
    """返回 'book' | 'paper' | 'both'。默认偏书（AII high_miss 多为基础盲区）。"""
    tl = topic.lower()
    has_book = any(s in tl for s in _BOOK_SIGNALS)
    has_paper = any(s in tl for s in _PAPER_SIGNALS)
    if has_book and not has_paper:
        return "book"
    if has_paper and not has_book:
        return "paper"
    return "both"  # 中性：书优先 + arxiv 少量补充


# ── 话题→查询 映射表（无需 LLM 的快速路径）────────────────────────────────

_TOPIC_MAP: list[tuple[list[str], list[dict]]] = [
    # ── 量化金融（优先于「统计」规则，防止「统计套利」被子串误命中概率规则） ──
    (
        [
            "量化交易",
            "统计套利",
            "套利",
            "高频交易",
            "做市",
            "对冲基金",
            "量化投资",
            "因子投资",
            "配对交易",
            "alpha策略",
            "arbitrage",
            "quantitative trading",
            "pairs trading",
            "market making",
            "high frequency trading",
            "algorithmic trading",
            "factor investing",
        ],
        [
            {
                "source_type": "arxiv",
                "query": {
                    "categories": ["q-fin.ST", "q-fin.TR", "q-fin.PM"],
                    "keywords": "statistical arbitrage quantitative finance",
                },
            },
        ],
    ),
    # ── 对冲/宏观金融（宽泛的"金融"落到 econ 规则，这里只管量化层） ──
    (
        ["概率", "probability", "随机", "stochastic", "统计", "统计学"],
        [
            {
                "source_type": "arxiv",
                "query": {
                    "categories": ["math.PR", "stat.TH"],
                    "keywords": "probability distribution statistics",
                },
            },
            {"source_type": "gutenberg", "query": {"topic": "probability", "languages": ["en"]}},
        ],
    ),
    (
        ["微积分", "calculus", "分析", "analysis", "实分析"],
        [
            {
                "source_type": "arxiv",
                "query": {"categories": ["math.CA"], "keywords": "calculus analysis"},
            },
            {"source_type": "gutenberg", "query": {"topic": "calculus", "languages": ["en"]}},
        ],
    ),
    (
        ["线性代数", "linear algebra", "矩阵", "matrix", "向量空间"],
        [
            {
                "source_type": "arxiv",
                "query": {"categories": ["math.LA"], "keywords": "linear algebra matrix"},
            },
            {"source_type": "gutenberg", "query": {"topic": "algebra", "languages": ["en"]}},
        ],
    ),
    (
        ["机器学习", "machine learning", "神经网络", "deep learning", "深度学习"],
        [
            {
                "source_type": "arxiv",
                "query": {
                    "categories": ["cs.LG", "stat.ML"],
                    "keywords": "machine learning neural network",
                },
            },
            {
                "source_type": "gutenberg",
                "query": {"topic": "computer science", "languages": ["en"]},
            },
        ],
    ),
    (
        ["强化学习", "reinforcement learning", "RL", "策略优化"],
        [
            {
                "source_type": "arxiv",
                "query": {
                    "categories": ["cs.LG", "cs.AI"],
                    "keywords": "reinforcement learning policy optimization",
                },
            },
        ],
    ),
    (
        ["经济学", "economics", "宏观经济", "微观经济", "金融"],
        [
            {
                "source_type": "arxiv",
                "query": {"categories": ["econ.GN", "q-fin.GN"], "keywords": "economics"},
            },
            {"source_type": "gutenberg", "query": {"topic": "economics", "languages": ["en"]}},
        ],
    ),
    (
        ["数论", "number theory", "代数", "algebra", "拓扑", "topology"],
        [
            {
                "source_type": "arxiv",
                "query": {
                    "categories": ["math.NT", "math.GR", "math.AT"],
                    "keywords": "mathematics",
                },
            },
            {"source_type": "gutenberg", "query": {"topic": "mathematics", "languages": ["en"]}},
        ],
    ),
    (
        ["物理", "physics", "量子", "quantum", "力学", "mechanics"],
        [
            {
                "source_type": "arxiv",
                "query": {"categories": ["physics.gen-ph", "quant-ph"], "keywords": "physics"},
            },
            {"source_type": "gutenberg", "query": {"topic": "physics", "languages": ["en"]}},
        ],
    ),
]


def _map_topic_rule(topic: str, need_type: str = "both") -> list[dict] | None:
    """快速规则映射，按 need_type 过滤来源。返回 [{source_type, query},...] 或 None。"""
    topic_l = topic.lower()
    for keywords, queries in _TOPIC_MAP:
        if any(k.lower() in topic_l for k in keywords):
            if need_type == "book":
                filtered = [q for q in queries if q["source_type"] != "arxiv"]
            elif need_type == "paper":
                filtered = [q for q in queries if q["source_type"] not in ("gutenberg", "oapen")]
            else:
                # 中性：书优先（gutenberg/oapen 先），arxiv 补充
                books = [q for q in queries if q["source_type"] in ("gutenberg", "oapen")]
                papers = [q for q in queries if q["source_type"] == "arxiv"]
                filtered = books + papers
            return filtered if filtered else queries  # 若该性质无对应源则回退全部
    return None


def _map_topic_llm(topic: str) -> list[dict]:
    """LLM 兜底映射。失败则返回空列表（静默记日志）。"""
    try:
        from oprim.llm.llm_call import llm_call

        prompt = (
            f"学术知识需求: 「{topic}」\n\n"
            "将此需求映射到以下数据源的查询参数。只返回 JSON，不加解释。\n\n"
            '格式: [{"source_type": "arxiv", "query": {"categories": ["math.XX"], "keywords": "english keywords"}}, '
            '{"source_type": "gutenberg", "query": {"topic": "english topic", "languages": ["en"]}}]\n\n'
            "arxiv 分类示例: math.PR(概率), math.CA(分析), math.LA(线代), cs.LG(ML), econ.GN(经济), physics.gen-ph(物理)\n"
            "gutenberg 主题: 1-3 个英文单词描述学科"
        )
        result = llm_call(prompt=prompt, provider="nvidia_nim", model="meta/llama-3.1-70b-instruct")
        raw = result.text.strip()
        # 提取 JSON 数组
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if not m:
            raise ValueError(f"no JSON array in LLM response: {raw[:200]}")
        queries = json.loads(m.group(0))
        return [q for q in queries if q.get("source_type") in ALLOWED_SOURCES]
    except Exception as exc:
        log.warning("aii_feedback: LLM mapping failed for topic=%r: %s", topic[:50], exc)
        return []


def _map_topic(topic: str) -> tuple[list[dict], str]:
    """topic → (sources_list, need_type)。规则优先，LLM 兜底。"""
    need_type = _classify_need_type(topic)
    log.info("aii_feedback: need_type=%r for topic=%r", need_type, topic[:40])
    queries = _map_topic_rule(topic, need_type)
    if queries is not None:
        log.info(
            "aii_feedback: rule-mapped topic=%r → %d sources (type=%s)",
            topic[:40],
            len(queries),
            need_type,
        )
        return queries, need_type
    log.info("aii_feedback: no rule match for topic=%r, falling back to LLM", topic[:40])
    return _map_topic_llm(topic), need_type


# ── 护栏 ────────────────────────────────────────────────────────────────────


def _need_hash(topic: str, reason: str = "") -> str:
    return hashlib.sha256(f"{topic}|{reason}".encode()).hexdigest()[:16]


def _guardrail_daily_monthly() -> tuple[int, int]:
    """返回 (today_count, month_count) from aii_processed_needs。"""
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    try:
        with get_conn() as conn:
            day_c = conn.execute(
                "SELECT COUNT(*) FROM aii_processed_needs WHERE result='ok' AND processed_at >= ?",
                (day_start.isoformat(),),
            ).fetchone()[0]
            mon_c = conn.execute(
                "SELECT COUNT(*) FROM aii_processed_needs WHERE result='ok' AND processed_at >= ?",
                (month_start.isoformat(),),
            ).fetchone()[0]
        return day_c, mon_c
    except Exception as exc:
        log.warning("aii_feedback: guardrail count query failed: %s", exc)
        return 0, 0


def _guardrail_need_count(need_hash: str) -> int:
    """此 need 跨全部历史已实际入库的论文/书总数（SUM ingested_count）。"""
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(ingested_count), 0) FROM aii_processed_needs WHERE need_hash=?",
                (need_hash,),
            ).fetchone()
        return int(row[0]) if row else 0
    except Exception as exc:
        log.warning("aii_feedback: need_count query failed: %s", exc)
        return 0


def _anti_loop_check(need_hash: str, source_type: str) -> bool:
    """G5: 检查该 source_type 是否连续 miss。True = 应停（记 needs_human_review）。"""
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT miss_rounds FROM aii_processed_needs WHERE need_hash=? AND source_type=?",
                (need_hash, source_type),
            ).fetchone()
        return bool(row and row[0] >= ANTI_LOOP_ROUNDS)
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
    *,
    _runner=None,
) -> tuple[str | None, int]:
    """创建订阅并立即触发扫描。返回 (sub_id, ingested_count)。

    _runner: 测试注入点（keyword-only）。None→生产路径 _check_one_subscription；
             非 None→调 _runner(sub_id, user_id, source_type, query, max_results)。
    """
    from ulid import ULID

    sub_id = str(ULID())
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO source_subscriptions "
                "(id, user_id, source_type, name, query_json, max_results, status, scan_status) "
                "VALUES (?, ?, ?, ?, ?, ?, 'active', 'idle')",
                (
                    sub_id,
                    user_id,
                    source_type,
                    name[:200],
                    json.dumps(query, ensure_ascii=False),
                    max_results,
                ),
            )
    except Exception as exc:
        log.error("aii_feedback: create subscription failed: %s", exc)
        return None, 0

    try:
        if _runner is not None:
            await _runner(sub_id, user_id, source_type, query, max_results)
        else:
            from stratum.services.source_watcher_service import _check_one_subscription

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


def _get_prev_miss_rounds(need_hash: str, source_type: str) -> int:
    """当前 (need, source) 的连续 miss 轮数。仅读最近一行（已有 UNIQUE 保证单行）。"""
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT miss_rounds FROM aii_processed_needs WHERE need_hash=? AND source_type=?",
                (need_hash, source_type),
            ).fetchone()
        return row[0] if row else 0
    except Exception:
        return 0


def _record_need(
    need_hash: str,
    topic: str,
    source_type: str,
    sub_id: str | None,
    result: str,
    miss_rounds: int,
    ingested_count: int = 0,
    notes: str = "",
) -> None:
    from ulid import ULID

    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO aii_processed_needs "
                "(id, need_hash, topic, source_type, sub_id, result, miss_rounds, ingested_count, notes, processed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NOW()) "
                "ON CONFLICT (need_hash, source_type) DO UPDATE SET "
                "sub_id=excluded.sub_id, result=excluded.result, "
                "miss_rounds=excluded.miss_rounds, "
                "ingested_count=aii_processed_needs.ingested_count + excluded.ingested_count, "
                "notes=excluded.notes, processed_at=excluded.processed_at",
                (
                    str(ULID()),
                    need_hash,
                    topic[:300],
                    source_type,
                    sub_id,
                    result,
                    miss_rounds,
                    ingested_count,
                    notes[:500],
                ),
            )
    except Exception as exc:
        log.error("aii_feedback: record need failed: %s", exc)


# ── 主处理逻辑 ────────────────────────────────────────────────────────────────


async def _process_one_need(need: dict, user_id: str, *, _runner=None) -> None:
    topic = (need.get("topic") or "").strip()
    reason = need.get("reason", "")
    if not topic:
        return

    nh = _need_hash(topic, reason)
    log.info("aii_feedback: processing need hash=%s topic=%r", nh, topic[:50])

    # G2/G3: daily/monthly cap
    day_c, mon_c = _guardrail_daily_monthly()
    if day_c >= MAX_PER_DAY:
        log.warning("aii_feedback: G2 daily cap reached (%d), skip", day_c)
        return
    if mon_c >= MAX_PER_MONTH:
        log.warning("aii_feedback: G3 monthly cap reached (%d), skip", mon_c)
        return

    # G1: per-need 总入库篇数上限（历史累计）
    already_ingested = _guardrail_need_count(nh)
    if already_ingested >= MAX_PER_NEED:
        log.info(
            "aii_feedback: G1 quota full (already=%d) for topic=%r", already_ingested, topic[:50]
        )
        return

    # 映射话题 → 查询条件（含 need_type 过滤）
    queries, need_type = _map_topic(topic)
    if not queries:
        log.warning("aii_feedback: no queries mapped for topic=%r", topic[:50])
        _record_need(nh, topic, "none", None, "error", 0, 0, "mapping returned empty")
        _log_to_file(UNRESOLVED_LOG, f"NO-MAPPING topic={topic!r} — 无法映射到任何数据源")
        return

    total_ingested = 0
    for q_spec in queries:
        source_type = q_spec.get("source_type", "")
        # G4: whitelist
        if source_type not in ALLOWED_SOURCES:
            log.info("aii_feedback: G4 skip non-whitelisted source=%r", source_type)
            continue

        # G5: per-source anti-loop（独立判定，不跨源污染）
        if _anti_loop_check(nh, source_type):
            log.warning(
                "aii_feedback: G5 anti-loop source=%r topic=%r, skip source",
                source_type,
                topic[:50],
            )
            _log_to_file(
                UNRESOLVED_LOG,
                f"ANTI-LOOP topic={topic!r} source={source_type} — 已达 {ANTI_LOOP_ROUNDS} 轮 miss，转人工",
            )
            continue  # 仅跳过此源，其他源继续

        # G2/G3 re-check
        day_c, mon_c = _guardrail_daily_monthly()
        if day_c >= MAX_PER_DAY or mon_c >= MAX_PER_MONTH:
            log.warning("aii_feedback: cap reached mid-loop, stopping")
            break

        # G1: 按剩余配额分配 max_results（历史+本轮已拉累计不超上限）
        remaining = max(0, MAX_PER_NEED - already_ingested - total_ingested)
        if remaining <= 0:
            log.info(
                "aii_feedback: G1 quota exhausted (total=%d), stopping",
                already_ingested + total_ingested,
            )
            break
        max_r = min(q_spec.get("max_results", remaining), remaining)

        query = q_spec.get("query", {})
        sub_name = f"[AII] {topic[:60]} ({source_type})"

        sub_id, ingested = await _create_and_run_subscription(
            user_id, source_type, query, sub_name, max_r, _runner=_runner
        )
        total_ingested += ingested

        if ingested == 0:
            miss_rounds = _get_prev_miss_rounds(nh, source_type) + 1
        else:
            miss_rounds = 0  # 只清自己源的计数

        result = (
            "ok"
            if ingested > 0
            else ("needs_human_review" if miss_rounds >= ANTI_LOOP_ROUNDS else "ok")
        )
        _record_need(
            nh,
            topic,
            source_type,
            sub_id,
            result,
            miss_rounds,
            ingested,
            f"need_type={need_type} ingested={ingested} query={json.dumps(query, ensure_ascii=False)[:180]}",
        )

        _log_to_file(
            FEEDBACK_LOG,
            f"need={topic!r} type={need_type} source={source_type} "
            f"sub={sub_id} ingested={ingested} result={result}",
        )

        if miss_rounds >= ANTI_LOOP_ROUNDS and ingested == 0:
            _log_to_file(
                UNRESOLVED_LOG,
                f"NEEDS-REVIEW topic={topic!r} source={source_type} — {ANTI_LOOP_ROUNDS} 轮 ingested=0",
            )

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

    needs = (
        data.get("needs", [])
        if isinstance(data, dict)
        else (data if isinstance(data, list) else [data])
    )
    if not needs:
        return

    user_id = _get_default_user_id()
    log.info("aii_feedback: tick — %d need(s) found", len(needs))

    for need in needs:
        try:
            await _process_one_need(need, user_id)
        except Exception as exc:
            log.error("aii_feedback: error processing need=%r: %s", str(need)[:80], exc)
