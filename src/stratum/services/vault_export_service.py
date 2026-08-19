"""整库 Markdown 导出 — 可迁移知识库文件夹 (MVP 验收 #4).

布局:
  vault/
    README.md
    notes/          # 人类笔记 + 概念生长页 (notes_sl)
    concepts/       # graph_entities 摘要页
    sources/        # substrate 原文 markdown derivative
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
from pathlib import Path
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

    # --- index + readme ---
    index = {
        "version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user_id_hash": uid_hash[:12] + "…",
        "counts": {
            "notes": len(note_index),
            "concepts": len(concept_index),
            "sources": len(source_index),
            "files": len(files) + 2,
        },
        "notes": note_index,
        "concepts": concept_index,
        "sources": source_index[:500],  # cap index size
    }
    files["index.json"] = json.dumps(index, ensure_ascii=False, indent=2)
    files["README.md"] = (
        f"# AII Note 知识库导出\n\n"
        f"- 导出时间: {index['exported_at']}\n"
        f"- 笔记: {index['counts']['notes']}\n"
        f"- 概念: {index['counts']['concepts']}\n"
        f"- 资料源: {index['counts']['sources']}\n\n"
        f"## 目录\n\n"
        f"- `notes/` — 人类笔记与概念生长页\n"
        f"- `concepts/` — 图谱实体摘要\n"
        f"- `sources/` — 入库原文 Markdown\n"
        f"- `index.json` — 清单\n\n"
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
