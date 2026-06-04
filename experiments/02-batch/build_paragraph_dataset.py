#!/usr/bin/env python3
"""
Build 10k paragraph dataset from #01 parsed outputs (pymupdf4llm best quality).
Saves to experiments/02-batch/benchmarks/paragraphs.jsonl
"""
import json, re
from pathlib import Path

BASE = Path(__file__).parent
PARSED = BASE / "parsed"
BENCH = BASE / "benchmarks"
BENCH.mkdir(exist_ok=True)

# Use pymupdf4llm as primary (best quality), supplement with others
SAMPLE_IDS = ["S1", "S2", "S3", "S4", "S5"]
DOMAIN_MAP = {
    "S1": "classical_chinese",
    "S2": "mathematics",
    "S3": "mathematics",
    "S4": "computer_science",
    "S5": "literature_en",
}

paragraphs = []

for sid in SAMPLE_IDS:
    md_path = PARSED / sid / "pymupdf4llm.md"
    if not md_path.exists():
        print(f"SKIP {sid}: no pymupdf4llm.md")
        continue
    text = md_path.read_text(encoding="utf-8")
    domain = DOMAIN_MAP[sid]
    # Split on double newline
    raw_paras = [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]
    # Filter: at least 50 chars, not a pure header/image line
    good_paras = []
    for p in raw_paras:
        # skip short, skip pure markdown headers without content, skip image placeholders
        if len(p) < 50:
            continue
        if p.startswith('#') and len(p) < 80:
            continue
        if re.match(r'^\[?(Illustration|Figure|Table|Image)\]?', p, re.I):
            continue
        good_paras.append(p)
    print(f"{sid}: {len(raw_paras)} raw → {len(good_paras)} good paragraphs (domain={domain})")
    for i, p in enumerate(good_paras):
        paragraphs.append({
            "id": f"{sid}-{i:04d}",
            "text": p,
            "domain": domain,
            "source": sid,
            "char_len": len(p),
        })

print(f"\nTotal paragraphs from PDFs: {len(paragraphs)}")

# If < 10000, oversample with sequential repetition
TARGET = 10000
if len(paragraphs) < TARGET:
    base_count = len(paragraphs)
    needed = TARGET - base_count
    extra = []
    idx = 0
    while len(extra) < needed:
        p = paragraphs[idx % base_count].copy()
        p["id"] = f"dup-{idx:05d}"
        extra.append(p)
        idx += 1
    paragraphs.extend(extra)
    print(f"Oversampled {needed} to reach {TARGET} total")

print(f"Final dataset: {len(paragraphs)} paragraphs")
print(f"Domain breakdown:")
from collections import Counter
counts = Counter(p["domain"] for p in paragraphs)
for d, c in sorted(counts.items()):
    print(f"  {d}: {c}")

# Save
out_path = BENCH / "paragraphs.jsonl"
with open(out_path, "w", encoding="utf-8") as f:
    for p in paragraphs:
        f.write(json.dumps(p, ensure_ascii=False) + "\n")
print(f"\nSaved to {out_path} ({out_path.stat().st_size//1024}KB)")
