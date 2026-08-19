"""Knowledge lint — orphan notes, broken wikilinks, pending contradictions.

MVP lightweight (no LLM). Results can be written as a notes_sl report page
and/or returned as JSON for the lint_bot agent wrapper.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from stratum.common import generate_ulid, now_utc
from stratum.db import insert, query, read, update
from stratum.utils.user_id_hash import hash_user_id

_WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")
_CONTRA_MARKER = "pending_human_review"


def run_lint(user_id: str, *, write_report: bool = True) -> dict[str, Any]:
    uh = hash_user_id(user_id)
    notes = query(
        "SELECT id, title, content_markdown, substrate_refs, updated_at "
        "FROM notes_sl WHERE user_id = %(uid)s AND deleted_at IS NULL",
        {"uid": user_id},
    )
    note_ids = {n["id"] for n in notes}
    note_titles = {(n.get("title") or "").strip().lower(): n["id"] for n in notes if n.get("title")}

    broken_links: list[dict] = []
    orphans: list[dict] = []
    contradictions: list[dict] = []
    empty_notes: list[dict] = []

    # all note ids that appear as targets of wikilinks
    linked_to: set[str] = set()

    for n in notes:
        body = n.get("content_markdown") or ""
        title = n.get("title") or n["id"]
        if len(body.strip()) < 20:
            empty_notes.append({"id": n["id"], "title": title})

        if _CONTRA_MARKER in body or "矛盾 / 待裁决" in body or "⚠ 矛盾" in body:
            contradictions.append({"id": n["id"], "title": title})

        for m in _WIKILINK.finditer(body):
            target = m.group(1).strip()
            # strip alias [[id|label]]
            target = target.split("|", 1)[0].strip()
            if not target:
                continue
            if target in note_ids:
                linked_to.add(target)
                continue
            tid = note_titles.get(target.lower())
            if tid:
                linked_to.add(tid)
                continue
            broken_links.append(
                {
                    "from_id": n["id"],
                    "from_title": title,
                    "target": target,
                }
            )

    for n in notes:
        nid = n["id"]
        title = n.get("title") or nid
        body = n.get("content_markdown") or ""
        # skip system reports
        if title.startswith("Lint 报告") or title.startswith("日报"):
            continue
        refs = n.get("substrate_refs") or []
        has_out = bool(_WIKILINK.search(body)) or bool(refs)
        has_in = nid in linked_to
        if not has_out and not has_in and "来源补充" not in body:
            orphans.append({"id": nid, "title": title})

    # entities with zero source substrates
    lonely_entities = []
    try:
        ents = query(
            "SELECT id, name, source_substrate_ids, mention_count FROM graph_entities "
            "WHERE user_id = %(uh)s ORDER BY mention_count DESC NULLS LAST LIMIT 500",
            {"uh": uh},
        )
        for e in ents:
            sids = e.get("source_substrate_ids") or []
            if isinstance(sids, str):
                import json

                try:
                    sids = json.loads(sids)
                except Exception:
                    sids = []
            if not sids:
                lonely_entities.append({"id": e["id"], "name": e.get("name")})
    except Exception:
        pass

    summary = {
        "notes_scanned": len(notes),
        "broken_wikilinks": len(broken_links),
        "orphans": len(orphans),
        "contradictions_pending": len(contradictions),
        "empty_notes": len(empty_notes),
        "lonely_entities": len(lonely_entities),
    }

    report_id = None
    if write_report:
        report_id = _write_lint_report(
            user_id,
            summary,
            broken_links[:50],
            orphans[:50],
            contradictions[:50],
            empty_notes[:30],
            lonely_entities[:30],
        )

    return {
        "status": "ok",
        "summary": summary,
        "broken_wikilinks": broken_links[:50],
        "orphans": orphans[:50],
        "contradictions": contradictions[:50],
        "empty_notes": empty_notes[:30],
        "lonely_entities": lonely_entities[:30],
        "report_note_id": report_id,
    }


def _write_lint_report(
    user_id: str,
    summary: dict,
    broken,
    orphans,
    contradictions,
    empty_notes,
    lonely_entities,
) -> str:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    title = f"Lint 报告 · {day}"
    lines = [
        f"# {title}",
        "",
        f"_generated: {datetime.now(timezone.utc).isoformat()}_",
        "",
        "## 摘要",
        "",
        f"- 扫描笔记: {summary['notes_scanned']}",
        f"- 断链 wikilink: {summary['broken_wikilinks']}",
        f"- 孤立页: {summary['orphans']}",
        f"- 待裁决矛盾: {summary['contradictions_pending']}",
        f"- 过短笔记: {summary['empty_notes']}",
        f"- 无来源实体: {summary['lonely_entities']}",
        "",
        "## 断链",
        "",
    ]
    for b in broken:
        lines.append(f"- [[{b['from_id']}|{b['from_title']}]] → `[[{b['target']}]]`")
    if not broken:
        lines.append("_无_")
    lines += ["", "## 孤立页", ""]
    for o in orphans:
        lines.append(f"- [[{o['id']}|{o['title']}]]")
    if not orphans:
        lines.append("_无_")
    lines += ["", "## 待裁决矛盾", ""]
    for c in contradictions:
        lines.append(f"- [[{c['id']}|{c['title']}]]")
    if not contradictions:
        lines.append("_无_")
    lines += ["", "## 过短笔记", ""]
    for e in empty_notes:
        lines.append(f"- [[{e['id']}|{e['title']}]]")
    body = "\n".join(lines) + "\n"

    # upsert same-day report by title
    existing = query(
        "SELECT id FROM notes_sl WHERE user_id = %(uid)s AND title = %(t)s "
        "AND deleted_at IS NULL LIMIT 1",
        {"uid": user_id, "t": title},
    )
    if existing:
        rid = existing[0]["id"]
        update(
            "notes_sl",
            rid,
            {"content_markdown": body, "updated_at": now_utc()},
        )
        return rid

    rid = generate_ulid()
    fm = (
        f"---\nid: {rid}\ntype: lint_report\ntitle: {title}\n"
        f"aliases: []\nsources: []\nupdated: {day}\n---\n\n"
    )
    insert(
        "notes_sl",
        {
            "id": rid,
            "user_id": user_id,
            "title": title,
            "content_markdown": fm + body,
            "substrate_refs": [],
            "concept_refs": [],
            "content_refs": [],
            "created_at": now_utc(),
            "updated_at": now_utc(),
        },
    )
    return rid
