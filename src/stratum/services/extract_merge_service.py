"""Extract + Link&Merge for MVP knowledge growth.

After ingest: pull markdown derivative → LLM extract entities →
  upsert graph_entities (with source anchors) and
  append to concept knowledge notes (notes_sl) instead of only isolated graphs.

Does NOT overwrite original substrate content.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from stratum.common import generate_ulid, now_utc
from stratum.dao.graph import upsert_entity, upsert_relation
from stratum.db import get_conn, insert, query, update

log = logging.getLogger(__name__)

_EXTRACT_PROMPT = """从以下文本抽取知识条目。只输出 JSON，不要 markdown 围栏。
{
  "entities": [
    {"name": "名称", "type": "concept|person|company|project|theme", "description": "一句话", "aliases": []}
  ],
  "judgments": [
    {"claim": "判断/观点", "anchor": "原文短句摘录"}
  ],
  "todos": ["可执行待办"]
}
规则: name 尽量规范; description 忠实原文; anchor 必须是文中短句。

文本:
"""


def _llm_json(prompt: str) -> dict:
    try:
        from obase import ProviderRegistry as _PR

        caller = _PR.get().llm("qwen3")
        raw = caller(messages=[{"role": "user", "content": prompt}], max_tokens=1200)
        text = (raw if isinstance(raw, str) else str(raw)).strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            return json.loads(m.group(0))
    except Exception as e:
        log.warning("extract_merge llm failed: %s", e)
    return {}


def _get_markdown(substrate_id: str) -> tuple[str, str]:
    """Return (title, markdown_content)."""
    with get_conn() as conn:
        s = conn.execute(
            "SELECT title FROM substrates WHERE id=?", (substrate_id,)
        ).fetchone()
        title = (s[0] if s else None) or substrate_id
        row = conn.execute(
            "SELECT content FROM derivative WHERE substrate_id=? AND kind='markdown' "
            "AND content IS NOT NULL AND content<>'' ORDER BY seq LIMIT 1",
            (substrate_id,),
        ).fetchone()
        if row and row[0]:
            return title, row[0]
        # fallback: any translation_zh or plaintext-ish
        row2 = conn.execute(
            "SELECT content FROM derivative WHERE substrate_id=? "
            "AND content IS NOT NULL AND content<>'' ORDER BY "
            "CASE WHEN kind LIKE 'translation%zh%' THEN 0 WHEN kind='markdown' THEN 1 ELSE 2 END "
            "LIMIT 1",
            (substrate_id,),
        ).fetchone()
        return title, (row2[0] if row2 else "") or ""


_NEG_MARKERS = re.compile(
    r"(不|并非|相反|否定|错误|failed|not\b|never\b|contrary|opposite|incorrect|false\b)",
    re.I,
)


def _looks_contradictory(old_desc: str, new_desc: str) -> bool:
    """Lightweight contradiction heuristic (no extra LLM).

    Flags when both sides have content, low token overlap, and polarity markers differ.
    """
    a = (old_desc or "").strip()
    b = (new_desc or "").strip()
    if len(a) < 8 or len(b) < 8:
        return False
    if a == b or a in b or b in a:
        return False
    ta = set(re.findall(r"[\w\u4e00-\u9fff]{2,}", a.lower()))
    tb = set(re.findall(r"[\w\u4e00-\u9fff]{2,}", b.lower()))
    if not ta or not tb:
        return False
    overlap = len(ta & tb) / max(1, len(ta | tb))
    if overlap > 0.45:
        return False
    # polarity mismatch or explicit negation in one side only
    na, nb = bool(_NEG_MARKERS.search(a)), bool(_NEG_MARKERS.search(b))
    return na != nb or overlap < 0.2


def _existing_entity_desc(user_id_hash: str, name: str) -> str:
    rows = query(
        "SELECT description FROM graph_entities "
        "WHERE user_id=%(uh)s AND LOWER(TRIM(name))=LOWER(TRIM(%(name)s)) LIMIT 1",
        {"uh": user_id_hash, "name": name},
    )
    if rows:
        return rows[0].get("description") or ""
    return ""


def _append_concept_note(
    user_id: str,
    *,
    name: str,
    entity_type: str,
    description: str,
    source_title: str,
    substrate_id: str,
    anchor: str = "",
    contradiction: bool = False,
    prior_desc: str = "",
) -> str:
    """Find existing note by title/alias or create; append a dated source block."""
    rows = query(
        "SELECT id, title, content_markdown FROM notes_sl "
        "WHERE user_id=%(uid)s AND deleted_at IS NULL "
        "AND (title=%(name)s OR content_markdown LIKE %(pat)s) "
        "ORDER BY updated_at DESC LIMIT 1",
        {"uid": user_id, "name": name, "pat": f"%aliases: %{name}%"},
    )
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    block = (
        f"\n\n## 来源补充 · {ts}\n\n"
        f"- **来源**: [{source_title}](substrate://{substrate_id})\n"
        f"- **类型**: {entity_type}\n"
        f"- **摘要**: {description}\n"
    )
    if anchor:
        block += f"- **原文锚点**: 「{anchor[:200]}」\n"
    if contradiction:
        block += (
            f"\n### ⚠ 矛盾 / 待裁决\n\n"
            f"- **既有表述**: {prior_desc[:300]}\n"
            f"- **新资料表述**: {description[:300]}\n"
            f"- **状态**: pending_human_review\n"
            f"- **substrate**: {substrate_id}\n"
        )

    if rows:
        note_id = rows[0]["id"]
        old = rows[0].get("content_markdown") or ""
        # Idempotent: skip if this substrate already appended
        if substrate_id in old:
            return note_id
        update(
            "notes_sl",
            note_id,
            {"content_markdown": old + block, "updated_at": now_utc()},
        )
        return note_id

    note_id = generate_ulid()
    front = (
        f"---\n"
        f"id: {note_id}\n"
        f"type: {entity_type}\n"
        f"title: {name}\n"
        f"aliases: []\n"
        f"sources: [{substrate_id}]\n"
        f"updated: {ts}\n"
        f"---\n\n"
        f"# {name}\n\n"
        f"{description}\n"
    )
    insert(
        "notes_sl",
        {
            "id": note_id,
            "user_id": user_id,
            "title": name,
            "content_markdown": front + block,
            "substrate_refs": [substrate_id],
            "concept_refs": [],
            "content_refs": [],
            "created_at": now_utc(),
            "updated_at": now_utc(),
        },
    )
    return note_id


async def extract_and_merge(
    substrate_id: str,
    user_id: str,
    user_id_hash: str | None = None,
) -> dict[str, Any]:
    """Run extract + merge for one substrate. Safe to call multiple times (idempotent append)."""
    from stratum.utils.user_id_hash import hash_user_id

    uh = user_id_hash or hash_user_id(user_id)
    title, content = _get_markdown(substrate_id)
    if not content or len(content.strip()) < 40:
        return {
            "status": "skipped",
            "reason": "no_markdown_content",
            "substrate_id": substrate_id,
            "entities": 0,
            "notes_updated": 0,
        }

    # Cap LLM cost
    chunk = content[:3500]
    data = _llm_json(_EXTRACT_PROMPT + chunk)
    entities = data.get("entities") or []
    judgments = data.get("judgments") or []

    entities_n = 0
    notes_n = 0
    contradictions_n = 0
    name_to_id: dict[str, str] = {}

    for ent in entities[:25]:
        name = (ent.get("name") or "").strip()
        if not name:
            continue
        etype = (ent.get("type") or "concept").strip().lower()
        if etype not in ("concept", "person", "company", "project", "theme", "method", "system"):
            etype = "concept"
        desc = (ent.get("description") or "")[:300]
        prior = _existing_entity_desc(uh, name)
        is_contra = _looks_contradictory(prior, desc) if prior else False
        if is_contra:
            contradictions_n += 1
        try:
            eid = upsert_entity(
                user_id=uh,
                name=name,
                entity_type=etype,
                description=desc,
                substrate_id=substrate_id,
            )
            name_to_id[name] = eid
            entities_n += 1
        except Exception as e:
            log.warning("upsert_entity failed name=%s: %s", name, e)
            continue

        # Link & Merge → concept note page (+ contradiction block when needed)
        anchor = ""
        for j in judgments:
            if name in (j.get("claim") or "") or name in (j.get("anchor") or ""):
                anchor = j.get("anchor") or ""
                break
        try:
            _append_concept_note(
                user_id,
                name=name,
                entity_type=etype,
                description=desc or name,
                source_title=title,
                substrate_id=substrate_id,
                anchor=anchor,
                contradiction=is_contra,
                prior_desc=prior,
            )
            notes_n += 1
        except Exception as e:
            log.warning("append_concept_note failed name=%s: %s", name, e)

    # Simple co-occurrence edges between first N entities
    names = list(name_to_id.keys())[:8]
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            try:
                upsert_relation(
                    user_id=uh,
                    source_id=name_to_id[a],
                    target_id=name_to_id[b],
                    relation_type="related_to",
                    description=f"co-mentioned in {title}",
                    substrate_id=substrate_id,
                )
            except Exception:
                pass

    return {
        "status": "ok",
        "substrate_id": substrate_id,
        "entities": entities_n,
        "notes_updated": notes_n,
        "contradictions": contradictions_n,
        "judgments": len(judgments),
    }
