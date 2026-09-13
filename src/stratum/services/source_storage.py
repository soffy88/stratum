"""Durable storage and resolution for canonical source bytes.

The parser may create markdown derivatives, but the canonical substrate must
continue to point at the bytes that were uploaded.  Files are content
addressed below the configured Stratum data directory and scoped by the
owner-hash so the filesystem layout does not become an authorization bypass.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from stratum.db import get_conn
from stratum.utils.user_id_hash import hash_user_id


def _root() -> Path:
    return Path(os.environ.get("STRATUM_DATA_DIR", str(Path.home() / ".stratum"))) / "originals"


def resolve_storage_path(uri: str | Path) -> Path:
    """Resolve a local URI, including the standard container mount mapping."""
    path = Path(uri)
    if path.is_file():
        return path
    configured_root = _root().parent
    legacy_root = Path("/root/.stratum")
    try:
        relative = path.relative_to(legacy_root)
    except ValueError:
        return path
    mapped = configured_root / relative
    return mapped if mapped.is_file() else path


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def store_original_binary(
    path: str | Path, owner_id: str, content_hash: str | None = None
) -> dict[str, Any]:
    """Copy verified upload bytes into immutable, owner-scoped storage."""
    source = Path(path)
    actual_hash, size = _hash_file(source)
    if content_hash and actual_hash != content_hash:
        raise ValueError("original binary hash does not match upload hash")
    owner_hash = hash_user_id(owner_id)
    suffix = source.suffix.lower() or ".bin"
    target_dir = _root() / owner_hash
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{actual_hash}{suffix}"
    if not target.exists():
        fd, temp_name = tempfile.mkstemp(prefix=f".{actual_hash}.", dir=str(target_dir))
        try:
            with os.fdopen(fd, "wb") as out, source.open("rb") as inp:
                while chunk := inp.read(1024 * 1024):
                    out.write(chunk)
                out.flush()
                os.fsync(out.fileno())
            os.replace(temp_name, target)
            # The service container and host-side verification may use
            # different UIDs; the URI is still protected by SQL ownership.
            target.chmod(0o644)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
    check_hash, check_size = _hash_file(target)
    if check_hash != actual_hash or check_size != size:
        raise IOError("stored original binary failed integrity check")
    return {"uri": str(target), "hash": actual_hash, "size": size, "owner_hash": owner_hash}


def attach_original_binary(
    source_id: str,
    owner_id: str,
    path: str | Path,
    *,
    content_hash: str | None = None,
    mime_type: str | None = None,
) -> dict[str, Any]:
    """Attach durable original bytes to an owned canonical substrate."""
    stored = store_original_binary(path, owner_id, content_hash)
    owner_hash = hash_user_id(owner_id)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, user_id, meta_json FROM substrates WHERE id=? AND user_id=?",
            (source_id, owner_hash),
        ).fetchone()
        if not row:
            raise PermissionError("source is not owned by authenticated user")
        meta = row[2] if isinstance(row[2], dict) else json.loads(row[2] or "{}")
        meta.update(
            {
                "original_binary_uri": stored["uri"],
                "original_binary_hash": stored["hash"],
                "original_binary_size": stored["size"],
                "original_binary_mime": mime_type,
            }
        )
        conn.execute(
            "UPDATE substrates SET source_path=?, file_hash=?, mime=COALESCE(?, mime), meta_json=?, updated_at=NOW() WHERE id=? AND user_id=?",
            (stored["uri"], stored["hash"], mime_type, json.dumps(meta), source_id, owner_hash),
        )
    return stored


def resolve_original_source(source_id: str, owner_id: str) -> dict[str, Any]:
    """Resolve and integrity-check original bytes after SQL ownership check."""
    owner_hash = hash_user_id(owner_id)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, source_path, file_hash, mime, byte_size, meta_json FROM substrates WHERE id=? AND user_id=?",
            (source_id, owner_hash),
        ).fetchone()
    if not row:
        raise PermissionError("source is not owned by authenticated user")
    path = resolve_storage_path(row[1]) if row[1] else None
    if not path or not path.is_file():
        raise FileNotFoundError("canonical original binary is unavailable")
    actual_hash, size = _hash_file(path)
    expected = row[2]
    if expected and actual_hash != expected:
        raise ValueError("canonical original binary hash mismatch")
    return {
        "source_id": row[0],
        "uri": str(path),
        "path": path,
        "content_hash": actual_hash,
        "mime_type": row[3],
        "size": size,
    }
