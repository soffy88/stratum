#!/usr/bin/env python3
"""本地主题学习播客生成器 (qiaomu/NotebookLM 价值本地化, 3O 方式)。

B 仓主题 → LLM 双人对话脚本(NIM) → edge-tts 双音色 → ffmpeg 合并
→ ~/.stratum/vault/07-播客/<slug>.mp3 (Obsidian 中播放/通勤学习)

角色: A=讲解者(女声 Xiaoxiao) / B=提问者(男声 Yunxi), 一问一答推进。
全部本地/已有依赖, 零外部闭源服务。主题级粒度(79 主题), 按需/批量生成。

用法:
    .venv/bin/python scripts/podcast_generator.py [--theme <slug或id>] [--limit N] [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import asyncpg

REFINED_URL = os.getenv("REFINED_URL", "postgresql://aii:aii_safe_pass@localhost:5436/aii_refined")
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = Path.home() / ".stratum" / "vault" / "07-播客"
VOICE_A = "zh-CN-XiaoxiaoNeural"   # 讲解者(女)
VOICE_B = "zh-CN-YunxiNeural"      # 提问者(男)
MAX_LINES = 20                     # 每主题对话行数(≈3-5 分钟)

SYS = f"""你是学习播客编剧。根据给定主题材料, 写一段双人对话式播客脚本。
严格规则:
(1) A=讲解者(专业、清晰、善于举例), B=提问者(好奇、追问、常要例子)
(2) 一问一答交替, 共 {MAX_LINES} 行
(3) 内容必须基于给定材料, 禁止编造
(4) 每行 <=90 字, 口语化, 适合朗读
(5) 开头 A 用一句话引出主题, 结尾 A 用一句话总结
(6) 全程使用简体中文, 不允许出现英文句子或段落
(7) 专业术语首次出现时用中文, 括号内附英文: 如「稀缺性 (scarcity)」
(8) 输出 STRICT JSON: {{"lines":[{{"speaker":"A|B","text":"中文内容..."}}]}}"""


def _nim_key() -> str:
    k = os.getenv("NVIDIA_NIM_API_KEY")
    if k:
        return k
    try:
        d = json.loads((ROOT / ".pipeline_keys.json").read_text())
        return d.get("advmath_verify") or d.get("econ") or ""
    except Exception:
        return ""


async def _fetch_theme(conn, theme_id: int | str) -> dict | None:
    """主题材料: theme + top 概念 + 代表 KU point。"""
    if isinstance(theme_id, int) or str(theme_id).isdigit():
        th = await conn.fetchrow(
            "SELECT kc_id, theme_name, theme_name_en, summary, summary_zh"
            " FROM rf.refined_theme_kc WHERE kc_id=$1 AND is_current", int(theme_id))
    else:
        th = await conn.fetchrow(
            "SELECT kc_id, theme_name, theme_name_en, summary, summary_zh"
            " FROM rf.refined_theme_kc WHERE theme_name_en ILIKE $1 AND is_current",
            f"%{theme_id}%")
    if not th:
        return None
    # 主题 KU → 概念 → top 概念
    members = await conn.fetch("SELECT ku_id FROM rf.refined_kc_member WHERE kc_id=$1",
                               th["kc_id"])
    ku_ids = [m["ku_id"] for m in members]
    kus = await conn.fetch(
        "SELECT ku_id, point, point_zh FROM rf.refined_ku WHERE ku_id = ANY($1::text[])",
        ku_ids)
    ku_info = {r["ku_id"]: r for r in kus}
    kc = await conn.fetch(
        "SELECT ku_id, concept_id FROM rf.refined_ku_concept WHERE ku_id = ANY($1::text[])",
        ku_ids)
    cnt: dict[int, int] = {}
    for r in kc:
        cnt[r["concept_id"]] = cnt.get(r["concept_id"], 0) + 1
    top_c = sorted(cnt.items(), key=lambda x: -x[1])[:5]
    concepts = await conn.fetch(
        "SELECT concept_id, name, name_zh FROM rf.refined_concept"
        " WHERE concept_id = ANY($1::bigint[])", [c for c, _ in top_c])
    cnames = {c["concept_id"]: (c["name_zh"] or c["name"]) for c in concepts}
    pts = [ku_info[k]["point_zh"] or ku_info[k]["point"]
           for k in ku_ids[:12] if ku_info[k].get("point_zh") or ku_info[k].get("point")]
    return {
        "title": th["theme_name_en"] or th["theme_name"],
        "summary": th["summary_zh"] or th["summary"] or "",
        "concepts": [cnames.get(c) for c, _ in top_c if cnames.get(c)],
        "points": pts[:10],
    }


async def _gen_script(theme: dict) -> list[dict]:
    """NIM 生成对话脚本。"""
    import httpx
    key = _nim_key()
    if not key:
        raise RuntimeError("无 NIM key")
    material = (
        f"主题: {theme['title']}\n"
        f"概述: {theme['summary']}\n"
        f"核心概念: {'、'.join(theme['concepts'] or [])}\n"
        f"要点:\n" + "\n".join(f"- {p}" for p in theme["points"] or []))
    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": os.getenv("NIM_MODEL", "nvidia/llama-3.3-nemotron-super-49b-v1.5"),
                "messages": [
                    {"role": "system", "content": SYS},
                    {"role": "user", "content": material[:6000]},
                ],
                "response_format": {"type": "json_object"},
                "max_tokens": 3200,
            },
        )
        out = resp.json()["choices"][0]["message"]["content"]
        if not out:
            raise RuntimeError("NIM 空响应")
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            # 截断容错: 提取最后一个完整 JSON 对象
            m = re.search(r"\{.*\}", out, re.DOTALL)
            if not m:
                raise
            data = json.loads(m.group(0))
    return [l for l in data.get("lines", []) if l.get("speaker") in ("A", "B") and l.get("text")]


def _clean_tts(text: str) -> str:
    """edge-tts 容错: 清理特殊字符/控制符/emoji, 避免 NoAudioReceived。"""
    import re
    t = text.strip()
    # 移除 control chars (保留换行/制表)
    t = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", t)
    # 移除 emoji/特殊符号
    t = re.sub(r"[𐀀-􏿿]", "", t)
    # 规范化引号
    t = t.replace("\u201c", '"').replace("\u201d", '"')
    t = t.replace("\u2018", "'").replace("\u2019", "'")
    # 移除连续标点/断行符
    t = re.sub(r"[\u2028\u2029\u00ad]", "", t)
    t = re.sub(r"[…]{2,}", "…", t)
    return t.strip()


async def _tts_line(text: str, voice: str, out: Path) -> None:
    text = _clean_tts(text)
    if len(text) < 3:
        raise ValueError(f"text too short after clean: {repr(text)}")

    import edge_tts
    comm = edge_tts.Communicate(text, voice, rate="-5%")
    await comm.save(str(out))


async def generate(theme_id: int | str, out_dir: Path, dry: bool = False, suffix: str = "") -> str | None:
    conn = await asyncpg.connect(REFINED_URL)
    try:
        theme = await _fetch_theme(conn, theme_id)
    finally:
        await conn.close()
    if not theme:
        print(f"❌ 主题未找到: {theme_id}")
        return None
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", theme["title"])[:50].strip("-")
    if suffix:
        slug = f"{slug}{suffix}"
    print(f"🎙 {theme['title']} — {len(theme['concepts'])} 概念, {len(theme['points'])} 要点")

    lines = await _gen_script(theme)
    if not lines:
        print("❌ 脚本生成失败")
        return None
    print(f"  脚本 {len(lines)} 行")

    if dry:
        for l in lines[:5]:
            print(f"  [{l['speaker']}] {l['text'][:60]}")
        return None

    out_dir.mkdir(parents=True, exist_ok=True)
    mp3 = out_dir / f"{slug}.mp3"
    with tempfile.TemporaryDirectory() as td:
        segs = []
        for i, l in enumerate(lines):
            seg = Path(td) / f"s{i:03d}.mp3"
            try:
                await _tts_line(l["text"], VOICE_A if l["speaker"] == "A" else VOICE_B, seg)
                segs.append(seg)
            except Exception as e:
                print(f"  ⚠ 跳过行 {i} [{l['speaker']}]: {e}")
        # ffmpeg concat 合并
        lst = Path(td) / "list.txt"
        lst.write_text("\n".join(f"file '{s}'" for s in segs), encoding="utf-8")
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                        "-c", "copy", str(mp3)],
                       capture_output=True, timeout=300)
    print(f"  ✅ {mp3} ({mp3.stat().st_size // 1024}KB)")
    return str(mp3)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--theme", help="主题 id 或名称(缺省=列出主题)")
    ap.add_argument("--limit", type=int, default=0, help="批量生成前 N 个主题")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--suffix", default="", help="文件名后缀 (如 -英文)")
    args = ap.parse_args()

    if not args.theme and not args.limit:
        conn = await asyncpg.connect(REFINED_URL)
        rows = await conn.fetch(
            "SELECT kc_id, theme_name_en FROM rf.refined_theme_kc"
            " WHERE is_current ORDER BY kc_id LIMIT 20")
        await conn.close()
        print("可用主题(前 20):")
        for r in rows:
            print(f"  {r['kc_id']}: {r['theme_name_en']}")
        return 0

    if args.theme:
        await generate(args.theme, OUT_DIR, args.dry_run, args.suffix)
    else:
        conn = await asyncpg.connect(REFINED_URL)
        rows = await conn.fetch(
            "SELECT kc_id FROM rf.refined_theme_kc WHERE is_current ORDER BY kc_id")
        await conn.close()
        for r in rows[: args.limit]:
            try:
                await generate(r["kc_id"], OUT_DIR, args.dry_run, args.suffix)
            except Exception as e:  # noqa: BLE001
                print(f"  ⚠ {r['kc_id']}: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
