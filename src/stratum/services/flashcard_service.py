"""闪卡服务: 从 substrate / note 生成问答卡 + 复习调度落库.

生成两档:
1. LLM (oprim.llm.llm_call, 镜像内可用) — 高价值 Q/A
2. 确定性 fallback — Markdown 标题 → "解释 <标题>" 卡 (无 LLM 也可跑, 可测试)

复习: services/spaced_repetition.schedule_review (SM-2)。
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from stratum.common import generate_ulid, now_utc
from stratum.db import execute, insert, query, read, update
from stratum.services.spaced_repetition import RATINGS, ReviewState, schedule_review

log = logging.getLogger(__name__)

SOURCE_KINDS = ("substrate", "note")

_MAX_CARDS = 50
_FALLBACK_MIN_TEXT = 100  # 内容太短不值得出卡


# ── 内容取回 ──────────────────────────────────────────────────────────────────


def _source_text(user_id: str, source_kind: str, source_id: str) -> tuple[str, str] | None:
    """返回 (title, text)。越权或找不到返回 None。"""
    if source_kind == "note":
        row = read("notes_sl", source_id)
        if not row or row.get("user_id") != user_id:
            return None
        return (row.get("title") or source_id, row.get("content_markdown") or "")
    if source_kind == "substrate":
        rows = query(
            "SELECT content FROM derivative WHERE substrate_id = %(sid)s "
            "AND kind = 'markdown' ORDER BY seq",
            {"sid": source_id},
        )
        sub = read("substrates", source_id)
        if not sub or sub.get("user_id") != user_id:
            return None
        text = "\n\n".join(r.get("content") or "" for r in rows)
        return (sub.get("title") or source_id, text)
    return None


# ── 生成 ──────────────────────────────────────────────────────────────────────


def generate_cards(
    user_id: str, source_kind: str, source_id: str, max_cards: int = 12
) -> list[dict[str, Any]]:
    """为来源生成闪卡并落库。返回新插入的卡片列表。"""
    if source_kind not in SOURCE_KINDS:
        raise ValueError(f"source_kind must be one of {SOURCE_KINDS}")
    max_cards = min(max_cards, _MAX_CARDS)

    found = _source_text(user_id, source_kind, source_id)
    if not found:
        return []
    title, text = found
    if len(text.strip()) < _FALLBACK_MIN_TEXT:
        return []

    pairs = _llm_cards(text, max_cards) or _fallback_cards(text, max_cards)
    if not pairs:
        return []

    created = []
    for front, back in pairs:
        cid = generate_ulid()
        row = {
            "id": cid,
            "user_id": user_id,
            "source_kind": source_kind,
            "source_id": source_id,
            "source_title": title,
            "front": front,
            "back": back,
            "tags": [],
            "repetitions": 0,
            "easiness": 2.5,
            "interval_days": 0,
            "due_at": now_utc(),
        }
        insert("flashcards", row)
        created.append(row)
    log.info("flashcards generated user=%s kind=%s source=%s n=%d", user_id, source_kind, source_id, len(created))
    return created


def _llm_cards(text: str, max_cards: int) -> list[tuple[str, str]] | None:
    """LLM 生成 Q/A。返回 None 表示不可用/失败 → 调用方走 fallback。"""
    try:
        from oprim.llm import llm_call
    except Exception:
        return None
    snippet = text[:6000]
    prompt = (
        "你是知识库闪卡制作者。从下面的材料提炼出最有价值的问答卡。\n"
        "要求: 1) 问题具体、答案自包含(不依赖上下文) 2) 覆盖定义/定理/概念/要点 3) 不要问过于琐碎的事实\n"
        f"输出 JSON 数组, 每项 {{\"front\": \"问题\", \"back\": \"答案\"}}, 最多 {max_cards} 条。\n\n材料:\n{snippet}"
    )
    try:
        raw = llm_call(prompt=prompt)
        payload = raw if isinstance(raw, (list, dict)) else json.loads(str(raw))
        items = payload if isinstance(payload, list) else payload.get("cards", [])
        pairs = []
        for it in items[:max_cards]:
            front = str(it.get("front") or it.get("question") or "").strip()
            back = str(it.get("back") or it.get("answer") or "").strip()
            if front and back:
                pairs.append((front[:500], back[:2000]))
        return pairs or None
    except Exception as e:
        log.warning("flashcard llm generation failed, fallback to headings: %s", e)
        return None


_HEADING_RE = re.compile(r"^#{1,4}\s+(.+)$")


def _fallback_cards(text: str, max_cards: int) -> list[tuple[str, str]]:
    """确定性 fallback: 每个 Markdown 标题 → 「解释 <标题>」卡, 答案为紧随段落。"""
    cards: list[tuple[str, str]] = []
    current_heading: str | None = None
    buffer: list[str] = []
    seen: set[str] = set()

    def flush() -> None:
        nonlocal current_heading, buffer
        if current_heading and buffer:
            back = " ".join(buffer).strip()
            if len(back) >= 20 and current_heading not in seen:
                seen.add(current_heading)
                cards.append((current_heading, back[:2000]))
        current_heading = None
        buffer = []

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        m = _HEADING_RE.match(stripped)
        if m and len(cards) < max_cards:
            flush()
            current_heading = m.group(1).strip()[:200]
        elif current_heading is not None:
            buffer.append(re.sub(r"\s+", " ", stripped)[:300])
            if len(" ".join(buffer)) > 400:
                flush()
    flush()
    if not cards:
        # 无标题结构 → 按句子分块做 cloze 卡
        sentences = [s for s in re.split(r"(?<=[。.!?])\s+", text) if len(s) > 30][:max_cards]
        cards = [
            ("判断对错: " + s[:120] + ("…" if len(s) > 120 else ""), s[:2000])
            for s in sentences
        ]
    return cards[:max_cards]


# ── 查询 / 复习 ───────────────────────────────────────────────────────────────


def list_cards(user_id: str, due_only: bool = False, limit: int = 50) -> list[dict]:
    where = "user_id = %(uid)s"
    params: dict[str, Any] = {"uid": user_id, "limit": limit}
    if due_only:
        where += " AND due_at <= now()"
    return query(
        f"SELECT * FROM flashcards WHERE {where} ORDER BY due_at ASC LIMIT %(limit)s",
        params,
    )


def due_stats(user_id: str) -> dict:
    row = query(
        "SELECT count(*) AS n, min(due_at) AS next_due FROM flashcards "
        "WHERE user_id = %(uid)s AND due_at <= now()",
        {"uid": user_id},
        limit=1,
    )
    r = row[0] if row else {}
    return {"due_count": r.get("n", 0), "next_due": r.get("next_due")}


def review_card(user_id: str, card_id: str, rating: str) -> dict | None:
    """应用评级, 返回更新后的卡片。越权/不存在返回 None。"""
    if rating not in RATINGS:
        raise ValueError(f"rating must be one of {RATINGS}")
    card = read("flashcards", card_id)
    if not card or card.get("user_id") != user_id:
        return None

    state = ReviewState(
        repetitions=card.get("repetitions") or 0,
        easiness=float(card.get("easiness") or 2.5),
        interval_days=float(card.get("interval_days") or 0.0),
    )
    new_state, due = schedule_review(state, rating)
    update(
        "flashcards",
        card_id,
        {
            "repetitions": new_state.repetitions,
            "easiness": new_state.easiness,
            "interval_days": new_state.interval_days,
            "due_at": due.isoformat(),
            "updated_at": now_utc(),
        },
    )
    updated = read("flashcards", card_id)
    return updated


def delete_card(user_id: str, card_id: str) -> bool:
    existing = read("flashcards", card_id)
    if not existing or existing.get("user_id") != user_id:
        return False
    execute("DELETE FROM flashcards WHERE id = %(cid)s AND user_id = %(uid)s", {"cid": card_id, "uid": user_id})
    return True
