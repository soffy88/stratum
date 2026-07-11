"""AII 全自动回流：监控 needs.json → 自动拉料入库。

Pipeline:
  needs.json → 性质判断 → 护栏检查 → 话题→查询条件映射 → 创建订阅 → 触发扫描 → 记日志

五道护栏 (§4):
  G1 MAX_PER_NEED=20      一个 need 实际入库篇数上限——书/论文分桶各自记账（论文吃满不堵拉书）
  G2 MAX_PER_DAY=50       每天全局最多创建 50 个订阅
  G3 MAX_PER_MONTH=500    每月全局最多创建 500 个订阅
  G4 source whitelist     arxiv / gutenberg / openstax / mit_ocw（oapen 代理服务 :8766 缺失待建）
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

MAX_PER_NEED = 20  # 一个 need 实际入库篇数上限（书/论文分桶, 各自 ≤ 此值）
# G1 分桶依据: 四个飞轮只吃有章节教材, 但 arxiv 论文曾把单桶配额全部吃满
# (2026-07-11 实测 6/6 个 need 被 G1 卡死, 历史累计 3992 篇论文 vs 340 本书),
# 不分桶的话"拉书"通道被论文永久堵死。
_BOOK_SOURCES = frozenset({"gutenberg", "oapen", "openstax", "mit_ocw"})
MAX_PER_DAY = 50
MAX_PER_MONTH = 500
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
                "source_type": "openstax",
                "query": {"subjects": ["Business"], "keywords": "finance"},
            },
            {
                "source_type": "oapen",
                "query": {"query": "quantitative finance"},
                "max_results": 5,
            },
            {
                "source_type": "mit_ocw",
                "query": {"departments": ["15"], "keywords": "finance", "max_pdfs_per_course": 4},
                "max_results": 8,
            },
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
            {
                "source_type": "openstax",
                "query": {"subjects": ["Math"], "keywords": "statistics"},
            },
            {
                "source_type": "oapen",
                "query": {"query": "probability statistics"},
                "max_results": 5,
            },
            {
                "source_type": "arxiv",
                "query": {"categories": ["math.PR", "math.ST", "math.HO"], "keywords": "lecture notes"},
                "max_results": 10,
                "bucket": "book",
            },
            {
                "source_type": "mit_ocw",
                "query": {
                    "departments": ["18"],
                    "keywords": "probability",
                    "max_pdfs_per_course": 4,
                },
                "max_results": 8,
            },
        ],
    ),
    (
        ["微积分", "calculus", "分析", "analysis", "实分析"],
        [
            {
                "source_type": "arxiv",
                "query": {"categories": ["math.CA"], "keywords": "calculus analysis"},
            },
            {
                # ★arXiv 长篇讲义(lecture notes): 定理编号密集, classify 的"讲义型"门
                # (≥300KB+定理≥40)会路由进数学池——math-prog B范式的规模化粮源。
                "source_type": "arxiv",
                "query": {"categories": ["math.CA", "math.HO"], "keywords": "lecture notes"},
                "max_results": 10,
                "bucket": "book",  # 讲义实为书: 走书桶配额, 别和论文抢
            },
            {"source_type": "gutenberg", "query": {"topic": "calculus", "languages": ["en"]}},
            {
                "source_type": "openstax",
                "query": {"subjects": ["Math"], "keywords": "calculus"},
            },
            {
                "source_type": "oapen",
                "query": {"query": "calculus analysis"},
                "max_results": 5,
            },
        ],
    ),
    (
        ["线性代数", "linear algebra", "矩阵", "matrix", "向量空间"],
        [
            {
                "source_type": "arxiv",
                "query": {"categories": ["math.LA"], "keywords": "linear algebra matrix"},
            },
            {
                "source_type": "arxiv",
                "query": {"categories": ["math.LA", "math.RA"], "keywords": "lecture notes"},
                "max_results": 10,
                "bucket": "book",
            },
            {"source_type": "gutenberg", "query": {"topic": "algebra", "languages": ["en"]}},
            {
                "source_type": "openstax",
                "query": {"subjects": ["Math"], "keywords": "algebra"},
            },
            {
                "source_type": "oapen",
                "query": {"query": "linear algebra"},
                "max_results": 5,
            },
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
            {
                "source_type": "oapen",
                "query": {"query": "machine learning"},
                "max_results": 5,
            },
            {
                "source_type": "mit_ocw",
                "query": {
                    "departments": ["6"],
                    "keywords": "machine learning",
                    "max_pdfs_per_course": 4,
                },
                "max_results": 8,
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
        ["最优化", "凸优化", "optimization", "convex", "运筹", "operations research"],
        [
            {
                "source_type": "arxiv",
                "query": {"categories": ["math.OC"], "keywords": "optimization"},
            },
            {
                "source_type": "oapen",
                "query": {"query": "optimization"},
                "max_results": 5,
            },
            {
                "source_type": "arxiv",
                "query": {"categories": ["math.OC", "math.HO"], "keywords": "lecture notes"},
                "max_results": 10,
                "bucket": "book",
            },
            {
                "source_type": "mit_ocw",
                "query": {
                    "departments": ["18", "15"],
                    "keywords": "optimization",
                    "max_pdfs_per_course": 4,
                },
                "max_results": 8,
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
            {
                "source_type": "openstax",
                "query": {"subjects": ["Business"], "keywords": "econom"},
            },
            {
                "source_type": "oapen",
                # 单词 "economics" 上游命中恒 0(DSpace 搜索怪癖), 多词才有结果
                "query": {"query": "macroeconomics"},
                "max_results": 5,
            },
            {
                "source_type": "mit_ocw",
                "query": {"departments": ["14", "15"], "max_pdfs_per_course": 4},
                "max_results": 8,
            },
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
            {
                "source_type": "arxiv",
                "query": {
                    "categories": ["math.NT", "math.GR", "math.AT", "math.HO"],
                    "keywords": "lecture notes",
                },
                "max_results": 10,
                "bucket": "book",
            },
            {"source_type": "gutenberg", "query": {"topic": "mathematics", "languages": ["en"]}},
            {
                "source_type": "oapen",
                "query": {"query": "abstract algebra number theory"},
                "max_results": 5,
            },
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
            def _is_book_spec(q):
                return q["source_type"] in _BOOK_SOURCES or q.get("bucket") == "book"

            if need_type == "book":
                filtered = [q for q in queries if _is_book_spec(q)]
            elif need_type == "paper":
                filtered = [q for q in queries if not _is_book_spec(q)]
            else:
                # 中性：书优先（含 bucket=book 的讲义 spec），纯论文 arxiv 补充
                books = [q for q in queries if _is_book_spec(q)]
                papers = [q for q in queries if not _is_book_spec(q)]
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


def _need_hash(topic: str) -> str:
    """按 topic 本身算哈希, 不能带 reason——reason 里嵌了 ku_count, 每轮飞轮进化都在涨,

    混进哈希会导致同一个 topic 每次 tick 都算出"新"哈希, 让 G1/G5 两道护栏(按 need_hash
    记账)形同虚设, 造成同一 topic 反复建全新订阅(2026-07-09 实测: 同一 topic 105条订阅
    只有3种真实query, 105-3=102条是这个bug造出来的重复)。
    """
    return hashlib.sha256(topic.encode()).hexdigest()[:16]


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


def _guardrail_need_count(need_hash: str, sources: frozenset[str] | None = None) -> int:
    """此 need 跨全部历史已实际入库的篇数（SUM ingested_count）。

    sources 给定时只统计这些源——G1 按书/论文分桶记账用。
    """
    try:
        sql = "SELECT COALESCE(SUM(ingested_count), 0) FROM aii_processed_needs WHERE need_hash=?"
        params: list = [need_hash]
        if sources:
            sql += f" AND source_type IN ({','.join('?' * len(sources))})"
            params.extend(sorted(sources))
        with get_conn() as conn:
            row = conn.execute(sql, tuple(params)).fetchone()
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
    """按 (user_id, source_type, query) 复用已有 active 订阅, 没有才新建, 然后立即触发扫描。
    返回 (sub_id, ingested_count)。

    复用而不是每次都新建, 是因为 _need_hash 修好之后 G1/G5 护栏会让同一 topic 每小时
    仍可能被处理若干轮(直到配额用完/连续miss达标才停)——如果这里还是无脑INSERT, 同一个
    query 依然会攒出一堆新订阅行, 只是比之前(每小时必建)慢一点, 治标不治本。

    _runner: 测试注入点（keyword-only）。None→生产路径 _check_one_subscription；
             非 None→调 _runner(sub_id, user_id, source_type, query, max_results)。
    """
    from ulid import ULID

    query_json = json.dumps(query, ensure_ascii=False)
    try:
        with get_conn() as conn:
            existing = conn.execute(
                "SELECT id FROM source_subscriptions "
                "WHERE user_id=? AND source_type=? AND query_json=? AND status='active'",
                (user_id, source_type, query_json),
            ).fetchone()
        if existing:
            sub_id = existing[0]
        else:
            sub_id = str(ULID())
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
                        query_json,
                        max_results,
                    ),
                )
    except Exception as exc:
        log.error("aii_feedback: create/lookup subscription failed: %s", exc)
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
    if not topic:
        return

    nh = _need_hash(topic)
    log.info("aii_feedback: processing need hash=%s topic=%r", nh, topic[:50])

    # G2/G3: daily/monthly cap
    day_c, mon_c = _guardrail_daily_monthly()
    if day_c >= MAX_PER_DAY:
        log.warning("aii_feedback: G2 daily cap reached (%d), skip", day_c)
        return
    if mon_c >= MAX_PER_MONTH:
        log.warning("aii_feedback: G3 monthly cap reached (%d), skip", mon_c)
        return

    # G1: per-need 入库篇数上限（历史累计, 书/论文分桶——论文吃满不堵拉书）
    already_books = _guardrail_need_count(nh, _BOOK_SOURCES)
    already_papers = _guardrail_need_count(nh) - already_books
    if already_books >= MAX_PER_NEED and already_papers >= MAX_PER_NEED:
        log.info(
            "aii_feedback: G1 quota full (books=%d papers=%d) for topic=%r",
            already_books,
            already_papers,
            topic[:50],
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
    total_books = 0
    total_papers = 0
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

        # G1: 按剩余配额分配 max_results（历史+本轮已拉累计不超上限, 书/论文各自记账;
        # 本桶吃满只跳过该源, 另一桶的源继续——不能 break）
        is_book = source_type in _BOOK_SOURCES or q_spec.get("bucket") == "book"
        remaining = max(
            0,
            MAX_PER_NEED
            - (already_books if is_book else already_papers)
            - (total_books if is_book else total_papers),
        )
        if remaining <= 0:
            log.info(
                "aii_feedback: G1 %s quota exhausted for topic=%r, skip source=%s",
                "book" if is_book else "paper",
                topic[:50],
                source_type,
            )
            continue
        max_r = min(q_spec.get("max_results", remaining), remaining)

        query = q_spec.get("query", {})
        sub_name = f"[AII] {topic[:60]} ({source_type})"

        sub_id, ingested = await _create_and_run_subscription(
            user_id, source_type, query, sub_name, max_r, _runner=_runner
        )
        total_ingested += ingested
        if is_book:
            total_books += ingested
        else:
            total_papers += ingested

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
        # ★subtopics 也是真实 KG 缺口(aii backend 按 purpose 拆出的子方向): 只处理主
        # topic 时, 每个 need 的书配额终身 20 本, 主题集固定 → 拉满即永久断供("修完
        # 过几天又空转"的结构性根因)。子题各自成 need(独立 hash=独立配额), 供给×10;
        # G2/G3 日/月闸和 G5 反循环照常兜底, 不会失控。
        for sub in (need.get("subtopics") or [])[:10]:
            sub = (sub or "").strip()
            if not sub:
                continue
            try:
                await _process_one_need(
                    {"topic": sub, "reason": f"subtopic of {need.get('topic', '')}"}, user_id
                )
            except Exception as exc:
                log.error("aii_feedback: error processing subtopic=%r: %s", sub[:40], exc)
