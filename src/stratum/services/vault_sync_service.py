"""Vault ↔ local/cloud-folder sync (MVP week 5–6).

Export: write build_vault_files() into a directory (rclone/gdrive mount OK).
Import: read notes/*.md with YAML frontmatter back into notes_sl.

Path safety: only roots listed in STRATUM_VAULT_SYNC_ROOTS (colon-separated),
defaulting to /tmp/aii-vault and /root/.stratum (set STRATUM_VAULT_SYNC_ROOTS in prod).
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from stratum.common import generate_ulid, now_utc
from stratum.db import insert, query, read, update
from stratum.services.vault_export_service import build_vault_files

log = logging.getLogger(__name__)

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.S)
_DEFAULT_ROOTS = "/tmp/aii-vault:/root/.stratum"


def allowed_roots() -> list[Path]:
    raw = os.environ.get("STRATUM_VAULT_SYNC_ROOTS", _DEFAULT_ROOTS)
    return [Path(p).resolve() for p in raw.split(":") if p.strip()]


def assert_safe_vault_path(path_str: str) -> Path:
    """Resolve path and ensure it is under an allowed root."""
    if not path_str or not path_str.strip():
        raise ValueError("path required")
    p = Path(path_str).expanduser().resolve()
    roots = allowed_roots()
    for root in roots:
        try:
            p.relative_to(root)
            return p
        except ValueError:
            continue
    raise ValueError(
        f"path not under allowed roots: {[str(r) for r in roots]}. "
        "Set STRATUM_VAULT_SYNC_ROOTS to add mounts."
    )


def assert_safe_watch_path(path_str: str) -> Path:
    """Like assert_safe_vault_path, but prefers STRATUM_FOLDER_WATCH_ROOTS when set."""
    if not path_str or not path_str.strip():
        raise ValueError("path required")
    raw = os.environ.get("STRATUM_FOLDER_WATCH_ROOTS")
    if raw:
        roots = [Path(p).resolve() for p in raw.split(":") if p.strip()]
    else:
        roots = allowed_roots()
    p = Path(path_str).expanduser().resolve()
    for root in roots:
        try:
            p.relative_to(root)
            return p
        except ValueError:
            continue
    raise ValueError(
        f"path not under allowed roots: {[str(r) for r in roots]}. "
        "Set STRATUM_FOLDER_WATCH_ROOTS or STRATUM_VAULT_SYNC_ROOTS."
    )


def _safe_dest_under_root(root: Path, rel: str) -> Path | None:
    """Resolve root/rel and ensure it stays under root (blocks .. escape)."""
    if not rel or Path(rel).is_absolute():
        return None
    # Reject any parent traversal in the relative path
    parts = Path(rel).parts
    if any(p == ".." for p in parts):
        return None
    dest = (root / rel).resolve()
    try:
        dest.relative_to(root.resolve())
    except ValueError:
        return None
    return dest


def export_vault_to_path(user_id: str, path_str: str) -> dict[str, Any]:
    """Write full vault markdown tree to disk."""
    root = assert_safe_vault_path(path_str)
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()
    files = build_vault_files(user_id)
    written = 0
    for rel, content in files.items():
        dest = _safe_dest_under_root(root, rel)
        if dest is None:
            log.warning("vault_sync export skip unsafe rel path: %r", rel)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        written += 1
    # stamp
    meta = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user_id_suffix": user_id[-8:] if len(user_id) > 8 else user_id,
        "files": written,
    }
    (root / ".aii-vault-sync.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info("vault_sync export → %s (%d files)", root, written)
    return {"status": "ok", "path": str(root), "files_written": written, "meta": meta}


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    m = _FM_RE.match(text or "")
    if not m:
        return {}, text or ""
    raw = m.group(1)
    body = text[m.end() :]
    meta: dict[str, Any] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k, v = k.strip(), v.strip()
        if v.startswith("[") or v.startswith("{"):
            try:
                meta[k] = json.loads(v)
            except Exception:
                meta[k] = v.strip('"')
        else:
            meta[k] = v.strip('"')
    return meta, body


def import_notes_from_path(user_id: str, path_str: str) -> dict[str, Any]:
    """Import notes/*.md from a vault directory into notes_sl (upsert by frontmatter id)."""
    root = assert_safe_vault_path(path_str)
    notes_dir = root / "notes"
    if not notes_dir.is_dir():
        # also accept flat *.md at root
        candidates = list(root.glob("*.md"))
    else:
        candidates = list(notes_dir.rglob("*.md"))

    created = updated = skipped = 0
    errors: list[str] = []

    for fp in candidates:
        if fp.name in ("README.md", "index.md"):
            skipped += 1
            continue
        try:
            text = fp.read_text(encoding="utf-8")
        except Exception as e:
            errors.append(f"{fp.name}: read {e}")
            continue
        meta, body = _parse_frontmatter(text)
        title = (meta.get("title") or fp.stem).strip()
        note_id = (meta.get("id") or "").strip()
        sources = meta.get("sources") or []
        if isinstance(sources, str):
            try:
                sources = json.loads(sources)
            except Exception:
                sources = []

        content = text  # keep frontmatter in stored markdown for round-trip
        if note_id:
            existing = read("notes_sl", note_id)
            if existing and existing.get("user_id") == user_id:
                if existing.get("deleted_at"):
                    # revive + update
                    update(
                        "notes_sl",
                        note_id,
                        {
                            "title": title,
                            "content_markdown": content,
                            "deleted_at": None,
                            "updated_at": now_utc(),
                        },
                    )
                    updated += 1
                elif (existing.get("content_markdown") or "") != content:
                    update(
                        "notes_sl",
                        note_id,
                        {
                            "title": title,
                            "content_markdown": content,
                            "updated_at": now_utc(),
                        },
                    )
                    updated += 1
                else:
                    skipped += 1
                continue
            # id not owned / missing → create with that id if free
            if not existing:
                insert(
                    "notes_sl",
                    {
                        "id": note_id,
                        "user_id": user_id,
                        "title": title,
                        "content_markdown": content,
                        "substrate_refs": sources if isinstance(sources, list) else [],
                        "concept_refs": [],
                        "content_refs": [],
                        "created_at": now_utc(),
                        "updated_at": now_utc(),
                    },
                )
                created += 1
                continue

        # no id or conflict → new note
        nid = generate_ulid()
        # rewrite id in frontmatter if present
        if content.startswith("---"):
            content = _FM_RE.sub(
                lambda m: m.group(0).replace(
                    f"id: {meta.get('id')}", f"id: {nid}"
                )
                if meta.get("id")
                else f"---\nid: {nid}\ntype: note\ntitle: {title}\naliases: []\nsources: []\nupdated: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n---\n\n{body}",
                content,
                count=1,
            )
            if "id:" not in content[:80]:
                content = (
                    f"---\nid: {nid}\ntype: note\ntitle: {title}\n"
                    f"aliases: []\nsources: []\n"
                    f"updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n---\n\n"
                    f"{body}"
                )
        else:
            content = (
                f"---\nid: {nid}\ntype: note\ntitle: {title}\n"
                f"aliases: []\nsources: []\n"
                f"updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n---\n\n"
                f"{content}"
            )
        insert(
            "notes_sl",
            {
                "id": nid,
                "user_id": user_id,
                "title": title,
                "content_markdown": content,
                "substrate_refs": sources if isinstance(sources, list) else [],
                "concept_refs": [],
                "content_refs": [],
                "created_at": now_utc(),
                "updated_at": now_utc(),
            },
        )
        created += 1

    return {
        "status": "ok",
        "path": str(root),
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors[:20],
        "scanned": len(candidates),
    }


def sync_vault(user_id: str, path_str: str, mode: str = "export") -> dict[str, Any]:
    mode = (mode or "export").lower()
    if mode == "export":
        return export_vault_to_path(user_id, path_str)
    if mode == "import":
        return import_notes_from_path(user_id, path_str)
    if mode == "both":
        out_ex = export_vault_to_path(user_id, path_str)
        out_im = import_notes_from_path(user_id, path_str)
        return {"status": "ok", "export": out_ex, "import": out_im}
    raise ValueError("mode must be export|import|both")
