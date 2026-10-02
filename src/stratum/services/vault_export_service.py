"""整库 Markdown 导出 — 可迁移知识库文件夹 (MVP 验收 #4).

布局:
  vault/
    README.md
    notes/          # 人类笔记 + 概念生长页 (notes_sl)
    concepts/       # graph_entities 摘要页
    sources/        # substrate 原文 markdown derivative
    evidence/       # W3C-style Evidence JSON (highlights)
    learning/       # FSRS cards + user review settings
    manifest.json   # versioned machine-readable manifest
    index.json      # 清单 + 统计

YAML frontmatter 规范 (MVP):
  id, type, title, aliases, sources, updated
"""

from __future__ import annotations

import io
import json
import logging
import re
import zipfile
from datetime import datetime, timezone
from typing import Any

from stratum.db import query
from stratum.utils.user_id_hash import hash_user_id

log = logging.getLogger(__name__)

_SAFE = re.compile(r"[^\w\u4e00-\u9fff\-]+")


def _slug(title: str, fallback: str) -> str:
    t = (title or "").strip() or fallback
    t = _SAFE.sub("-", t).strip("-")[:80]
    return t or fallback


def _yaml_escape(s: str) -> str:
    s = (s or "").replace("\\", "\\\\").replace('"', '\\"')
    if any(c in s for c in ":#{}[],&*?|>!%@`'\"\n"):
        return f'"{s}"'
    return s


def _frontmatter(
    *,
    id: str,
    type_: str,
    title: str,
    aliases: list[str] | None = None,
    sources: list[str] | None = None,
    updated: str | None = None,
    extra: dict | None = None,
) -> str:
    lines = [
        "---",
        f"id: {id}",
        f"type: {type_}",
        f"title: {_yaml_escape(title)}",
        f"aliases: {json.dumps(aliases or [], ensure_ascii=False)}",
        f"sources: {json.dumps(sources or [], ensure_ascii=False)}",
        f"updated: {updated or datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
    ]
    for k, v in (extra or {}).items():
        if isinstance(v, (list, dict)):
            lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
        else:
            lines.append(f"{k}: {_yaml_escape(str(v))}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def _ensure_body_has_title(title: str, body: str) -> str:
    body = (body or "").strip()
    if body.startswith("#"):
        return body + "\n"
    return f"# {title}\n\n{body}\n"


def _json_value(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return fallback
    return value


def _iso_value(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def build_vault_files(user_id: str) -> dict[str, str]:
    """Return path→content map for the vault (relative paths)."""
    uid_hash = hash_user_id(user_id)
    files: dict[str, str] = {}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # --- notes_sl ---
    notes = query(
        """
        SELECT id, title, content_markdown, substrate_refs, created_at, updated_at
        FROM notes_sl
        WHERE user_id = %(uid)s AND deleted_at IS NULL
        ORDER BY updated_at DESC NULLS LAST
        """,
        {"uid": user_id},
    )
    note_index = []
    for n in notes:
        nid = n["id"]
        title = n.get("title") or nid
        body = n.get("content_markdown") or ""
        # strip existing frontmatter if present
        if body.startswith("---"):
            parts = body.split("---", 2)
            if len(parts) >= 3:
                body = parts[2].lstrip("\n")
        refs = n.get("substrate_refs") or []
        if isinstance(refs, str):
            try:
                refs = json.loads(refs)
            except Exception:
                refs = []
        updated = ""
        if n.get("updated_at"):
            updated = (
                n["updated_at"].strftime("%Y-%m-%d")
                if hasattr(n["updated_at"], "strftime")
                else str(n["updated_at"])[:10]
            )
        # detect concept-growth notes
        ntype = "concept" if "## 来源补充" in (n.get("content_markdown") or "") else "note"
        fm = _frontmatter(
            id=nid,
            type_=ntype,
            title=title,
            sources=list(refs) if refs else [],
            updated=updated or now,
        )
        path = f"notes/{_slug(title, nid)}.md"
        # collision
        if path in files:
            path = f"notes/{_slug(title, nid)}-{nid[:8]}.md"
        files[path] = fm + _ensure_body_has_title(title, body)
        note_index.append({"id": nid, "title": title, "path": path, "type": ntype})

    # --- graph concepts (summary pages) ---
    entities = query(
        """
        SELECT id, name, entity_type, description, source_substrate_ids, mention_count, updated_at
        FROM graph_entities
        WHERE user_id = %(uh)s
        ORDER BY mention_count DESC NULLS LAST
        LIMIT 2000
        """,
        {"uh": uid_hash},
    )
    concept_index = []
    for e in entities:
        eid = e["id"]
        name = e.get("name") or eid
        sids = e.get("source_substrate_ids") or []
        if isinstance(sids, str):
            try:
                sids = json.loads(sids)
            except Exception:
                sids = []
        desc = e.get("description") or ""
        etype = e.get("entity_type") or "concept"
        body = f"{desc}\n\n## 来源\n\n"
        for sid in (sids or [])[:20]:
            body += f"- substrate://{sid}\n"
        body += f"\n_mentions: {e.get('mention_count') or 1}_\n"
        fm = _frontmatter(
            id=eid,
            type_=etype,
            title=name,
            sources=list(sids or []),
            updated=now,
            extra={"mention_count": e.get("mention_count") or 1},
        )
        path = f"concepts/{_slug(name, eid)}.md"
        if path in files:
            path = f"concepts/{_slug(name, eid)}-{eid[:8]}.md"
        files[path] = fm + _ensure_body_has_title(name, body)
        concept_index.append({"id": eid, "title": name, "path": path, "type": etype})

    # --- sources (substrates with markdown) ---
    sources = query(
        """
        SELECT s.id, s.title, s.source, s.created_at, s.meta_json, d.content
        FROM substrates s
        JOIN derivative d ON d.substrate_id = s.id
          AND d.kind = 'markdown'
          AND d.content IS NOT NULL AND d.content <> ''
        WHERE s.user_id = %(uh)s
        ORDER BY s.created_at DESC
        LIMIT 5000
        """,
        {"uh": uid_hash},
    )
    source_index = []
    for s in sources:
        sid = s["id"]
        title = s.get("title") or sid
        content = s.get("content") or ""
        created = ""
        if s.get("created_at"):
            created = (
                s["created_at"].strftime("%Y-%m-%d")
                if hasattr(s["created_at"], "strftime")
                else str(s["created_at"])[:10]
            )
        fm = _frontmatter(
            id=sid,
            type_="source",
            title=title,
            sources=[sid],
            updated=created or now,
            extra={"origin": s.get("source") or ""},
        )
        path = f"sources/{_slug(title, sid)}.md"
        if path in files:
            path = f"sources/{_slug(title, sid)}-{sid[:8]}.md"
        files[path] = fm + _ensure_body_has_title(title, content)
        source_index.append({"id": sid, "title": title, "path": path})

    # --- Evidence / highlights (machine-readable and portable) ---
    evidence_rows: list[dict[str, Any]] = []
    try:
        evidence_rows = query(
            """
            SELECT e.id, e.substrate_id, h.color, e.quote AS text, h.note,
                   h.location_json, e.confidence, e.quote_hash, e.locator_json,
                   e.created_at, e.updated_at
            FROM stratum.evidence e
            LEFT JOIN highlights h ON h.id = e.source_highlight_id
            WHERE e.user_id IN (%(uh)s, %(uid)s)
            ORDER BY e.created_at DESC
            """,
            {"uh": uid_hash, "uid": user_id},
        )
    except Exception as exc:
        log.warning("vault export: canonical evidence unavailable, using highlights: %s", exc)
        try:
            evidence_rows = query(
                """
                SELECT id, substrate_id, color, text, note, location_json,
                       confidence, quote_hash, locator_json, created_at, updated_at
                FROM highlights
                WHERE user_id = %(uh)s
                ORDER BY created_at DESC
                """,
                {"uh": uid_hash},
            )
        except Exception as legacy_exc:
            log.warning("vault export: highlight evidence unavailable: %s", legacy_exc)

    evidence_index: list[dict[str, Any]] = []
    for row in evidence_rows:
        evidence_id = row["id"]
        evidence = {
            "id": evidence_id,
            "type": "Evidence",
            "source": f"substrate://{row.get('substrate_id')}",
            "quote": row.get("text") or "",
            "quote_hash": row.get("quote_hash"),
            "confidence": float(row.get("confidence") or 1.0),
            "color": row.get("color") or "yellow",
            "note": row.get("note"),
            "locator": _json_value(row.get("locator_json"), {}),
            "legacy_location": _json_value(row.get("location_json"), {}),
            "created_at": _iso_value(row.get("created_at")),
            "updated_at": _iso_value(row.get("updated_at")),
        }
        path = f"evidence/{_slug(str(evidence_id), str(evidence_id))}.json"
        files[path] = json.dumps(evidence, ensure_ascii=False, indent=2)
        evidence_index.append({"id": evidence_id, "path": path, "type": "Evidence"})

    # --- Learning state (FSRS cards + user preference) ---
    flashcards: list[dict[str, Any]] = []
    learning_preferences: dict[str, Any] = {"desired_retention": 0.9}
    try:
        flashcards = query(
            "SELECT id, source_kind, source_id, source_title, front, back, tags, "
            "repetitions, easiness, interval_days, due_at, fsrs_state, fsrs_step, "
            "stability, difficulty, last_review_at, desired_retention, created_at, updated_at "
            "FROM flashcards WHERE user_id = %(uid)s ORDER BY due_at ASC",
            {"uid": user_id},
        )
        prefs = query(
            "SELECT desired_retention, updated_at FROM learning_preferences "
            "WHERE user_id = %(uid)s LIMIT 1",
            {"uid": user_id},
        )
        if prefs:
            learning_preferences = {
                "desired_retention": float(prefs[0].get("desired_retention") or 0.9),
                "updated_at": _iso_value(prefs[0].get("updated_at")),
            }
    except Exception as exc:
        log.warning("vault export: learning tables unavailable: %s", exc)

    learning_rows = []
    for card in flashcards:
        learning_rows.append(
            {
                key: (
                    _json_value(value, [])
                    if key == "tags"
                    else _iso_value(value)
                    if key in {"due_at", "last_review_at", "created_at", "updated_at"}
                    else value
                )
                for key, value in card.items()
            }
        )
    files["learning/flashcards.json"] = json.dumps(
        {"schema": "stratum.fsrs-card", "cards": learning_rows},
        ensure_ascii=False,
        indent=2,
    )
    files["learning/preferences.json"] = json.dumps(
        {"schema": "stratum.fsrs-preferences", **learning_preferences},
        ensure_ascii=False,
        indent=2,
    )

    # --- index + readme ---
    index = {
        "version": 2,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user_id_hash": uid_hash[:12] + "…",
        "counts": {
            "notes": len(note_index),
            "concepts": len(concept_index),
            "sources": len(source_index),
            "evidence": len(evidence_index),
            "flashcards": len(learning_rows),
            "files": len(files) + 3,
        },
        "notes": note_index,
        "concepts": concept_index,
        "sources": source_index[:500],  # cap index size
        "evidence": evidence_index,
        "learning": {
            "flashcards": "learning/flashcards.json",
            "preferences": "learning/preferences.json",
        },
    }
    files["index.json"] = json.dumps(index, ensure_ascii=False, indent=2)
    files["manifest.json"] = json.dumps(
        {
            "schema": "stratum.vault",
            "schema_version": 2,
            "exported_at": index["exported_at"],
            "user_id_hash": index["user_id_hash"],
            "resources": {
                "notes": "notes/",
                "concepts": "concepts/",
                "sources": "sources/",
                "evidence": "evidence/",
                "learning": "learning/",
            },
            "index": "index.json",
        },
        ensure_ascii=False,
        indent=2,
    )
    files["README.md"] = (
        f"# Stratum Personal Knowledge Foundation 导出\n\n"
        f"- 导出时间: {index['exported_at']}\n"
        f"- 笔记: {index['counts']['notes']}\n"
        f"- 概念: {index['counts']['concepts']}\n"
        f"- 资料源: {index['counts']['sources']}\n"
        f"- Evidence: {index['counts']['evidence']}\n"
        f"- 闪卡: {index['counts']['flashcards']}\n\n"
        f"## 目录\n\n"
        f"- `notes/` — 人类笔记与概念生长页\n"
        f"- `concepts/` — 图谱实体摘要\n"
        f"- `sources/` — 入库原文 Markdown\n"
        f"- `evidence/` — 可引用 Evidence（含 quote_hash/confidence/locator）\n"
        f"- `learning/` — FSRS 闪卡与 Desired Retention\n"
        f"- `manifest.json` — 版本化机器清单\n"
        f"- `index.json` — 详细清单\n\n"
        f"YAML frontmatter: `id, type, title, aliases, sources, updated`\n"
    )
    return files


def build_vault_zip(user_id: str) -> bytes:
    """Zip the vault in-memory."""
    files = build_vault_files(user_id)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in files.items():
            zf.writestr(f"aii-note-vault/{path}", content.encode("utf-8"))
    return buf.getvalue()


def vault_stats(user_id: str) -> dict[str, Any]:
    files = build_vault_files(user_id)
    # re-count without building twice is ok for preview - use lighter query
    uid_hash = hash_user_id(user_id)
    notes_n = query(
        "SELECT count(*) AS n FROM notes_sl WHERE user_id=%(uid)s AND deleted_at IS NULL",
        {"uid": user_id},
    )
    concepts_n = query(
        "SELECT count(*) AS n FROM graph_entities WHERE user_id=%(uh)s",
        {"uh": uid_hash},
    )
    sources_n = query(
        """
        SELECT count(DISTINCT s.id) AS n FROM substrates s
        JOIN derivative d ON d.substrate_id=s.id AND d.kind='markdown'
          AND d.content IS NOT NULL AND d.content<>''
        WHERE s.user_id=%(uh)s
        """,
        {"uh": uid_hash},
    )
    return {
        "notes": int((notes_n[0]["n"] if notes_n else 0) or 0),
        "concepts": int((concepts_n[0]["n"] if concepts_n else 0) or 0),
        "sources": int((sources_n[0]["n"] if sources_n else 0) or 0),
        "approx_files": len(files),
    }
