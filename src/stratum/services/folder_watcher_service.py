"""Background folder watcher — periodic scan + ingest into Stratum."""

import asyncio
import hashlib
import logging
from pathlib import Path

from stratum.db import execute as db_execute, query as db_query
from stratum.utils.user_id_hash import hash_user_id

log = logging.getLogger(__name__)

SUPPORTED_EXT = {'.pdf', '.epub', '.md', '.txt', '.docx'}
SCAN_INTERVAL = 300  # seconds between full scans

try:
    from omodul.process_inbox_substrate import (
        InboxConfig,
        InboxInput,
        process_inbox_substrate,
    )
    from stratum.common import ensure_dir, user_inbox_dir
    _HAS_OMODUL = True
except ImportError:
    _HAS_OMODUL = False
    log.warning("folder_watcher: omodul not available — scan will record files but not ingest")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def _scan_dir(path: Path) -> list[Path]:
    return [f for f in path.rglob('*') if f.is_file() and f.suffix.lower() in SUPPORTED_EXT]


def _ingest_sync(file_path: Path, user_id: str, file_hash: str) -> None:
    """Synchronous ingest — must be called inside asyncio.to_thread."""
    if not _HAS_OMODUL:
        return
    inbox = ensure_dir(user_inbox_dir(user_id))
    config = InboxConfig(
        file_path=str(file_path),
        file_checksum=file_hash,
        user_id_hash=hash_user_id(user_id),
        auto_classify=True,
        llm_provider="qwen3",
        llm_model="qwen3-max",
    )
    result = process_inbox_substrate(config=config, input_data=InboxInput(), output_dir=inbox)
    if result.get("status") == "failed":
        err = (result.get("error") or {}).get("error_message", "unknown")
        raise RuntimeError(err)


async def _scan_one_watch(watch_id: str, user_id: str, path_str: str) -> None:
    path = Path(path_str)
    if not path.exists():
        log.warning("folder_watcher: path not found (check mount): %s", path_str)
        return

    uid_hash = hash_user_id(user_id)
    files = await asyncio.to_thread(_scan_dir, path)
    ingested = 0

    for f in files:
        try:
            file_hash = await asyncio.to_thread(_sha256, f)
            if db_query(
                "SELECT id FROM substrates WHERE file_hash = %(h)s AND user_id = %(u)s",
                {"h": file_hash, "u": uid_hash},
                limit=1,
            ):
                continue
            await asyncio.to_thread(_ingest_sync, f, user_id, file_hash)
            ingested += 1
            log.info("folder_watcher: ingested %s", f.name)
        except Exception:
            log.exception("folder_watcher: error on %s", f.name)

    db_execute(
        "UPDATE folder_watches SET last_scan_at = NOW(), file_count = %(fc)s WHERE id = %(wid)s",
        {"fc": len(files), "wid": watch_id},
    )
    log.info(
        "folder_watcher: %s — %d files total, %d newly ingested",
        path_str, len(files), ingested,
    )


async def folder_watcher_loop() -> None:
    """Background asyncio task. 30s startup delay then every SCAN_INTERVAL seconds."""
    await asyncio.sleep(30)
    while True:
        try:
            watches = db_query(
                "SELECT id, user_id, path FROM folder_watches WHERE status = 'active'",
                limit=1000,
            )
            log.info("folder_watcher: tick — %d active watch(es)", len(watches))
            for w in watches:
                await _scan_one_watch(w["id"], w["user_id"], w["path"])
        except Exception:
            log.exception("folder_watcher_loop tick error")
        await asyncio.sleep(SCAN_INTERVAL)
