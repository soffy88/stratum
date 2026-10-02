#!/usr/bin/env python3
# ★极速 convert — 只跑"可转"且 < 5MB PDF, 直接调 pdf_inspector, 单本 timeout 10s.
import os
import json
import sys
import subprocess
import time
from pathlib import Path

CACHE = Path("/data/soffy/projects/stratum/aii/context_pipeline/convert_analyze_cache.json")
cache = json.load(open(CACHE))

candidates = []
for k, v in cache.items():
    if v.get("cat") != "可转":
        continue
    if not k.startswith("/home/soffy/books/其它/"):
        continue
    if not os.path.exists(k):
        continue
    sz = os.path.getsize(k)
    if sz > 5 * 1024 * 1024:
        continue
    candidates.append((sz, k))

print(f"目标: {len(candidates)} 本 (< 5MB 可转)", flush=True)
candidates.sort()

dst_root = Path("/home/soffy/books/MD/其它")
dst_root.mkdir(exist_ok=True)

sys.path.insert(0, str(Path(__file__).parent / "scripts"))

converted = 0
for sz, src in candidates:
    name = Path(src).name
    clean = name.replace("(z-lib", "").replace("(z-library", "").replace("(Z-Library", "").strip()
    dst = dst_root / clean.replace(".pdf", ".md").replace(".epub", ".md")
    if dst.exists():
        print(f"  [skip exists] {clean[:50]}", flush=True)
        continue

    print(f"  [convert] {clean[:50]} ({sz / 1024 / 1024:.1f}MB)", flush=True)
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

        dst.write_text(md, encoding="utf-8")
        converted += 1
        print(f"    ✓ {len(md) // 1024}KB in {time.time() - t0:.1f}s", flush=True)

    except Exception as e:
        print(f"    ✗ {e}", flush=True)

print(f"\n完成: {converted}/{len(candidates)} 本转换成功", flush=True)
