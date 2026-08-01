#!/usr/bin/env python3
"""书籍自动分类(2026-07-17)。读 aii.book_classify_config, 把 rclone 源里的新书按
混合规则(关键词先, LLM兜底)move 到对应文件夹, 记 aii.book_classify_log。

用法:
  python scripts/auto_classify_books.py            # owner=default
  python scripts/auto_classify_books.py --owner X --dry
被 systemd timer 定时调, 也被后端 /api/classify/run 复用(import run_classify)。
"""

import argparse
import asyncio
import json
import os
import subprocess
import unicodedata
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
import asyncpg


def _rclone(*a):
    return subprocess.run(["rclone", *a], capture_output=True, text=True)


def _lsf(source: str) -> list[str]:
    return [x for x in _rclone("lsf", source).stdout.splitlines() if x.strip()]


def _norm_name(name: str) -> str:
    s = unicodedata.normalize("NFKC", name)
    for pre in ("(NEW)", "(new)", "(New)"):
        if s.startswith(pre):
            s = s[len(pre) :]
            break
    return s


def _keyword_hit(name: str, categories: list[dict]) -> str | None:
    low = name.lower()
    for c in categories:
        for kw in c.get("keywords") or []:
            if kw.lower() in low:
                return c["folder"]
    return None


def _llm_classify(names: list[str], categories: list[dict]) -> dict:
    """一批书名 → {name: folder}。用 default provider(NIM 优先, deepseek 兜底)按 description 归类。"""
    if not names:
        return {}
    from aii.api._provider import _pipeline_nim_key, register_providers
    from obase import ProviderRegistry

    # ★NIM key 固化(仅本进程): deepseek 余额耗尽即 402, register_providers 本就"有 NIM key
    #   即作 default"。从密钥池兜底注入, 不写 aii/.env——后端 default(检索/入库)保持不变。
    #   池里加 "classify" 槽可给分类配独立 key, 缺省复用 econ。
    if not os.getenv("NVIDIA_NIM_API_KEY"):
        _k = _pipeline_nim_key("classify") or _pipeline_nim_key("econ")
        if _k:
            os.environ["NVIDIA_NIM_API_KEY"] = _k
    register_providers()
    llm = ProviderRegistry.get().llm("default")
    cat_desc = "\n".join(f"- {c['folder']}: {c.get('description', '')}" for c in categories)
    sys = (
        "你把书按文件名归到最合适的分类文件夹。只能用给定的文件夹名。输出 JSON 对象: "
        '{"完整文件名":"文件夹名", ...}。每个输入文件名都要有一条。分不准就选最接近的, 不要新造文件夹名。\n\n'
        f"可选文件夹:\n{cat_desc}"
    )
    # 分批: 大积压(200+书)单请求会超时/截断 JSON; 单批失败只丢该批, 其余照常
    out: dict = {}
    CHUNK = 30
    for i in range(0, len(names), CHUNK):
        batch = names[i : i + CHUNK]
        body = "待分类文件名:\n" + "\n".join(f"- {n}" for n in batch)
        try:
            raw = json.loads(llm.call_sync(sys + "\n\n" + body))
            if isinstance(raw, dict):
                # 偶发: LLM把系统提示里的JSON模板键"完整文件名"当字面输出, 套一层
                # {"完整文件名": {真实文件名: 文件夹, ...}}——解一层壳再合并
                if len(raw) == 1 and isinstance(next(iter(raw.values())), dict):
                    raw = next(iter(raw.values()))
                out.update(raw)
        except Exception as e:
            print(
                f"  ⚠ LLM 分类失败(第{i // CHUNK + 1}批{len(batch)}本归空, 留原处): {e}", flush=True
            )
    return out


async def run_classify(owner: str = "default", dry: bool = False, force: bool = False) -> dict:
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    row = await conn.fetchrow(
        "SELECT source, categories, skip_patterns, enabled FROM aii.book_classify_config WHERE owner=$1",
        owner,
    )
    if not row:
        await conn.close()
        return {"error": f"无配置 owner={owner}"}
    if not row["enabled"] and not force:
        await conn.close()
        print(
            f"[{owner}] 定时分类已禁用(enabled=false), 跳过。手动 /run 或 --force 可强跑。",
            flush=True,
        )
        return {"skipped": "disabled"}
    source = row["source"]
    categories = (
        json.loads(row["categories"]) if isinstance(row["categories"], str) else row["categories"]
    )
    skips = (
        json.loads(row["skip_patterns"])
        if isinstance(row["skip_patterns"], str)
        else row["skip_patterns"]
    )
    base = source.rsplit("/", 1)[0]  # gdrive-rw:books/all → gdrive-rw:books
    valid_folders = {c["folder"] for c in categories}

    files = _lsf(source)
    print(f"[{owner}] 源 {source}: {len(files)} 文件", flush=True)

    plan = []  # (name, folder|None, method)
    llm_pending = []
    for f in files:
        if any(s.lower() in f.lower() for s in skips):
            plan.append((f, None, "skip"))
            continue
        hit = _keyword_hit(f, categories)
        if hit:
            plan.append((f, hit, "keyword"))
        else:
            llm_pending.append(f)
    llm_map = {} if dry else _llm_classify(llm_pending, categories)
    # LLM偶发"清理"文件名再回传(全角/半角标点不一致, 或整段丢掉"(NEW)"前缀),
    # 原样查表会对不上——归一化(NFKC + 剥掉常见前缀)后兜底再查一次
    llm_map_norm = {_norm_name(k): v for k, v in llm_map.items()}
    for f in llm_pending:
        folder = llm_map.get(f) or llm_map_norm.get(_norm_name(f))
        plan.append((f, folder if folder in valid_folders else None, "llm"))

    moved = skipped = failed = 0
    for name, folder, method in plan:
        if folder is None:
            skipped += 1
            if not dry:
                await conn.execute(
                    "INSERT INTO aii.book_classify_log(owner,filename,category,method,moved_ok) VALUES($1,$2,NULL,$3,NULL)",
                    owner,
                    name,
                    method,
                )
            continue
        if dry:
            print(f"  [DRY {method}] {name[:50]} → {folder}", flush=True)
            moved += 1
            continue
        r = _rclone("moveto", f"{source}/{name}", f"{base}/{folder}/{name}")
        ok = r.returncode == 0
        moved += ok
        failed += not ok
        await conn.execute(
            "INSERT INTO aii.book_classify_log(owner,filename,category,method,moved_ok) VALUES($1,$2,$3,$4,$5)",
            owner,
            name,
            folder,
            method,
            ok,
        )
        print(f"  {'✓' if ok else '✗'} [{method}] {name[:46]} → {folder}", flush=True)

    await conn.close()
    summary = {"total": len(files), "moved": moved, "skipped": skipped, "failed": failed}
    print(f"[{owner}] 完成: {summary}", flush=True)
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner", default="default")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--force", action="store_true")  # 无视 enabled 强跑(API /run 用)
    args = ap.parse_args()
    asyncio.run(run_classify(args.owner, args.dry, args.force))
