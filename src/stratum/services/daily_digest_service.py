"""Simple daily digest — recent notes/substrates + lint snapshot → notes_sl + notification.

Does not require omodul daily_digest_workflow (optional enhancement later).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from stratum.common import generate_ulid, now_utc
from stratum.db import insert, query, update
from stratum.services.knowledge_lint_service import run_lint
from stratum.utils.user_id_hash import hash_user_id


def build_daily_digest(user_id: str, *, days: int = 1, notify: bool = True) -> dict[str, Any]:
    uh = hash_user_id(user_id)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    since = datetime.now(timezone.utc) - timedelta(days=max(1, days))

    notes = query(
        "SELECT id, title, updated_at FROM notes_sl "
        "WHERE user_id = %(uid)s AND deleted_at IS NULL "
        "AND updated_at >= %(since)s "
        "ORDER BY updated_at DESC LIMIT 30",
        {"uid": user_id, "since": since},
    )
    substrates = query(
        "SELECT id, title, created_at FROM substrates "
        "WHERE (user_id = %(uh)s OR user_id = %(uid)s) "
        "AND created_at >= %(since)s "
        "ORDER BY created_at DESC LIMIT 30",
        {"uh": uh, "uid": user_id, "since": since},
    )

    lint = run_lint(user_id, write_report=False)
    summary = lint.get("summary") or {}

    title = f"日报 · {day}"
    lines = [
        f"# {title}",
        "",
        f"_window: last {days} day(s) · {datetime.now(timezone.utc).isoformat()}_",
        "",
        "## 知识健康",
        "",
        f"- 断链: {summary.get('broken_wikilinks', 0)}",
        f"- 孤立页: {summary.get('orphans', 0)}",
        f"- 待裁决矛盾: {summary.get('contradictions_pending', 0)}",
        f"- 扫描笔记: {summary.get('notes_scanned', 0)}",
        "",
        "## 最近更新的笔记",
        "",
    ]
    for n in notes:
        lines.append(f"- [[{n['id']}|{n.get('title') or n['id']}]]")
    if not notes:
        lines.append("_无_")
    lines += ["", "## 新入库资料", ""]
    for s in substrates:
        lines.append(f"- [{s.get('title') or s['id']}](substrate://{s['id']})")
    if not substrates:
        lines.append("_无_")

    if summary.get("contradictions_pending"):
        lines += ["", "## 建议处理", "", "- 打开含 `pending_human_review` 的概念页完成裁决"]

    body = "\n".join(lines) + "\n"

    existing = query(
        "SELECT id FROM notes_sl WHERE user_id = %(uid)s AND title = %(t)s "
        "AND deleted_at IS NULL LIMIT 1",
        {"uid": user_id, "t": title},
    )
    if existing:
        note_id = existing[0]["id"]
        update(
            "notes_sl",
            note_id,
            {"content_markdown": body, "updated_at": now_utc()},
        )
    else:
        note_id = generate_ulid()
        fm = (
            f"---\nid: {note_id}\ntype: daily_digest\ntitle: {title}\n"
            f"aliases: []\nsources: []\nupdated: {day}\n---\n\n"
        )
        insert(
            "notes_sl",
            {
                "id": note_id,
                "user_id": user_id,
                "title": title,
                "content_markdown": fm + body,
                "substrate_refs": [s["id"] for s in substrates[:20]],
                "concept_refs": [],
                "content_refs": [],
                "created_at": now_utc(),
                "updated_at": now_utc(),
            },
        )

    if notify:
        try:
            insert(
                "changefeed",
                {
                    "event_id": generate_ulid(),
                    "user_id": user_id,
                    "device_id": "server",
                    "event_type": "notification",
                    "payload": {
                        "title": title,
                        "body": (
                            f"更新笔记 {len(notes)} · 新资料 {len(substrates)} · "
                            f"矛盾 {summary.get('contradictions_pending', 0)}"
                        ),
                        "channels": ["web"],
                        "note_id": note_id,
                    },
                },
            )
        except Exception:
            pass

    return {
        "status": "ok",
        "note_id": note_id,
        "title": title,
        "notes_updated": len(notes),
        "substrates_new": len(substrates),
        "lint_summary": summary,
    }
