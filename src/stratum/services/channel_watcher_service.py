# src/stratum/services/channel_watcher_service.py
import asyncio
import logging
import json
from stratum.db import get_conn
from stratum.services.channel_subscription_store import SubscriptionStore

log = logging.getLogger(__name__)
CHANNEL_CHECK_INTERVAL = 3600  # 1小时扫一次

async def _check_one_subscription(sub_id: str, user_id_hash: str, channel_url: str, rules_dict: dict):
    from oservi.engines.channel_watcher import ChannelWatcherEngine
    from oprim._channel_list_videos import channel_list_videos
    from oprim._media_types import FilterRules
    
    # 更新状态为 scanning
    with get_conn() as conn:
        conn.execute("UPDATE channel_subscriptions SET scan_status='scanning' WHERE id=?", (sub_id,))

    substrate_ids = []
    current_video_title = [""]

    async def adapted_ingest_media(video_url: str, **kwargs):
        from omodul.process_media_substrate import (
            MediaConfig, MediaInput, process_media_substrate,
        )
        import tempfile
        from pathlib import Path

        # 提取配置参数
        proxy = kwargs.get("proxy")
        asr_backend = kwargs.get("asr_backend", "local")
        transcribe = kwargs.get("transcribe_if_no_subtitle", True)
        cookies_path = kwargs.get("cookies_path")

        config = MediaConfig(
            video_url=video_url,
            user_id_hash=user_id_hash,
            proxy=proxy,
            asr_backend=asr_backend,
            transcribe_if_no_subtitle=transcribe,
            llm_provider="qwen3",
            llm_model="qwen3-max",
            cookies_path=cookies_path,
        )

        with tempfile.TemporaryDirectory(prefix="channel_ingest_") as tmpdir:
            try:
                result = await process_media_substrate(
                    config=config,
                    input_data=MediaInput(),
                    output_dir=Path(tmpdir),
                )
            except Exception as exc:
                log.error("channel_ingest: process_media_substrate failed url=%s: %s", video_url, exc, exc_info=True)
                return {"status": "failed", "error": str(exc)}

        status = result.get("status")
        title = (result.get("title") or "").strip()
        if title:
            current_video_title[0] = title
            # 更新当前处理的视频标题以供前端轮询进度
            try:
                with get_conn() as conn:
                    conn.execute(
                        "UPDATE channel_subscriptions SET current_video=? WHERE id=?",
                        (title, sub_id)
                    )
            except Exception:
                pass

        if status == "completed":
            sid = result.get("substrate_id") or ""
            if sid:
                # 补齐 substrates 属性：medium="video" 并修复标题
                try:
                    import json as _json
                    with get_conn() as conn:
                        row = conn.execute(
                            "SELECT meta_json FROM substrates WHERE id=?", (sid,)
                        ).fetchone()
                        meta = _json.loads(row[0] or "{}") if row else {}
                        meta["medium"] = "video"
                        meta_str = _json.dumps(meta, ensure_ascii=False)
                        if title:
                            conn.execute(
                                "UPDATE substrates SET meta_json=?, title=? WHERE id=?",
                                (meta_str, title, sid),
                            )
                        else:
                            conn.execute(
                                "UPDATE substrates SET meta_json=? WHERE id=?",
                                (meta_str, sid),
                            )
                        log.info("channel_ingest: patched medium=video title=%s sid=%s", title, sid)
                except Exception as exc:
                    log.warning("channel_ingest: medium/title patch failed sid=%s: %s", sid, exc)

                # 新入库的 markdown 导出
                try:
                    from stratum.services.md_export_service import export_one
                    export_one(sid)
                except Exception as exc:
                    log.warning("channel_ingest: md_export failed sid=%s: %s", sid, exc)

                substrate_ids.append(sid)
                return {"status": "completed", "substrate_id": sid}

        return {"status": "failed", "error": str(result.get("error"))}

    async def custom_filter_videos(videos, rules, llm=None):
        from oskill._video_filter_by_rules import video_filter_by_rules
        from obase.provider_registry import ProviderRegistry
        if llm is None:
            try:
                llm = ProviderRegistry.get().llm("qwen3")
            except Exception:
                pass
        return await video_filter_by_rules(videos, rules=rules, llm=llm)

    store = SubscriptionStore(sub_id)

    rules_obj = FilterRules(
        after_date=rules_dict.get("after_date"),
        limit=rules_dict.get("limit"),
        min_duration=rules_dict.get("min_duration"),
        max_duration=rules_dict.get("max_duration"),
        title_include=rules_dict.get("title_include", []),
        title_exclude=rules_dict.get("title_exclude", []),
        llm_filter=rules_dict.get("llm_filter"),
    )

    async def adapted_list_videos(channel_url: str, proxy: str | None = None, limit: int | None = None):
        return await channel_list_videos(
            channel_url=channel_url,
            proxy=proxy,
            limit=limit,
            cookies_path="~/.stratum/youtube_cookies.txt",
        )

    # 真实装配调用 ChannelWatcherEngine
    engine = ChannelWatcherEngine(
        list_videos=adapted_list_videos,
        filter_videos=custom_filter_videos,
        ingest_media=adapted_ingest_media,
        subscription=store,
        config={
            "channel_url": channel_url,
            "proxy": "socks5://100.73.220.5:21080",
            "filter_rules": rules_obj,
            "user_id_hash": user_id_hash,
            "asr_backend": "local",
            "transcribe_if_no_subtitle": True,
            "cookies_path": "~/.stratum/youtube_cookies.txt",
        }
    )

    try:
        res = await engine._tick()
        found_count = res.get("new_videos", 0)
        ingested_count = res.get("ingested", 0)
        scan_status = "completed"
        error_msg = None
    except Exception as exc:
        import traceback
        error_msg = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        found_count = 0
        ingested_count = 0
        scan_status = "error"
        log.exception("Scan subscription failed sub_id=%s", sub_id)

    # 完成更新
    with get_conn() as conn:
        if scan_status == "completed":
            row = conn.execute("SELECT found_count, ingested_count FROM channel_subscriptions WHERE id=?", (sub_id,)).fetchone()
            current_found = row[0] if row else 0
            current_ingested = row[1] if row else 0
            
            conn.execute(
                "UPDATE channel_subscriptions SET scan_status='completed', last_check=NOW(), "
                "found_count=?, ingested_count=? WHERE id=?",
                (current_found + found_count, current_ingested + ingested_count, sub_id)
            )
        else:
            conn.execute(
                "UPDATE channel_subscriptions SET scan_status='error', current_video=? WHERE id=?",
                (error_msg[:300] if error_msg else "Unknown Error", sub_id)
            )

async def _run_first_check(sub_id: str, user_id_hash: str, channel_url: str, rules_dict: dict):
    try:
        await _check_one_subscription(sub_id, user_id_hash, channel_url, rules_dict)
    except Exception:
        log.exception("First scan background task failed sub_id=%s", sub_id)

async def channel_watcher_loop():
    await asyncio.sleep(60)  # 启动延迟
    while True:
        try:
            with get_conn() as conn:
                subs = conn.execute(
                    "SELECT id, user_id, channel_url, rules_json FROM channel_subscriptions WHERE status='active'"
                ).fetchall()
            for sub_id, uh, url, rules in subs:
                await _check_one_subscription(sub_id, uh, url, json.loads(rules or '{}'))
        except Exception as e:
            log.error("channel_watcher_loop error: %s", e)
        await asyncio.sleep(CHANNEL_CHECK_INTERVAL)
