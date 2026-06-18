"""
Layer 4: 视频 URL 入库服务。

链路（全在 Layer 4，不改主库）:
  yt-dlp 元数据 + 字幕 → 格式化 Markdown → substrates + derivative 直写 DB
  → export_one() 导出 .md 到 AII 共享目录

字幕优先策略:
  1. 有原生字幕（zh/en）→ 直接用
  2. 有 auto-generated 字幕 → 直接用
  3. 无字幕 → 元数据 + 描述入库，transcript 字段标注 "暂无字幕"

ASR 路径留为 Phase 2（需音频公网 URL 才能调 DashScope Transcription）。
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path

from stratum.common import generate_ulid
from stratum.db import get_conn, insert as db_insert

log = logging.getLogger(__name__)

_DEFAULT_PROXY = os.environ.get("VIDEO_PROXY", "socks5://100.73.220.5:21080")
_YTDLP_TIMEOUT = 60  # seconds per subprocess call


def _run_ytdlp(args: list[str], timeout: int = _YTDLP_TIMEOUT) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["yt-dlp"] + args,
        capture_output=True, text=True, timeout=timeout,
    )


def _extract_metadata(url: str, proxy: str | None) -> dict | None:
    """Return parsed yt-dlp --dump-json for a single video."""
    cmd = ["--dump-json", "--no-playlist", "--skip-download"]
    if proxy:
        cmd = ["--proxy", proxy] + cmd
    r = _run_ytdlp(cmd + [url])
    if r.returncode != 0:
        log.warning("yt-dlp metadata failed for %s: %s", url, r.stderr[-300:])
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        log.warning("yt-dlp metadata JSON parse error for %s", url)
        return None


def _extract_subtitles(url: str, proxy: str | None, tmpdir: str) -> str | None:
    """
    Download best available subtitle (zh-Hans > en > auto-zh > auto-en).
    Returns plain text of subtitle or None if unavailable.
    """
    priority_langs = ["zh-Hans", "en", "zh-Hans-en", "zh"]

    for lang in priority_langs:
        for sub_flag in ["--write-sub", "--write-auto-sub"]:
            cmd = [
                sub_flag, "--sub-lang", lang,
                "--sub-format", "srt",
                "--skip-download",
                "-o", str(Path(tmpdir) / "sub.%(ext)s"),
            ]
            if proxy:
                cmd = ["--proxy", proxy] + cmd
            r = _run_ytdlp(cmd + [url], timeout=30)
            # find any .srt file written
            srt_files = list(Path(tmpdir).glob("*.srt"))
            if srt_files:
                txt = _srt_to_text(srt_files[0])
                if txt.strip():
                    log.info("video_ingest: subtitle found lang=%s auto=%s", lang, "auto" in sub_flag)
                    return txt
    return None


def _srt_to_text(path: Path) -> str:
    """Strip SRT timestamps and index numbers, return clean text."""
    raw = path.read_text(encoding="utf-8", errors="ignore")
    # Remove index lines (pure numbers), timestamp lines (00:00:00,000 --> ...)
    lines = []
    for line in raw.splitlines():
        line = line.strip()
        if re.match(r"^\d+$", line):
            continue
        if re.match(r"^\d{2}:\d{2}:\d{2}[,\.]\d+\s*-->", line):
            continue
        if line:
            lines.append(line)
    return "\n".join(lines)


def _fmt_duration(secs: float | None) -> str:
    if not secs:
        return "未知"
    m, s = divmod(int(secs), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _detect_lang(meta: dict) -> str:
    lang = meta.get("language") or ""
    if lang.startswith("zh"):
        return "zh"
    if lang.startswith("en"):
        return "en"
    # Guess from channel/title CJK
    title = meta.get("title", "")
    if re.search(r"[一-鿿]", title):
        return "zh"
    return "en"


def _build_markdown(meta: dict, subtitle_text: str | None) -> str:
    title = meta.get("title", "Untitled")
    channel = meta.get("channel") or meta.get("uploader") or ""
    upload_date = meta.get("upload_date", "")
    if upload_date and len(upload_date) == 8:
        upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
    duration = _fmt_duration(meta.get("duration"))
    description = (meta.get("description") or "").strip()[:500]
    video_url = meta.get("webpage_url") or meta.get("original_url", "")

    lines = [
        f"# {title}",
        "",
        f"**频道**: {channel}  ",
        f"**时长**: {duration}  ",
        f"**上传日期**: {upload_date}  ",
        f"**来源**: [{video_url}]({video_url})",
        "",
    ]

    if description:
        lines += ["## 简介", "", description, ""]

    if subtitle_text:
        lines += ["## 字幕 / 转录", "", subtitle_text.strip(), ""]
    else:
        lines += [
            "## 字幕 / 转录",
            "",
            "> 该视频暂无字幕，转录功能将在后续版本支持（ASR Phase 2）。",
            "",
        ]

    return "\n".join(lines)


def ingest_video_url(
    url: str,
    user_id_hash: str,
    proxy: str | None = _DEFAULT_PROXY,
) -> dict:
    """
    完整入库链路:
      - yt-dlp 元数据 + 字幕
      - 写 substrates + derivative(markdown)
      - 调 export_one() 导出 .md

    Returns:
        dict with keys: status, substrate_id, title, has_subtitle, error
    """
    log.info("video_ingest: start url=%s", url)

    with tempfile.TemporaryDirectory(prefix="video_ingest_") as tmpdir:
        meta = _extract_metadata(url, proxy)
        if not meta:
            return {"status": "failed", "error": "无法获取视频元数据（网络或 URL 无效）"}

        subtitle_text = _extract_subtitles(url, proxy, tmpdir)
        md = _build_markdown(meta, subtitle_text)

    video_id = meta.get("id", "")
    channel = meta.get("channel") or meta.get("uploader") or ""
    title = meta.get("title", "Untitled Video")
    lang = _detect_lang(meta)
    video_url = meta.get("webpage_url") or url

    # Deduplicate: check if this video URL already exists for this user
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM substrates WHERE source_path = $url AND user_id = $uid",
            {"url": video_url, "uid": user_id_hash},
        ).fetchone()
    if existing:
        return {
            "status": "skipped",
            "substrate_id": existing[0],
            "title": title,
            "reason": "already ingested",
        }

    sid = generate_ulid()
    db_insert("substrates", {
        "id": sid,
        "user_id": user_id_hash,
        "title": title,
        "mime": "text/plain",
        "source_path": video_url,
        "language": lang,
        "meta_json": json.dumps({
            "medium": "video",
            "video_id": video_id,
            "channel": channel,
            "duration_s": meta.get("duration"),
            "upload_date": meta.get("upload_date"),
            "subtitle_source": "subtitle" if subtitle_text else "none",
        }, ensure_ascii=False),
        "parse_quality": "ok",
    })

    deriv_id = generate_ulid()
    db_insert("derivative", {
        "id": deriv_id,
        "substrate_id": sid,
        "kind": "markdown",
        "content": md,
        "medium": "video",
    })

    log.info("video_ingest: substrate created sid=%s title=%s has_sub=%s", sid, title, bool(subtitle_text))

    try:
        from stratum.services.md_export_service import export_one
        export_one(sid)
    except Exception as exc:
        log.warning("video_ingest: md_export failed sid=%s: %s", sid, exc)

    return {
        "status": "completed",
        "substrate_id": sid,
        "title": title,
        "has_subtitle": bool(subtitle_text),
    }
