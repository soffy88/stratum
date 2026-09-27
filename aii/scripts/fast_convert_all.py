#!/usr/bin/env python3
# ★极速 convert 全覆盖 — 跑其它/教辅/计算机/经济/数学所有"可转"< 5MB PDF.
# 跳过: 容器, 大文件, epub(只支持 PDF).
import os
import json
import sys
import subprocess
import time
from pathlib import Path

CACHE = Path("/data/soffy/projects/stratum/aii/context_pipeline/convert_analyze_cache.json")
cache = json.load(open(CACHE))

DST_MAP = {
    "/home/soffy/books/其它/": "/home/soffy/books/MD/其它/",
    "/home/soffy/books/教辅/": "/home/soffy/books/MD/教辅/",
    "/home/soffy/books/计算机/": "/home/soffy/books/MD/计算机/",
    "/home/soffy/books/数学/": "/home/soffy/books/MD/英文数学/",  # 英文为主
    "/home/soffy/books/Economic/": "/home/soffy/books/MD/经济学/",
}

candidates = []
for k, v in cache.items():
    if v.get("cat") != "可转":
        continue
    if not os.path.exists(k):
        continue
    sz = os.path.getsize(k)
    if sz > 5 * 1024 * 1024:
        continue
    if not k.lower().endswith(".pdf"):
        continue
    # 找目标 dir
    dst_dir = None
    for src_prefix, dst_prefix in DST_MAP.items():
        if k.startswith(src_prefix):
            dst_dir = dst_prefix
            break
    if not dst_dir:
        continue
    candidates.append((sz, k, dst_dir))

print(f"目标: {len(candidates)} 本 (< 5MB 可转 PDF)", flush=True)
candidates.sort()

sys.path.insert(0, str(Path(__file__).parent / "scripts"))

converted = 0
for sz, src, dst_dir in candidates:
    name = Path(src).name
    clean = name.replace("(z-lib", "").replace("(z-library", "").replace("(Z-Library", "").strip()
    dst = Path(dst_dir) / clean.replace(".pdf", ".md")
    if dst.exists():
        print(f"  [skip exists] {dst.name[:50]}", flush=True)
        continue

    print(
        f"  [convert] {clean[:50]} ({sz / 1024 / 1024:.1f}MB) → {dst_dir.split('/')[-2]}/",
        flush=True,
    )
    t0 = time.time()
    try:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-c",
                f'''
import sys
sys.path.insert(0, "{str(Path(__file__).parent / "scripts")}")
from oprim.parser.parse_pdf import parse_pdf
pc = parse_pdf(r"{src}", provider="pdf_inspector")
print(pc.markdown)
''',
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            out, err = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            out, err = proc.communicate()
            raise TimeoutError("pdf_inspector 10s 超时")

        if proc.returncode != 0:
            raise RuntimeError(f"pdf_inspector 失败: {err[:200]}")

        md = out.strip()
        if len(md) < 1000:
            raise RuntimeError(f"MD 太短 ({len(md)} 字符)")

        Path(dst_dir).mkdir(parents=True, exist_ok=True)
        Path(dst).write_text(md, encoding="utf-8")
        converted += 1
        print(f"    ✓ {len(md) // 1024}KB in {time.time() - t0:.1f}s → {dst.name[:40]}", flush=True)

    except Exception as e:
        print(f"    ✗ {e}", flush=True)

print(f"\n完成: {converted}/{len(candidates)} 本转换成功", flush=True)
