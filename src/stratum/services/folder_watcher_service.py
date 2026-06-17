import asyncio
import hashlib
import logging
from pathlib import Path

log = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {'.pdf', '.epub', '.md', '.txt'}
SCAN_INTERVAL_SECONDS = 300


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


async def _scan_one_watch(watch_id: str, user_id_hash: str, path_str: str):
    from stratum.db import get_conn
    from omodul.process_inbox_substrate import (
        process_inbox_substrate, InboxConfig, InboxInput
    )
    from stratum.common import ensure_dir, user_inbox_dir

    path = Path(path_str)
    if not path.exists():
        log.warning("folder_watcher: path not found: %s", path_str)
        return

    files = [f for f in path.rglob('*')
             if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS]

    ingested = 0
    for f in files:
        try:
            fhash = _file_hash(f)

            with get_conn() as conn:
                exists = conn.execute(
                    "SELECT id FROM substrates WHERE file_hash=? AND user_id=?",
                    (fhash, user_id_hash)
                ).fetchone()

            if exists:
                continue

            config = InboxConfig(
                file_path=str(f),
                file_checksum=fhash,
                user_id_hash=user_id_hash,
                auto_classify=True,
                llm_provider="qwen3",
                llm_model="qwen3-max",
            )

            result = await asyncio.to_thread(
                process_inbox_substrate,
                config=config,
                input_data=InboxInput(),
                output_dir=ensure_dir(user_inbox_dir(user_id_hash)),
            )

            if result.get("status") == "completed":
                ingested += 1
                log.info("folder_watcher: ingested %s", f.name)
            else:
                log.warning("folder_watcher: failed %s: %s",
                            f.name, result.get("error"))

        except Exception as e:
            log.warning("folder_watcher: skip %s: %s", f.name, e)

    with get_conn() as conn:
        conn.execute(
            "UPDATE folder_watches SET last_scan_at=NOW(), file_count=? WHERE id=?",
            (len(files), watch_id)
        )

    log.info("folder_watcher: %s — %d files, %d ingested",
             path_str, len(files), ingested)


async def folder_watcher_loop():
    await asyncio.sleep(30)
    while True:
        try:
            from stratum.db import get_conn
            with get_conn() as conn:
                watches = conn.execute(
                    "SELECT id, user_id, path FROM folder_watches "
                    "WHERE status='active'"
                ).fetchall()
            for watch_id, user_id_hash, path_str in watches:
                await _scan_one_watch(watch_id, user_id_hash, path_str)
        except Exception as e:
            log.error("folder_watcher_loop error: %s", e)
        await asyncio.sleep(SCAN_INTERVAL_SECONDS)
