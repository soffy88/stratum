import asyncio
import hashlib
import logging
from pathlib import Path

log = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {'.pdf', '.epub', '.md', '.txt'}
SCAN_INTERVAL_SECONDS = 300
MAX_FILE_SIZE_MB = 100  # 超过 100MB 跳过


def _file_hash_sync(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


async def _scan_one_watch(watch_id: str, user_id_raw: str, path_str: str):
    from stratum.db import get_conn
    from omodul.process_inbox_substrate import (
        process_inbox_substrate, InboxConfig, InboxInput
    )
    from stratum.common import ensure_dir, user_inbox_dir
    from stratum.utils.user_id_hash import hash_user_id

    # user_id_raw may be email (jwt sub) or legacy ULID — always hash before using
    user_id_hash = hash_user_id(user_id_raw)

    path = Path(path_str)
    if not path.exists():
        log.warning("folder_watcher: path not found: %s", path_str)
        return

    files = [f for f in path.rglob('*')
             if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS]

    total = len(files)
    ingested = 0
    scanned = 0
    skipped_large = 0

    # 扫描开始：重置进度，写入总文件数
    with get_conn() as conn:
        conn.execute(
            "UPDATE folder_watches SET scan_status='scanning', scanned_count=0, "
            "ingested_count=0, file_count=?, current_file='' WHERE id=?",
            (total, watch_id)
        )

    for f in files:
        try:
            size_mb = f.stat().st_size / 1024 / 1024
            if size_mb > MAX_FILE_SIZE_MB:
                log.info("folder_watcher: skip large file (%.0fMB) %s", size_mb, f.name)
                skipped_large += 1
            else:
                fhash = await asyncio.to_thread(_file_hash_sync, f)

                with get_conn() as conn:
                    exists = conn.execute(
                        "SELECT id FROM substrates WHERE file_hash=? AND user_id=?",
                        (fhash, user_id_hash)
                    ).fetchone()

                if not exists:
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
                        findings = result.get("findings")
                        if findings:
                            from stratum.api.routers.inbox import (
                                _fill_derivative_content,
                                _extract_id,
                            )
                            sid = _extract_id(findings.substrate_id)
                            if sid:
                                _fill_derivative_content(sid, findings)
                        ingested += 1
                        log.info("folder_watcher: ingested %s", f.name)
                    else:
                        log.warning("folder_watcher: failed %s: %s",
                                    f.name, result.get("error"))

        except Exception as e:
            log.warning("folder_watcher: skip %s: %s", f.name, e)

        # 每个文件处理后立即写进度
        scanned += 1
        with get_conn() as conn:
            conn.execute(
                "UPDATE folder_watches SET scanned_count=?, ingested_count=?, "
                "current_file=? WHERE id=?",
                (scanned, ingested, f.name, watch_id)
            )

    # 扫描完成
    with get_conn() as conn:
        conn.execute(
            "UPDATE folder_watches SET scan_status='completed', last_scan_at=NOW(), "
            "file_count=?, ingested_count=?, scanned_count=?, current_file='' WHERE id=?",
            (total, ingested, total, watch_id)
        )

    log.info("folder_watcher: %s — %d files, %d ingested, %d skipped (>%dMB)",
             path_str, total, ingested, skipped_large, MAX_FILE_SIZE_MB)


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
