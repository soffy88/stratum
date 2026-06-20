"""G5 anti-loop E2E test (R-3 SPEC-G5-v1.0).

真实往返验证：in-process 跑 _process_one_need 完整循环，真实 DuckDB（临时文件）。
唯一注入点：_create_and_run_subscription 的 _runner 参数（网络边界）。

验收（四项缺一不算 PASS）:
  O1  arxiv 侧真实进入 needs_human_review
  O2  UNRESOLVED_LOG 真实写入
  O3  gutenberg 侧不触发（miss_rounds 保持 0，result='ok'）
  O4  UPSERT 后 ingested_count SUM 正确

对照组：同 E2E 跑旧行为（_get_prev_miss_rounds 使用旧 SQL，
         ORDER BY processed_at DESC LIMIT 1，无 source_type 过滤）。
         证明旧代码 arxiv 不触发，根治有效。
"""
from __future__ import annotations

import asyncio
import contextlib
import time
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import duckdb
import pytest


# ── 测试 DB 建表 DDL（镜像 migration 039-041） ─────────────────────────────────

_DDL = """
CREATE TABLE aii_processed_needs (
    id           VARCHAR PRIMARY KEY,
    need_hash    VARCHAR NOT NULL,
    topic        VARCHAR,
    source_type  VARCHAR,
    sub_id       VARCHAR,
    result       VARCHAR DEFAULT 'ok',
    miss_rounds  INTEGER DEFAULT 0,
    ingested_count INTEGER DEFAULT 0,
    notes        VARCHAR,
    processed_at TIMESTAMP DEFAULT NOW()
);
CREATE UNIQUE INDEX idx_aii_needs_hash_source
    ON aii_processed_needs (need_hash, source_type);

CREATE TABLE source_subscriptions (
    id           VARCHAR PRIMARY KEY,
    user_id      VARCHAR,
    source_type  VARCHAR,
    name         VARCHAR,
    query_json   VARCHAR,
    max_results  INTEGER DEFAULT 5,
    status       VARCHAR DEFAULT 'active',
    scan_status  VARCHAR DEFAULT 'idle',
    ingested_count INTEGER DEFAULT 0,
    created_at   TIMESTAMP DEFAULT NOW()
);
"""


# ── DB fixture ─────────────────────────────────────────────────────────────────

@pytest.fixture
def g5_db(tmp_path):
    db_path = str(tmp_path / "g5_test.duckdb")
    conn = duckdb.connect(db_path)
    conn.execute(_DDL)
    conn.close()
    return db_path


@pytest.fixture
def g5_logs(tmp_path):
    return tmp_path / "feedback.log", tmp_path / "unresolved.log"


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────

def _make_get_conn(db_path: str):
    @contextmanager
    def _get_conn():
        conn = duckdb.connect(db_path)
        try:
            yield conn
        finally:
            conn.close()
    return _get_conn


def _make_runner(ingested_map: dict, db_path: str):
    """각 source_type 의 ingested_count 를 source_subscriptions 에 직접 기록. 网络边界替身."""
    async def runner(sub_id, user_id, source_type, query, max_results):
        count = ingested_map.get(source_type, 0)
        conn = duckdb.connect(db_path)
        conn.execute(
            "UPDATE source_subscriptions SET ingested_count=? WHERE id=?",
            (count, sub_id),
        )
        conn.close()
    return runner


def _db_rows(db_path: str) -> dict:
    """返回 {source_type: (miss_rounds, ingested_count, result)} 快照。"""
    conn = duckdb.connect(db_path)
    rows = conn.execute(
        "SELECT source_type, miss_rounds, ingested_count, result "
        "FROM aii_processed_needs ORDER BY source_type"
    ).fetchall()
    conn.close()
    return {r[0]: (r[1], r[2], r[3]) for r in rows}


def _run(need: dict, db_path: str, runner, feedback_log: Path, unresolved_log: Path,
         extra_patches: list | None = None):
    import stratum.services.aii_feedback_service as svc

    all_patches = [
        patch.object(svc, "get_conn",      _make_get_conn(db_path)),
        patch.object(svc, "FEEDBACK_LOG",  feedback_log),
        patch.object(svc, "UNRESOLVED_LOG", unresolved_log),
    ] + (extra_patches or [])

    with contextlib.ExitStack() as stack:
        for p in all_patches:
            stack.enter_context(p)
        asyncio.run(svc._process_one_need(need, "test_user", _runner=runner))


# ── 主测试：新逻辑（PASS 标准）────────────────────────────────────────────────

def test_g5_new_code_arxiv_independent_trigger(g5_db, g5_logs):
    """O1-O4 全部绿：arxiv 独立触发，gutenberg 不被污染。"""
    feedback_log, unresolved_log = g5_logs
    need = {"topic": "概率", "reason": ""}
    # gutenberg 每轮入库 2 篇，arxiv 每轮 0 篇
    runner = _make_runner({"gutenberg": 2, "arxiv": 0}, g5_db)

    # Round 1 → arxiv miss_rounds=1 (未达阈值)
    _run(need, g5_db, runner, feedback_log, unresolved_log)
    snap1 = _db_rows(g5_db)
    assert snap1.get("arxiv",  (None,))[0] == 1, f"Round1 arxiv miss_rounds should be 1, got {snap1}"
    assert snap1.get("gutenberg", (None,))[0] == 0, f"Round1 gutenberg miss_rounds should be 0"

    # 确保 Round 2 的 NOW() > Round 1（对照组 BUG 依赖时序）
    time.sleep(0.05)

    # Round 2 → arxiv miss_rounds=2 → needs_human_review + UNRESOLVED_LOG
    _run(need, g5_db, runner, feedback_log, unresolved_log)
    snap2 = _db_rows(g5_db)

    arx  = snap2.get("arxiv")
    gut  = snap2.get("gutenberg")
    unresolved_text = unresolved_log.read_text() if unresolved_log.exists() else ""

    # O1: arxiv → needs_human_review
    assert arx is not None, "arxiv row missing from DB"
    assert arx[2] == "needs_human_review", (
        f"O1 FAIL: arxiv result={arx[2]!r}, expected needs_human_review"
    )

    # O2: UNRESOLVED_LOG 写入
    assert "NEEDS-REVIEW" in unresolved_text or "ANTI-LOOP" in unresolved_text, (
        f"O2 FAIL: UNRESOLVED_LOG empty or missing keywords. content={unresolved_text!r}"
    )

    # O3: gutenberg 不触发
    assert gut is not None, "gutenberg row missing from DB"
    assert gut[2] != "needs_human_review", (
        f"O3 FAIL: gutenberg result={gut[2]!r}, should NOT be needs_human_review"
    )

    # O4: SUM(ingested_count) = 4 (gutenberg 2+2, arxiv 0+0)
    gut_cnt = gut[1] if gut else 0
    arx_cnt = arx[1] if arx else 0
    total   = gut_cnt + arx_cnt
    assert total == 4, f"O4 FAIL: SUM(ingested_count)={total}, expected 4 (gut={gut_cnt}, arx={arx_cnt})"


# ── 对照组：旧行为（miss_rounds 不按 source_type 过滤）────────────────────────

def _old_get_prev_miss_rounds(need_hash: str, source_type: str, db_path: str) -> int:
    """旧 SQL：ORDER BY processed_at DESC LIMIT 1，不过滤 source_type。"""
    conn = duckdb.connect(db_path)
    row = conn.execute(
        "SELECT miss_rounds FROM aii_processed_needs "
        "WHERE need_hash=? ORDER BY processed_at DESC LIMIT 1",
        (need_hash,)
    ).fetchone()
    conn.close()
    return row[0] if row else 0


def test_g5_old_code_arxiv_masked_by_gutenberg(g5_db, g5_logs):
    """对照组：旧 SQL 下 arxiv 被 gutenberg 掩盖，永不触发 needs_human_review。

    证明根治有效：仅当 _get_prev_miss_rounds 使用旧 SQL（混源 ORDER BY latest）时，
    gutenberg 的成功在 Round2 中把 arxiv 的 miss 重置为 1，永不达到阈值 2。
    """
    import stratum.services.aii_feedback_service as svc

    feedback_log, unresolved_log = g5_logs
    need  = {"topic": "概率", "reason": ""}
    runner = _make_runner({"gutenberg": 2, "arxiv": 0}, g5_db)

    # 用 db_path 捕获（闭包）构造旧行为 patch
    captured_db = g5_db

    def old_prev(need_hash: str, source_type: str) -> int:
        return _old_get_prev_miss_rounds(need_hash, source_type, captured_db)

    old_patch = patch.object(svc, "_get_prev_miss_rounds", old_prev)

    # Round 1（旧行为）
    _run(need, g5_db, runner, feedback_log, unresolved_log, extra_patches=[old_patch])
    time.sleep(0.05)   # 确保 Round2 的 NOW() > Round1 arxiv 的 processed_at

    # Round 2（旧行为）：gutenberg UPSERT 更新 processed_at=NOW()（最新），
    # 之后 arxiv 调 old_prev → ORDER BY DESC LIMIT 1 → gutenberg 行 → miss_rounds=0
    # → arxiv new miss_rounds = 0+1 = 1（应为 2，BUG）
    _run(need, g5_db, runner, feedback_log, unresolved_log, extra_patches=[old_patch])
    snap = _db_rows(g5_db)

    arx = snap.get("arxiv")
    gut = snap.get("gutenberg")

    # 旧代码：arxiv 不触发 needs_human_review（miss_rounds=1，未达阈值 2）
    assert arx is not None, "arxiv row missing"
    assert arx[2] != "needs_human_review", (
        f"CONTRAST FAIL: old code unexpectedly triggered needs_human_review for arxiv. "
        f"If this fails, the bug was already fixed before this patch — recheck test setup."
    )
    assert arx[0] == 1, (
        f"CONTRAST: arxiv miss_rounds should stay 1 under old code, got {arx[0]}. "
        "Timing issue: gutenberg processed_at must be > arxiv's Round1 processed_at."
    )
    # gutenberg 正常
    assert gut is not None
    assert gut[0] == 0, f"gutenberg miss_rounds should be 0, got {gut[0]}"
