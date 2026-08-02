"""Flashcards: SM-2 调度 (纯函数) + 服务/路由 (真实 PG).

Coverage:
  1-5.   spaced_repetition.schedule_review — again/hard/good/easy 的确定性行为
  6.     generate_cards — note 来源, 标题 fallback 出卡 (无 LLM)
  7.     generate_cards — substrate 越权 → []
  8.     generate_cards — 内容太短 → []
  9.     review 后 due_at 推进 + 状态更新
  10.    review 越权 → 404
  11.    list due_only 过滤
  12.    delete + 越权 delete 404
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-for-sl-unit-tests-32x")

from datetime import datetime, timedelta, timezone

from stratum.common import create_token  # noqa: E402
from stratum.services.spaced_repetition import ReviewState, schedule_review  # noqa: E402


def _auth(uid: str = "user-alice") -> dict:
    return {"Authorization": f"Bearer {create_token(uid)}"}


@pytest.fixture()
def client():
    from stratum.api.main import app

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture(autouse=True)
def _clean_cards():
    from stratum.db import execute

    execute("DELETE FROM flashcards WHERE user_id IN ('user-alice', 'user-bob')")
    yield


# ═══════════════════════════════════════════════════════════════════════════════
# SM-2 调度 (纯函数)
# ═══════════════════════════════════════════════════════════════════════════════

_NOW = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)


def test_again_resets_and_short_due():
    st, due = schedule_review(ReviewState(repetitions=5, easiness=2.5, interval_days=30.0), "again", _NOW)
    assert st.repetitions == 0
    assert st.interval_days == 0
    assert st.easiness == pytest.approx(2.3)
    assert due == _NOW + timedelta(minutes=10)


def test_hard_slow_growth():
    st, due = schedule_review(ReviewState(repetitions=2, easiness=2.5, interval_days=6.0), "hard", _NOW)
    assert st.repetitions == 3
    assert st.easiness == pytest.approx(2.35)
    assert st.interval_days == pytest.approx(7.2)
    assert due == _NOW + timedelta(days=7.2)


def test_good_sm2_sequence():
    s1, _ = schedule_review(ReviewState(), "good", _NOW)
    assert s1.interval_days == 1.0 and s1.repetitions == 1
    s2, _ = schedule_review(s1, "good", _NOW)
    assert s2.interval_days == 6.0 and s2.repetitions == 2
    s3, d3 = schedule_review(s2, "good", _NOW)
    assert s3.interval_days == 15.0  # 6 × 2.5
    assert d3 == _NOW + timedelta(days=15.0)


def test_easy_faster_growth():
    st, _ = schedule_review(ReviewState(), "easy", _NOW)
    assert st.interval_days == 4.0
    assert st.easiness == pytest.approx(2.65)


def test_invalid_rating_raises():
    with pytest.raises(ValueError):
        schedule_review(ReviewState(), "wrong", _NOW)


# ═══════════════════════════════════════════════════════════════════════════════
# 服务层 (真实 PG)
# ═══════════════════════════════════════════════════════════════════════════════

_MD = """# 边际效用递减

在经济学中, 边际效用递减指每增加一单位消费带来的效用增量递减。

## 沉没成本

沉没成本是已发生且无法收回的成本, 理性决策不应考虑。

# 机会成本

机会成本是为选择某一方案而放弃的最佳替代方案的价值。
"""


def _insert_note(title: str, content: str, uid: str = "user-alice") -> str:
    from stratum.common import generate_ulid
    from stratum.db import insert

    nid = generate_ulid()
    insert("notes_sl", {"id": nid, "user_id": uid, "title": title, "content_markdown": content})
    return nid


def test_generate_cards_from_note_heading_fallback(client):
    nid = _insert_note("经济学笔记", _MD)
    r = client.post("/api/v1/flashcards/generate", headers=_auth(), json={"source_kind": "note", "source_id": nid})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["generated"] == 3, body  # 三个标题
    fronts = {c["front"] for c in body["cards"]}
    assert "边际效用递减" in fronts
    card = body["cards"][0]
    assert card["user_id"] == "user-alice"
    assert "效用增量" in card["back"]


def test_generate_cards_too_short_returns_empty(client):
    nid = _insert_note("短笔记", "太短了。")
    r = client.post("/api/v1/flashcards/generate", headers=_auth(), json={"source_kind": "note", "source_id": nid})
    assert r.status_code == 200
    assert r.json()["generated"] == 0


def test_generate_cards_cross_user_source_404_empty(client):
    nid = _insert_note("别人的笔记", _MD, uid="user-bob")
    r = client.post("/api/v1/flashcards/generate", headers=_auth("user-alice"), json={"source_kind": "note", "source_id": nid})
    assert r.status_code == 200
    assert r.json()["generated"] == 0  # 越权 → 静默空, 不泄露存在性


def test_generate_unknown_kind_422(client):
    r = client.post("/api/v1/flashcards/generate", headers=_auth(), json={"source_kind": "paper", "source_id": "x"})
    assert r.status_code == 422  # pydantic pattern 校验


def _gen_cards(client, nid: str) -> list[dict]:
    r = client.post("/api/v1/flashcards/generate", headers=_auth(), json={"source_kind": "note", "source_id": nid})
    return r.json()["cards"]


def test_review_advances_due(client):
    nid = _insert_note("复习笔记", _MD)
    cards = _gen_cards(client, nid)
    cid = cards[0]["id"]
    r = client.post(f"/api/v1/flashcards/{cid}/review", headers=_auth(), json={"rating": "good"})
    assert r.status_code == 200
    updated = r.json()
    assert updated["repetitions"] == 1
    assert updated["interval_days"] == 1.0
    assert updated["due_at"] > cards[0]["due_at"]


def test_review_cross_user_404(client):
    nid = _insert_note("我的卡", _MD)
    cid = _gen_cards(client, nid)[0]["id"]
    r = client.post(f"/api/v1/flashcards/{cid}/review", headers=_auth("user-bob"), json={"rating": "good"})
    assert r.status_code == 404


def test_list_due_only_filter(client):
    nid = _insert_note("到期过滤", _MD)
    cards = _gen_cards(client, nid)
    r = client.post(f"/api/v1/flashcards/{cards[0]['id']}/review", headers=_auth(), json={"rating": "good"})
    assert r.status_code == 200  # 这张不再 due (1 天后)
    r2 = client.get("/api/v1/flashcards?due_only=true", headers=_auth())
    due_ids = {c["id"] for c in r2.json()}
    assert cards[0]["id"] not in due_ids
    assert all(c["id"] in due_ids for c in cards[1:])


def test_due_stats(client):
    nid = _insert_note("统计", _MD)
    _gen_cards(client, nid)
    r = client.get("/api/v1/flashcards/due", headers=_auth())
    assert r.status_code == 200
    assert r.json()["due_count"] == 3


def test_delete_and_cross_user_404(client):
    nid = _insert_note("删除测试", _MD)
    cid = _gen_cards(client, nid)[0]["id"]
    r = client.delete(f"/api/v1/flashcards/{cid}", headers=_auth("user-bob"))
    assert r.status_code == 404
    r = client.delete(f"/api/v1/flashcards/{cid}", headers=_auth())
    assert r.status_code == 200
    r2 = client.get("/api/v1/flashcards", headers=_auth())
    assert all(c["id"] != cid for c in r2.json())
